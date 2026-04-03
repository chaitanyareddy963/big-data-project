#!/usr/bin/env bash
set -euo pipefail

set -a
source ./.env
set +a

echo "== docker compose ps =="
docker compose ps

echo "== minio buckets =="
docker compose run --rm minio-init -c "
mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin123} >/dev/null
mc ls local
"

echo "== kafka topics =="
docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --list

echo "== mlflow health =="
curl -fsS http://127.0.0.1:5000/ >/dev/null
echo "mlflow reachable"
