FROM apache/airflow:2.10.5-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends make docker-ce-cli docker-compose-plugin && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir boto3 minio mlflow kafka-python requests
