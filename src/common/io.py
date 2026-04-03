from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.client import Config

from src.common.config import AppConfig


def get_s3_client(config: AppConfig | None = None):
    config = config or AppConfig()
    return boto3.client(
        "s3",
        endpoint_url=config.minio_http_endpoint,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme not in {"s3", "s3a"}:
        raise ValueError(f"Unsupported URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def upload_file(local_path: str | Path, bucket: str, key: str, config: AppConfig | None = None) -> None:
    client = get_s3_client(config)
    client.upload_file(str(local_path), bucket, key)


def upload_json(payload: dict, uri: str, config: AppConfig | None = None) -> None:
    bucket, key = parse_s3_uri(uri)
    client = get_s3_client(config)
    body = json.dumps(payload, indent=2).encode("utf-8")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def download_bytes(uri: str, config: AppConfig | None = None) -> bytes:
    bucket, key = parse_s3_uri(uri)
    client = get_s3_client(config)
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def list_keys(prefix_uri: str, config: AppConfig | None = None) -> list[str]:
    bucket, prefix = parse_s3_uri(prefix_uri)
    client = get_s3_client(config)
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            keys.append(item["Key"])
    return keys


def download_to_buffer(uri: str, config: AppConfig | None = None) -> io.BytesIO:
    return io.BytesIO(download_bytes(uri, config))
