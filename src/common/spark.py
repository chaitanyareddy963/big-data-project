from __future__ import annotations

from pyspark.sql import SparkSession

from src.common.config import AppConfig


def create_spark_session(app_name: str) -> SparkSession:
    config = AppConfig()
    builder = (
        SparkSession.builder.appName(app_name)
        .master(config.spark_master_url)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.endpoint", config.minio_http_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", config.aws_access_key_id)
        .config("spark.hadoop.fs.s3a.secret.key", config.aws_secret_access_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.driver.memory", "1g")
        .config("spark.executor.memory", "2g")
        .config("spark.executor.cores", "2")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.streaming.stopGracefullyOnShutdown", "true")
    )
    return builder.getOrCreate()
