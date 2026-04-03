#!/usr/bin/env bash
set -euo pipefail

set -a
source ./.env
set +a

required_topics=("weather.live" "weather.replay" "disruption.scores")
required_buckets=("raw" "bronze" "silver" "gold" "mlflow")

echo "== docker compose ps =="
docker compose ps

echo "== core health endpoints =="
curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null
echo "minio reachable"
curl -fsS http://127.0.0.1:5000/ >/dev/null
echo "mlflow reachable"
curl -fsS http://127.0.0.1:8080 >/dev/null
echo "spark master UI reachable"

echo "== minio buckets =="
bucket_output="$(docker compose run --rm minio-init -c "
mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin123} >/dev/null
mc ls local
" )"
printf '%s\n' "$bucket_output"
for bucket in "${required_buckets[@]}"; do
  printf '%s\n' "$bucket_output" | grep -q "[[:space:]]${bucket}/$"
done

echo "== kafka topics =="
topic_output="$(docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --list)"
printf '%s\n' "$topic_output"
for topic in "${required_topics[@]}"; do
  printf '%s\n' "$topic_output" | grep -q "^${topic}$"
done

echo "== sample data =="
test -f data/sample/aviation_events_smoke.csv
head -n 2 data/sample/aviation_events_smoke.csv

echo "== serving export =="
docker compose --profile dev run --rm devbox python - <<'PY'
from src.common.config import AppConfig
from src.common.io import list_keys

config = AppConfig()
keys = list_keys(config.model_export_uri, config)
if keys:
    print("serving export present")
    for key in keys:
        print(key)
else:
    print("serving export not present yet; run make train to create it")
PY

echo "== airflow and monitoring (optional) =="
if docker compose ps --services --filter status=running | grep -q '^airflow-webserver$'; then
  curl -fsS http://127.0.0.1:8088/health
  echo
  echo "airflow reachable"
fi

if docker compose ps --services --filter status=running | grep -q '^prometheus$'; then
  curl -fsS http://127.0.0.1:9090/-/healthy >/dev/null
  echo "prometheus reachable"
fi

if docker compose ps --services --filter status=running | grep -q '^grafana$'; then
  curl -fsS http://127.0.0.1:3000/api/health >/dev/null
  echo "grafana reachable"
fi
