import pandas as pd
from prophet import Prophet
from prometheus_client import Gauge, start_http_server
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
import requests
import numpy
from datetime import datetime, timedelta
import logging
import time
import pickle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('prophet').setLevel(logging.WARNING)
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

anomaly_count = Gauge('anomaly_count', 'Number of anomalies detected')
mae_metric = Gauge('mae_metric', 'Mean Absolute Error')
mape_metric = Gauge('mape_metric', 'Mean Absolute Percentage Error')
start_http_server(8003)

def fetch_metric_data(metric_name, start_time, end_time, step='15s'):
    url = f"http://prometheus:9090/api/v1/query_range"
    params = {
        'query': metric_name,
        'start': start_time.timestamp(),
        'end': end_time.timestamp(),
        'step': step
    }
    results = requests.get(url, params=params).json().get('data', {}).get('result', [])
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results[0]['values'], columns=['ds', 'y'])
    df['ds'] = pd.to_datetime(df['ds'], unit='s')
    df['y'] = df['y'].astype(float)
    return df

def train_model(train_data):
    model = Prophet(growth='flat', daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
    model.fit(train_data)
    with open('prophet_model.pkl', 'wb') as f:
        pickle.dump(model, f)
    return model

def load_model():
    with open('prophet_model.pkl', 'rb') as f:
        model = pickle.load(f)
    return model

def detect_anomalies(model, test_data):
    forecast = model.predict(test_data)
    forecast['ds'] = pd.to_datetime(forecast['ds'])
    merged = forecast.merge(test_data, on='ds', how='inner')
    return merged[merged['y'] > merged['yhat_upper']], forecast

def main():
    all_results = pd.DataFrame()
    cumulative_anomaly_count = 0
    model = None
    
    # Train the model once
    end_time = datetime.now()
    train_data = fetch_metric_data('train_gauge', end_time - timedelta(minutes=5), end_time)
    if not train_data.empty:
        model = train_model(train_data)
        logging.info("Model trained successfully")
    else:
        logging.error("Training data is empty, unable to train the model.")
        return

    while True:
        try:
            if not model:
                model = load_model()
                logging.info("Loaded saved model successfully")
            
            # Fetch test data
            test_data = fetch_metric_data('test_gauge', end_time, datetime.now())
            if test_data.empty:
                logging.warning("Test data empty, skipping cycle")
                continue
            
            # Detect anomalies using the pre-trained model
            anomalies, forecast = detect_anomalies(model, test_data)
            cumulative_anomaly_count += len(anomalies)
            anomaly_count.set(cumulative_anomaly_count)
            
            # Calculate and set metrics
            mae = mean_absolute_error(test_data['y'], forecast['yhat'][:len(test_data)])
            mape = mean_absolute_percentage_error(test_data['y'], forecast['yhat'][:len(test_data)])
            mae_metric.set(mae)
            mape_metric.set(mape)
            
            # Log results
            current_results = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
            current_results['y'] = test_data['y'].values
            current_results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_results['anomaly_count'] = cumulative_anomaly_count
            current_results['ds'] = current_results['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
            current_results = current_results[['timestamp', 'ds', 'y', 'yhat', 'yhat_lower', 'yhat_upper', 'anomaly_count']]
            all_results = pd.concat([all_results, current_results], ignore_index=True)
            
            logging.info(f"Anomalies: {len(anomalies)}, Cumulative: {cumulative_anomaly_count}, MAE: {mae:.4f}, MAPE: {mape:.4f}")
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            logging.info("All Results:\n" + all_results.to_string(index=False))
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
