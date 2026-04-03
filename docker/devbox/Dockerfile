FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git procps default-jdk-headless docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    bentoml==1.3.16 \
    fastapi \
    "uvicorn[standard]" \
    kafka-python \
    minio \
    boto3 \
    requests \
    pandas \
    numpy \
    pyarrow \
    scikit-learn \
    joblib \
    mlflow \
    pyspark==3.5.1 \
    delta-spark==3.1.0 \
    pydantic \
    jupyterlab

WORKDIR /workspace
