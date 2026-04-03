# Aviation Disruption Intelligence MVP

Single-VM aviation disruption intelligence MVP built for fast local development on Debian 12 with Docker Compose only. The platform demonstrates an end-to-end path across Kafka, MinIO, Delta Lake, Spark, MLflow, BentoML, Prometheus, Grafana, and Airflow without managed cloud services in the runtime path.

## What This Project Demonstrates

- Historical batch ingestion into MinIO-backed Delta bronze, silver, and gold tables.
- Replay-driven streaming through Kafka with a small airport subset.
- Baseline disruption-risk model training tracked in MLflow.
- Stable serving export at `s3://mlflow/serving/current/` for deterministic Bento serving.
- Local inference over HTTP through BentoML.
- Minimal orchestration with Airflow after the manual path is healthy.
- Basic observability with Prometheus and Grafana.

## Architecture

```text
Local sample files
  -> Spark ingest
  -> MinIO raw + Delta bronze
  -> Spark silver normalization
  -> Spark gold feature build
  -> MLflow training + serving export
  -> BentoML /predict

Replay file
  -> Kafka weather.replay
  -> Spark streaming score
  -> Kafka disruption.scores + Delta scored output
```

## Demo Pack

- 2-minute architecture explanation: [docs/demo_pack.md](/home/guggella-chaitanya-reddy/big-data-project/docs/demo_pack.md)
- 5-minute live demo flow: [docs/demo_pack.md](/home/guggella-chaitanya-reddy/big-data-project/docs/demo_pack.md)
- One-page runbook: [docs/demo_runbook.md](/home/guggella-chaitanya-reddy/big-data-project/docs/demo_runbook.md)
- Replay-first fallback path: [docs/demo_runbook.md](/home/guggella-chaitanya-reddy/big-data-project/docs/demo_runbook.md)

## Project Tree

```text
big-data-project/
  data/
    sample/          # committed canonical smoke sample
    local/           # ignored generated one-month subset
  compose/           # service-specific config and init assets
  configs/           # request payloads and dashboard assets
  docker/            # custom Docker images
  docs/              # demo notes and runbook
  scripts/           # helper scripts and reset paths
  src/
    airflow/
    api/
    common/
    jobs/
    producers/
    tests/
  volumes/           # local bind-mounted service state
```

## Data Scope

- Airport subset: `ATL`, `JFK`, `ORD`, `DFW`, `DEN`
- Validation path: one-month local subset, generated outside Git
- Committed smoke sample: `data/sample/aviation_events_smoke.csv`
- Local generated subset: `data/local/aviation_events_2024-01.csv`

## What Is Mocked Vs Real

- Real local infrastructure: Kafka, MinIO, Delta Lake, Spark, MLflow, BentoML, Prometheus, Grafana, Airflow
- Synthetic data: the committed smoke sample and the generated one-month subset use synthetic aviation-weather records shaped to the real contracts
- Replay mode: real Kafka replay over synthetic sample events
- Model training: real local training run, artifact logging, and serving export

## Startup

1. Create local env values if needed:

```bash
cp .env.example .env
```

2. Start the core stack:

```bash
make up
make ps
```

3. Initialize topics and verify the stack:

```bash
make init-topics
make smoke
```

## Exact Smoke Test Commands

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

If you also want orchestration and monitoring validation:

```bash
make monitoring
make airflow
docker compose exec airflow-webserver airflow dags test aviation_disruption_mvp 2026-04-03
```

## Manual Pipeline

Batch path:

```bash
make ingest-sample
make build-silver
make build-gold
make train
```

Inference path:

```bash
make serve
curl -s http://127.0.0.1:3001/health -H 'Content-Type: application/json' -d '{}'
curl -s http://127.0.0.1:3001/predict \
  -H 'Content-Type: application/json' \
  -d @configs/sample_request.json
```

Replay and streaming:

```bash
docker compose exec -T -e PYTHONPATH=/workspace spark-master spark-submit /workspace/src/jobs/stream_score.py
make replay
```

Monitoring:

```bash
make monitoring
```

Airflow:

```bash
make airflow
docker compose exec airflow-webserver airflow dags test aviation_disruption_mvp 2026-04-03
```

## Resource-Saving Notes

- Run only the core stack by default: `postgres`, `minio`, `minio-init`, `kafka`, `spark-master`, `spark-worker`, `mlflow`
- Start `monitoring` only when you are demoing dashboards
- Start `airflow` only when you are validating DAGs
- Kafka retention is intentionally short for local replay development
- Spark worker memory is capped for a 4 vCPU / 15 GiB VM
- Do not keep multi-month local subsets under `data/local/` unless you actively need them
- Reset derived state with the provided `reset-*` targets instead of deleting random folders

## Common Failure Modes

- Kafka is restarting with a writable-path error:
  Fix ownership under `volumes/kafka` or run `make reset-kafka`
- MLflow or Airflow cannot authenticate to Postgres:
  Verify `.env` credentials and recreate the local state with `make reset-all`
- Spark cannot write Delta tables to MinIO:
  Recreate the custom Spark containers and verify `make smoke`
- Bento cannot start:
  Run `make train` first so `s3://mlflow/serving/current/` exists
- Airflow tasks can see the DAG but fail to execute repo commands:
  Recreate Airflow services so the repo is mounted at the real host path

## Sample Data Notes

- `data/sample/aviation_events_smoke.csv` is intentionally tiny and committed for deterministic smoke tests
- `data/local/` is ignored in Git and meant for larger local subsets only
- Downstream jobs read from MinIO, not from local files directly
- Local source files are kept on disk to make resets and re-ingest easy during demos

## Reset Paths

- `make reset-kafka`
  Clears Kafka dev state for replay debugging
- `make reset-data`
  Clears generated local data, checkpoints, Delta outputs, and derived model-serving artifacts
- `make reset-all`
  Stops the stack and clears local service state for a full rebuild

## Current Limitations

- Single VM only
- Airflow is configured for local development convenience, not production hardening
- Streaming is replay-first, not fed by a live external source
- The dataset is intentionally small and synthetic for deterministic evaluation
- No GKE or BigQuery integration yet

## Later Migration Path

- Export gold outputs to BigQuery first, keeping the contracts stable
- Add cloud SQL-style analytics and validation queries after the export path is solid
- Move orchestration and Spark execution to GKE only after the local interfaces settle
- Replace local object storage and serving components with managed equivalents only after the MVP contracts are stable

## Clean Shutdown

```bash
make down
```
