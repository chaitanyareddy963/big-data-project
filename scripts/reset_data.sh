#!/usr/bin/env bash
set -euo pipefail

set -a
source ./.env
set +a

rm -rf data/local/*
rm -rf checkpoints/*

docker compose run --rm minio-init /bin/sh -c "
mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin123} >/dev/null
mc rm -r --force local/raw || true
mc rm -r --force local/bronze || true
mc rm -r --force local/silver || true
mc rm -r --force local/gold || true
mc rm -r --force local/mlflow/serving || true
mc mb -p local/raw || true
mc mb -p local/bronze || true
mc mb -p local/silver || true
mc mb -p local/gold || true
mc mb -p local/mlflow || true
"
