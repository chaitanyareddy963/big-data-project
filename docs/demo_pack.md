# Demo Pack

## 2-Minute Architecture Explanation

This project is a single-VM aviation disruption intelligence MVP built for correctness and developer speed rather than scale. Local source files are the starting point for a small five-airport subset. Spark ingests those files into MinIO, which acts as S3-compatible object storage. The data is organized as Delta Lake bronze, silver, and gold tables so we can show raw landing, cleaned normalization, and model-ready features with versioned table history.

Kafka is used for replay and streaming, not as the source of truth. A replay producer publishes historical events into `weather.replay`, and Spark Structured Streaming scores those events and writes outputs to `disruption.scores` and a Delta sink. Model training is tracked in MLflow with Postgres as the backend store and MinIO for artifacts. After training, one inference-ready artifact is exported to the stable path `s3://mlflow/serving/current/`, which keeps Bento serving deterministic. Airflow is intentionally minimal and only orchestrates the already-working manual steps. Prometheus and Grafana are there to prove observability on the local stack.

## 5-Minute Live Demo Flow

1. Show the architecture diagram in the README and explain bronze, silver, gold, replay, MLflow, Bento, and Airflow at a high level.
2. Show `docker compose ps` or `make ps` to prove the local stack is up on one VM.
3. Show that bronze, silver, and gold are already built by opening MinIO and optionally referencing the Spark jobs that created them.
4. Open MLflow and show the baseline training run plus the stable serving artifact convention at `s3://mlflow/serving/current/`.
5. Start or show the Bento service and hit `/health`, then `/predict` with `configs/sample_request.json`.
6. Run `make replay` and explain that Kafka is being used for deterministic historical replay rather than live ingestion.
7. Show the Airflow DAG run success for `aviation_disruption_mvp`.
8. End on Prometheus and Grafana to show service-level observability.

## Best Demo Order

1. Architecture
2. Stack up
3. Replay path
4. Bronze, silver, gold
5. MLflow model
6. Bento `/predict`
7. Airflow DAG success
8. Grafana and Prometheus

## Failure Fallback

If a UI is slow or a live step gets stuck, switch to the replay-first fallback:

1. Show that the core services are healthy with `make smoke`
2. Show the existing successful Airflow DAG run
3. Show the MLflow run and stable serving export
4. Hit Bento `/health` and `/predict`
5. Run `make replay` and show Kafka topics plus Delta outputs already present

This keeps the demo deterministic and still proves the end-to-end path.
