#!/usr/bin/env bash
set -euo pipefail

set -a
source ./.env
set +a

docker compose down
rm -rf data/local/*
rm -rf checkpoints/*
rm -rf volumes/postgres/* volumes/minio/* volumes/kafka/* volumes/grafana/* volumes/spark-events/*
