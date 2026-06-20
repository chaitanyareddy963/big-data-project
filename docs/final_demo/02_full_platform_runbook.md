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
`aviation-disruption-balanced-logistic` model.

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

Call the API with a real Gold-table row:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.call_api_with_gold_sample --year 2024 --month 1 --api-url http://aviation-api:3000/predict'
```

## Dataset Streaming Replay

This replay demonstrates that real Gold feature rows from the downloaded
lakehouse can be streamed into the deployed prediction path. The script reads
Gold feature rows, publishes each event to Kafka topic
`simulation.prediction.requests`, calls the deployed API, and writes JSONL
evidence.

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
`Aviation Dataset Simulation Stream`.

## LLM Operations Assistant

The optional LLM layer uses Groq's OpenAI-compatible chat completions API with
Llama 3.3 70B. It answers questions from the dataset replay evidence and
Prometheus metrics.

Configure `.env`:

```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
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

If `GROQ_API_KEY` is missing, the assistant returns a local fallback summary
instead of failing.

## 10x Stability Demonstration

```bash
python3 api/load_test.py --requests 100 --concurrency 10
```

Open Grafana at <http://localhost:3001> and show:

1. Total prediction requests and current requests per second.
2. Failed API requests, if any.
3. Prediction latency p50 and p95.
4. Risk-band split across low and high predictions.
5. Dataset streaming replay rate and simulated risk-band split.

## Airflow

Open Airflow at <http://localhost:8088>. Show the scheduled
`aviation_original_data_lakehouse` DAG and its Spark, Delta, and MLflow tasks.

## Verification

```bash
docker compose exec jupyter bash -lc 'cd /workspace && pytest -q'
docker compose ps
```
