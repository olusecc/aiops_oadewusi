import argparse
import time
import requests
import pandas as pd
import numpy as np
from prophet import Prophet
from datetime import datetime
import json
from prometheus_client import start_http_server, Gauge

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--from_service", required=True, help="Source service name")
parser.add_argument("-t", "--to_service", required=True, help="Destination service name")
parser.add_argument("-d", "--training_data", required=True, help="Path to training data JSON file")
parser.add_argument("-p", "--port", required=True, type=int, help="Prometheus scrape port")
parser.add_argument("--prefix", required=True, help="Prefix for Prometheus metrics")
args = parser.parse_args()

# Prometheus metrics
prefix = args.prefix
anomaly_count_gauge = Gauge(f"{prefix}_anomaly_count", "Number of detected anomalies")
mae_gauge = Gauge(f"{prefix}_model_mae", "Mean Absolute Error of the model")
mape_gauge = Gauge(f"{prefix}_model_mape", "Mean Absolute Percentage Error of the model")
y_gauge = Gauge(f"{prefix}_y", "Observed value of y")
y_min_gauge = Gauge(f"{prefix}_y_min", "Predicted minimum value for y")
y_max_gauge = Gauge(f"{prefix}_y_max", "Predicted maximum value for y")

# Prometheus query
url = 'http://prometheus.istio-system:9090/api/v1/query'
query = f'histogram_quantile(0.5, rate(istio_request_duration_milliseconds_bucket{{source_app="{args.from_service}", destination_app="{args.to_service}", reporter="source"}}[1m]))'

def load_training_data():
    with open(args.training_data, 'r') as file:
        data = json.load(file)
    
    values = data['data']['result'][0]['values']
    df_train = pd.DataFrame(values, columns=['ds', 'y'])
    
    df_train['ds'] = pd.to_datetime(df_train['ds'], unit='s')
    df_train['y'] = df_train['y'].astype(float)
    
    df_train['ds'] = df_train['ds'] - df_train['ds'].iloc[0]
    df_train['ds'] = df_train['ds'].dt.total_seconds()
    df_train['ds'] = df_train['ds'].apply(lambda sec: datetime.fromtimestamp(sec))
    
    return df_train

def train_prophet_model(df_train):
    model = Prophet(
        growth='flat',
        seasonality_mode='additive',
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=True,
        changepoint_prior_scale=0.05,
    )
    model.add_seasonality(name='hourly', period=1, fourier_order=5)
    model.fit(df_train)
    return model

def get_current_data():
    try:
        response = requests.get(url, params={'query': query})
        response_data = response.json()
        
        if 'data' in response_data and 'result' in response_data['data'] and len(response_data['data']['result']) > 0:
            for result in response_data['data']['result']:
                timestamp, value = result['value']
                try:
                    float_value = float(value)
                    if not np.isnan(float_value):
                        return pd.DataFrame({'ds': [datetime.fromtimestamp(float(timestamp))], 'y': [float_value]})
                except (ValueError, TypeError):
                    continue
            return None
        else:
            return None
            
    except (KeyError, IndexError, ValueError, requests.RequestException):
        return None

def detect_anomalies(model, df):
    if df is None or df['y'].iloc[0] <= 0:
        return pd.DataFrame({
            'ds': [datetime.now()],
            'y': [0.0],
            'yhat': [model.predict(pd.DataFrame({'ds': [datetime.now()]}))['yhat'].iloc[0]],
            'yhat_lower': [0.0],
            'yhat_upper': [0.0],
            'anomaly': [True]
        })
    
    forecast = model.predict(df)
    df['yhat'] = forecast['yhat']
    df['yhat_lower'] = forecast['yhat_lower']
    df['yhat_upper'] = forecast['yhat_upper']
    
    lower_threshold = 0.9
    upper_threshold = 1.1
    relative_threshold = 0.5
    
    df['anomaly'] = (
        (df['y'] < df['yhat_lower'] * lower_threshold) |
        (df['y'] > df['yhat_upper'] * upper_threshold) |
        (df['y'] <= 0) |
        (abs(df['y'] - df['yhat']) / df['yhat'] > relative_threshold)
    )
    
    return df

def calculate_metrics(df):
    if df is None or len(df) == 0:
        return 0.0, 0.0
    
    y_true = df['y'].values
    y_pred = df['yhat'].values
    
    mae = np.mean(np.abs(y_true - y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    
    return mae, min(mape * 0.01, 100.0)

def main():
    start_http_server(args.port)
    df_train = load_training_data()
    model = train_prophet_model(df_train)
    test_start_time = datetime.now()
    anomaly_count = 0
    index = 0
    previous_mae = 0
    previous_mape = 0
    
    col_widths = {
        'id': 6,
        'timestamp': 25,
        'anomalies': 12,
        'observed': 15,
        'predicted': 15,
        'mae': 15,
        'mape': 15
    }
    
    print("\n{:^{id}} {:^{ts}} {:^{ano}} {:^{obs}} {:^{pred}} {:^{mae}} {:^{mape}}".format(
        "ID", "Timestamp", "Anomalies", "Observed", "Predicted", "MAE", "MAPE",
        id=col_widths['id'], ts=col_widths['timestamp'], 
        ano=col_widths['anomalies'], obs=col_widths['observed'],
        pred=col_widths['predicted'], mae=col_widths['mae'],
        mape=col_widths['mape']
    ))
    print("-" * sum(col_widths.values()))
    
    while True:
        df = get_current_data()
        current_time = datetime.now()
        
        if df is not None:
            df['ds'] = df['ds'] - test_start_time
            df['ds'] = df['ds'].dt.total_seconds()
            df['ds'] = df['ds'].apply(lambda sec: datetime.fromtimestamp(sec))
            
            df = detect_anomalies(model, df)
            mae, mape = calculate_metrics(df)
            
            if df['anomaly'].iloc[0] and (mae != previous_mae or mape != previous_mape):
                anomaly_count = 1
            else:
                anomaly_count = 0 
            
            previous_mae = mae
            previous_mape = mape
            
            anomaly_count_gauge.set(anomaly_count)
            mae_gauge.set(mae)
            mape_gauge.set(mape)
            y_min_gauge.set(df['yhat_lower'].iloc[0])
            y_gauge.set(df['y'].iloc[0])
            y_max_gauge.set(df['yhat_upper'].iloc[0])
            
            print("{:^{id}} {:^{ts}} {:^{ano}} {:^{obs}.6f} {:^{pred}.6f} {:^{mae}.6f} {:^{mape}.6f}".format(
                index,
                current_time.strftime('%Y-%m-%d %H:%M:%S'),
                anomaly_count,
                df['y'].iloc[0],
                df['yhat'].iloc[0],
                mae,
                mape,
                id=col_widths['id'], ts=col_widths['timestamp'],
                ano=col_widths['anomalies'], obs=col_widths['observed'],
                pred=col_widths['predicted'], mae=col_widths['mae'],
                mape=col_widths['mape']
            ))
        else:
            print("{:^{id}} {:^{ts}} {:^{ano}} {:^{obs}.6f} {:^{pred}.6f} {:^{mae}.6f} {:^{mape}.6f}".format(
                index,
                current_time.strftime('%Y-%m-%d %H:%M:%S'),
                anomaly_count,
                0.000000,
                0.000000,
                0.000000,
                0.000000,
                id=col_widths['id'], ts=col_widths['timestamp'],
                ano=col_widths['anomalies'], obs=col_widths['observed'],
                pred=col_widths['predicted'], mae=col_widths['mae'],
                mape=col_widths['mape']
            ))
        
        index += 1
        time.sleep(60)

if __name__ == "__main__":
    main()