# Aviation Disruption Intelligence MVP

Single-VM MVP for an aviation disruption intelligence platform using Kafka, MinIO, Delta Lake, Spark, MLflow, BentoML, Prometheus, Grafana, and Airflow. Everything runs locally on one Debian 12 VM through Docker Compose.

## Architecture

`data/sample` or `data/local` -> ingest job -> MinIO `raw` -> Spark Delta `bronze/silver/gold` -> training -> MLflow + stable serving export -> BentoML inference -> replay to Kafka -> Spark streaming score -> Kafka `disruption.scores` + Delta scored output

## Folder Structure

```text
big-data-project/
  data/
    sample/          # committed tiny smoke-test sample
    local/           # ignored generated one-month subset
  compose/
  configs/
  docker/
  scripts/
  src/
    api/
    common/
    jobs/
    producers/
    airflow/
    tests/
  volumes/
```

## Resource Budget

- Start only the core profile by default.
- Keep Airflow off unless validating DAGs.
- Keep monitoring off unless validating observability.
- Kafka heap is capped to 512 MiB and retention is short for local replay.
- Spark worker memory is capped for this 4 vCPU / 15 GiB VM.
- Do not run multi-month backfills during smoke testing.

## Startup

1. Copy `.env.example` to `.env` if you need to regenerate local defaults.
2. Start core services:

```bash
make up
make ps
```

3. Initialize Kafka topics and run smoke checks:

```bash
make init-topics
make smoke
```

## Batch Path

Smoke-test sample:

```bash
make ingest-sample
make build-silver
make build-gold
```

Larger local subset:

```bash
make prepare-local-data
docker compose --profile dev run --rm devbox python -m src.jobs.ingest_batch --input data/local/aviation_events_2024-01.csv
make build-silver
make build-gold
```

## Training And Serving

```bash
make train
make serve
```

Prediction example:

```bash
curl -s http://127.0.0.1:3001/predict \
  -H 'Content-Type: application/json' \
  -d @configs/sample_request.json
```

## Replay And Streaming

Start the scoring job in one terminal:

```bash
docker compose --profile dev run --rm devbox python -m src.jobs.stream_score
```

Replay events in another:

```bash
make replay
```

## Monitoring

```bash
make monitoring
```

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

## Airflow

Only start Airflow after the manual pipeline is healthy:

```bash
make airflow
```

- Airflow UI: `http://127.0.0.1:8088`

## Smoke Tests

```bash
docker compose config
make up
make init-topics
make smoke
make ingest-sample
make build-silver
make build-gold
make train
```

## Reset Paths

- `make reset-kafka`: clears Kafka state and topics for replay/debugging.
- `make reset-data`: removes generated local data, derived Delta outputs, checkpoints, and stable serving artifacts.
- `make reset-all`: stops the stack and removes all local dev state in `volumes/` plus generated outputs.

## Common Failure Modes

- Spark cannot write Delta to MinIO: check custom Spark image dependency alignment and S3A settings.
- MLflow cannot log artifacts: verify `mlflow` bucket exists and `MLFLOW_S3_ENDPOINT_URL` points to MinIO.
- Bento cannot serve: run `make train` first so `s3://mlflow/serving/current/` exists.
- Kafka replay appears idle: verify `weather.replay` exists and the streaming job is connected to `kafka:9092`.

## Clean Shutdown

```bash
make down
```

## Later Migration Path

- Move MinIO-backed Delta storage to cloud object storage.
- Replace local Kafka with managed messaging only after message schemas stabilize.
- Move Spark jobs and Airflow orchestration to GKE after interfaces are stable.
- Replace local serving and analytics sinks with managed equivalents such as BigQuery only after the bronze/silver/gold contracts settle.
