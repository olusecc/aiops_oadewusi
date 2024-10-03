FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8003
ENV PYTHONBUFFERED=1
CMD ["python", "monitor_app.py"]

