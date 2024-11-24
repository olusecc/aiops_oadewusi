FROM python:3.9-slim
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py .
COPY boutique_train.json .
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["python", "monitor.py"]