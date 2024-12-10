FROM python:3.9-slim
RUN apt-get update && apt-get install -y \
     build-essential \
     python3-dev \
     gcc \
     && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# RUN mkdir -p /app/training
# COPY boutique_train.json /app/training/frontend_shippingservice.json
# COPY boutique_train.json /app/training/frontend_productcatalog.json
COPY incident_detector.py /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE  8003
ENV PYTHONUNBUFFERED=1
CMD ["python", "incident_detector.py", "--port", "8003", "--services", "lab7_frontend_2_shippingservice", "lab7_frontend_2_productcatalogservice"]"
