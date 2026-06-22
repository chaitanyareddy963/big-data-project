# Final Dataset Streaming Demo Runbook

For a fresh clone or new VM, restore raw datasets first using
`docs/setup_dataset.md`. The final notebooks assume MinIO already contains
ARCO-ERA5, BTS ZIP archives, and metadata under the expected `raw/` paths.

## Start Services

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
docker compose up -d airflow aviation-api prometheus grafana llm-chat
```

## Build Delta Lake Tables

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.build_delta_lakehouse --year 2024 --month 1'
```

For the larger one-year proof:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.run_year_pipeline --year 2024 --with-delta --with-final-model'
```

## Train and Register Final Model

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m ml.train_register_model --year 2024'
```

Open MLflow at <http://localhost:5000> and show the registered
`aviation-disruption-balanced-logistic` model. Do not rebuild MLflow evidence
inside Grafana; use the MLflow UI directly.

Show:

- registered model
- AUC
- positive precision
- positive recall
- confusion metrics
- model artifact
- staging/production alias

## Start API and Dashboards

```bash
docker compose up -d aviation-api prometheus grafana kafka kafka-ui
```

Call the BentoML API:

```bash
curl -X POST http://localhost:3000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "features": {
      "scheduled_departure_hour_local": 16.0,
      "distance_miles": 1090.0,
      "day_of_week": 2.0,
      "day_of_month": 15.0,
      "temperature_c_avg": 5.5,
      "wind_speed_kts_max": 24.0,
      "wind_gust_kts_max": 31.0,
      "precipitation_mm_sum": 6.0,
      "surface_pressure_pa_avg": 100900.0,
      "total_cloud_cover_avg": 0.75,
      "cape_j_kg_max": 80.0
    }
  }'
```

Call the API with a historical Gold-table row from the downloaded lakehouse:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.call_api_with_gold_sample --year 2024 --month 1 --api-url http://aviation-api:3000/predict'
```

## Dataset Streaming Replay

This replay demonstrates the dataset-only streaming simulation. The script
reads historical Gold feature rows from the downloaded lakehouse, publishes
each replay event to Kafka topic `simulation.prediction.requests` for streaming
evidence, separately calls the deployed BentoML API for scoring, and writes
JSONL evidence for review. The API does not consume from Kafka in this demo.

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.simulate_gold_stream_predict --year 2024 --month 1 --limit 100 --delay-seconds 0.1 --output-jsonl data/local_cache/streaming_predictions/gold_simulation.jsonl --api-url http://aviation-api:3000/predict'
```

For a slower visual demo:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.simulate_gold_stream_predict --year 2024 --month 1 --limit 25 --delay-seconds 1 --output-jsonl data/local_cache/streaming_predictions/gold_simulation_slow.jsonl --api-url http://aviation-api:3000/predict'
```

Open Kafka UI at <http://localhost:8085> and show topic
`simulation.prediction.requests`. Open Grafana and show dashboard
`Aviation Final Demo Dashboard`.

On `Aviation Final Demo Dashboard`, show:

- simulated records scored
- stream rate
- latest probability
- risk-band split
- API latency during simulation
- all prediction sources
- active dataset replay alerts
- dataset replay alert states

Prometheus also exposes the same replay alerts at <http://localhost:9090/alerts>.
The alert rules are intentionally scoped to the simulated dataset replay, not
the entire platform:

- `AviationDatasetReplayInactive`
- `AviationDatasetReplayHighLatency`
- `AviationDatasetReplayAPIFailures`
- `AviationHighRiskBandShare`

## LLM Operations Assistant

The optional LLM layer uses Google Gemini generateContent API with Gemini 3.5 Flash. It answers questions from the codebase/docs/notebooks, dataset
replay evidence, Prometheus metrics, MLflow, Airflow, Kafka, MinIO, Spark, Grafana dashboard JSON, and bounded Docker service log tails.

Configure `.env`:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
```

Run:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.llm_ops_assistant --prometheus-url http://prometheus:9090 --question "Explain what is happening in this aviation dataset streaming demo right now."'
```

Start the browser chatbot:

```bash
docker compose up -d llm-chat
```

Open <http://localhost:7860> and ask:

- `Summarize what is happening right now.`
- `How does the dataset streaming replay work?`
- `Which downloaded datasets are used by the model?`
- `What should I show in Grafana for final presentation?`
- `Which files implement the dataset replay and API scoring path?`
- `What is the current status of MLflow, Kafka, MinIO, Spark, and Grafana?`
- `Are there recent warnings or errors in the service logs?`

If `GEMINI_API_KEY` is missing, the assistant returns a local fallback summary
instead of failing.

The assistant indexes source code, docs, notebooks, and dashboard JSON with
bounded file excerpts. It excludes local secrets, raw datasets, generated
lakehouse data, and model binaries. Runtime service state is queried directly from the corresponding service APIs when those services are reachable. Recent service logs are read from the local Docker socket for the project container allow-list and redacted before being sent to the assistant.

## 10x Stability Demonstration

```bash
python3 api/load_test.py --requests 100 --concurrency 10
```

Open Grafana at <http://localhost:3001> and show dashboard
`Aviation Final Demo Dashboard`:

- total prediction requests
- request rate
- failed requests, if any
- latency p50/p95
- risk-band requests
- probability trend
- probability distribution
- active dataset replay alerts
- dataset replay alert states

## Service UIs

Use these as service dashboards, not custom Grafana dashboards:

| UI | URL | Show |
|---|---|---|
| Airflow | http://localhost:8088 | `aviation_original_data_lakehouse` DAG graph and run status |
| Spark Master | http://localhost:8080 | Spark applications, jobs, and stages |
| Spark Worker | http://localhost:8081 | worker resources and executor activity |
| MLflow | http://localhost:5000 | model registry, metrics, artifacts, aliases |
| Kafka UI | http://localhost:8085 | `simulation.prediction.requests` topic messages |

## Verification

```bash
docker compose exec jupyter bash -lc 'cd /workspace && pytest -q'
docker compose ps
```
