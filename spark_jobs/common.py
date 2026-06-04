"""Shared configuration for Spark jobs that read and write MinIO through S3A."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import boto3
from pyspark.sql import Column
from pyspark.sql import functions as F
from pyspark.sql import SparkSession
from pyspark.sql.types import IntegralType


@dataclass(frozen=True)
class Settings:
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    aws_region: str
    raw_bucket: str
    lakehouse_bucket: str
    spark_master: str


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        minio_endpoint=_required_env("MINIO_ENDPOINT_INTERNAL"),
        minio_access_key=_required_env("MINIO_ROOT_USER"),
        minio_secret_key=_required_env("MINIO_ROOT_PASSWORD"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        raw_bucket=_required_env("RAW_BUCKET"),
        lakehouse_bucket=_required_env("LAKEHOUSE_BUCKET"),
        spark_master=os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077"),
    )


def s3a_uri(bucket: str, key: str = "") -> str:
    suffix = key.lstrip("/")
    return f"s3a://{bucket}/{suffix}" if suffix else f"s3a://{bucket}/"


def create_spark_session(
    app_name: str,
    settings: Settings,
    *,
    with_delta: bool = False,
    extra_packages: list[str] | None = None,
) -> SparkSession:
    # Spark 4 creates a relative artifacts directory during SQL actions.
    # Run from writable temporary storage instead of the mounted repository.
    work_dir = Path(os.getenv("SPARK_WORK_DIR", f"/tmp/spark-work-{os.getuid()}"))
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(work_dir)
    spark_local_dir = Path(os.getenv("SPARK_LOCAL_DIR", f"/tmp/spark-local-{os.getuid()}"))
    spark_local_dir.mkdir(parents=True, exist_ok=True)

    builder = (
        SparkSession.builder.appName(app_name)
        .master(settings.spark_master)
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "3g"))
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "16"))
        .config("spark.local.dir", str(spark_local_dir))
        .config("spark.sql.legacy.parquet.nanosAsLong", "true")
        .config("spark.hadoop.fs.s3a.endpoint", settings.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", settings.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        # hadoop-aws 3.3.4 expects these values as plain integers. Newer
        # Hadoop defaults use duration suffixes, which break S3A startup.
        .config("spark.hadoop.fs.s3a.threads.keepalivetime", "60")
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000")
        .config("spark.hadoop.fs.s3a.connection.timeout", "200000")
        .config("spark.hadoop.fs.s3a.connection.request.timeout", "0")
        .config("spark.hadoop.fs.s3a.multipart.purge.age", "86400")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )
    if with_delta:
        from delta import configure_spark_with_delta_pip

        builder = (
            builder.config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
        )
        builder = configure_spark_with_delta_pip(builder, extra_packages=extra_packages)
    return builder.getOrCreate()


def normalized_timestamp(df, column_name: str) -> Column:
    """Return a timestamp column for native timestamps or Parquet nanoseconds."""
    data_type = df.schema[column_name].dataType
    if isinstance(data_type, IntegralType):
        return F.expr(f"timestamp_micros(CAST({column_name} / 1000 AS BIGINT))")
    return F.col(column_name).cast("timestamp")


def create_s3_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name=settings.aws_region,
    )


def ensure_bucket_exists(settings: Settings, bucket: str) -> None:
    s3 = create_s3_client(settings)
    buckets = {entry["Name"] for entry in s3.list_buckets()["Buckets"]}
    if bucket not in buckets:
        raise RuntimeError(f"Required MinIO bucket does not exist: {bucket}")
