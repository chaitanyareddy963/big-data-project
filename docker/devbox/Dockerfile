FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git procps default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    bentoml \
    fastapi \
    "uvicorn[standard]" \
    kafka-python \
    minio \
    boto3 \
    requests \
    pandas \
    pyarrow \
    pyspark \
    delta-spark \
    jupyterlab

WORKDIR /workspace
