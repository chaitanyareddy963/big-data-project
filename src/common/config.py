from __future__ import annotations

import os
from dataclasses import dataclass

from src.common.contracts import MODEL_EXPORT_URI


@dataclass(frozen=True)
class AppConfig:
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    minio_endpoint: str = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000").replace(
        "http://", ""
    )
    minio_http_endpoint: str = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    spark_master_url: str = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    model_export_uri: str = os.getenv("MODEL_EXPORT_URI", MODEL_EXPORT_URI)
