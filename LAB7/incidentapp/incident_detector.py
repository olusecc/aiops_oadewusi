import time
from prometheus_client import Gauge, start_http_server
import requests
import argparse
import random

# Argument parsing
parser = argparse.ArgumentParser()
parser.add_argument("--threshold", type=int, default=4, help="Incident threshold")
parser.add_argument("--services", nargs=2, required=True, help="Two service prefixes (SVC1, SVC2)")
parser.add_argument("--port", type=int, required=True, help="Prometheus scrape port")
args = parser.parse_args()

# Prometheus metrics
temperature_gauge = Gauge("incident_temperature", "Current sum of accumulators")
sev1_gauge = Gauge("incident_sev1", "Sev 1 incident flag (0 or 1)")
sev2_gauge = Gauge("incident_sev2", "Sev 2 incident flag (0 or 1)")

# Initialize accumulators for the services
accumulators = {service: 0 for service in args.services}

# Prometheus query configuration
PROMETHEUS_URL = "http://prometheus.istio-system:9090/api/v1/query"
ANOMALY_QUERY_TEMPLATE = "sum({prefix}_anomaly_count) by (job)"


def fetch_anomaly_count(service):
    """
    Fetches the anomaly count for a given service using Prometheus queries.
    Implements retries with exponential backoff in case of failures.
    """
    query = ANOMALY_QUERY_TEMPLATE.format(prefix=service)
    retries = 3
    for attempt in range(retries):
        try:
            if attempt > 0:
                print(f"Retrying query for {service}: Attempt {attempt + 1}")
            else:
                print(f"Querying Prometheus for {service}: {query}")

            response = requests.get(PROMETHEUS_URL, params={"query": query}, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data["data"]["result"]:
                print(f"[{service}] No data found for query: {query}")
                return 0

            # Extract the anomaly count from the query result
            print(f"[{service}] Query result: {data['data']['result']}")
            return int(float(data["data"]["result"][0]["value"][1]))

        except requests.exceptions.RequestException as e:
            print(f"Error during Prometheus query for {service}: {e}")
            time.sleep(2 ** attempt + random.uniform(0, 1))  # Exponential backoff

    print(f"Failed to fetch anomaly count for {service} after {retries} retries.")
    return 0


def monitor_incidents():
    """
    Main monitoring loop for the incident detector.
    Fetches anomaly counts for each service, updates accumulators, calculates
    the total temperature, and evaluates incident severity.
    """
    while True:
        try:
            # Fetch and update anomaly counts for each service
            for service in args.services:
                anomaly_count = fetch_anomaly_count(service)

                if anomaly_count > 0:
                    accumulators[service] += 1
                else:
                    accumulators[service] = max(0, accumulators[service] - 2)

            # Calculate the total "temperature" (sum of accumulators)
            total_temperature = sum(accumulators.values())
            temperature_gauge.set(total_temperature)

            # Determine incident severity
            sev1_flag = 1 if total_temperature > args.threshold and all(acc > 0 for acc in accumulators.values()) else 0

            sev2_flag = 1 if total_temperature > args.threshold and not sev1_flag else 0

            sev1_gauge.set(sev1_flag)
            sev2_gauge.set(sev2_flag)

            # Debugging output for monitoring
            print("\n--- Incident Monitoring Status ---")
            print(f"Accumulators: {accumulators}")
            print(f"Temperature: {total_temperature}")
            print(f"Severity Levels - Sev1: {sev1_flag}, Sev2: {sev2_flag}")
            print("-----------------------------------\n")

            # Wait before the next cycle
            time.sleep(60)

        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            time.sleep(60)


if __name__ == "__main__":
    print(f"Starting Incident Detector on port {args.port}...")
    start_http_server(args.port)
    monitor_incidents()
