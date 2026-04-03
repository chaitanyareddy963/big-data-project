# Demo Runbook

## Commands In Order

```bash
cd ~/big-data-project

make up
make init-topics
make smoke

make ingest-sample
make build-silver
make build-gold
make train

make monitoring
make airflow

docker compose exec airflow-webserver airflow dags test aviation_disruption_mvp 2026-04-03
docker compose exec airflow-webserver airflow dags list-runs -d aviation_disruption_mvp

docker compose --profile dev run --rm devbox python -m src.api.bundle_model
docker compose --profile dev run --rm -p 127.0.0.1:3001:3001 devbox \
  bentoml serve src.api.service:svc --host 0.0.0.0 --port 3001
```

In a second terminal:

```bash
curl -s http://127.0.0.1:3001/health -H 'Content-Type: application/json' -d '{}'
curl -s http://127.0.0.1:3001/predict -H 'Content-Type: application/json' -d @configs/sample_request.json
make replay
```

## Screens To Open

1. README architecture section
2. MinIO at `http://127.0.0.1:9001`
3. MLflow at `http://127.0.0.1:5000`
4. Airflow at `http://127.0.0.1:8088`
5. Prometheus at `http://127.0.0.1:9090`
6. Grafana at `http://127.0.0.1:3000`

## Fallback If Something Fails

If the live DAG run or UI is slow:

```bash
make smoke
docker compose exec airflow-webserver airflow dags list-runs -d aviation_disruption_mvp
curl -s http://127.0.0.1:3001/health -H 'Content-Type: application/json' -d '{}'
curl -s http://127.0.0.1:3001/predict -H 'Content-Type: application/json' -d @configs/sample_request.json
make replay
docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --list
```

This still demonstrates the strongest path: replay, Delta outputs, MLflow artifact export, serving, and orchestration history.
