from prometheus_client import start_http_server, Gauge, Histogram
import random
import time

# Define metrics
test_gauge = Gauge('test_gauge', 'Test Gauge between 0 and 1')
train_gauge = Gauge('train_gauge', 'Train Gauge between 0 and 0.6')
test_hist = Histogram('test_hist', 'Test Histogram between 0 and 1', buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0))
train_hist = Histogram('train_hist', 'Train Histogram between 0 and 0.6', buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6))

def emit_data():
    """Emit fake data"""
    time.sleep(5)
    test_value = random.uniform(0, 1)
    train_value = random.uniform(0, 0.6)
    test_gauge.set(test_value)
    train_gauge.set(train_value)
    
    test_hist.observe(test_value)
    train_hist.observe(train_value)

    

if __name__ == '__main__':
    start_http_server(8000)
    while True:
        emit_data()
