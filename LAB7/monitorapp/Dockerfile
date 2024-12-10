FROM python:3.9-slim
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN mkdir -p /app/training
COPY boutique_train.json /app/training/frontend_shippingservice.json
COPY boutique_train.json /app/training/frontend_productcatalog.json
COPY anomaly-monitor.py /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE  8001 8002
ENV PYTHONUNBUFFERED=1
CMD ["python", "anomaly-monitor.py"]
