# Final Live Demo Runbook

## Start Services

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
docker compose up -d airflow
```

## Build Delta Lake Tables

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.build_delta_lakehouse --year 2024 --month 1'
```

## Demonstrate Structured Streaming

Run the PR1 Kafka replay notebooks, then:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.stream_kafka_weather_to_delta --trigger-once'
```

## Train and Register Final Model

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m ml.train_register_model'
```

For the larger one-year proof, run the monthly jobs for all 2024 months and
then register the final full-year model:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.run_year_pipeline --year 2024 --with-delta --with-final-model'
```

Open MLflow at <http://localhost:5000> and show the registered
`aviation-disruption-balanced-logistic` model with its `staging` and
`production` aliases.

## Start API and Dashboards

```bash
docker compose up -d aviation-api prometheus grafana
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

Live-weather inference, one snapshot:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.live_weather_predict --airport JFK --api-url http://aviation-api:3000/predict'
```

Continuous live-weather inference:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.live_weather_predict --airport JFK --watch --interval-seconds 30 --max-iterations 10 --output-jsonl data/local_cache/live_predictions/jfk.jsonl --api-url http://aviation-api:3000/predict'
```

Recommended live operational inference using AviationWeather.gov and
AeroDataBox:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.live_operational_predict --airport JFK --watch --interval-seconds 60 --max-iterations 10 --output-jsonl data/local_cache/live_predictions/jfk_operational.jsonl --api-url http://aviation-api:3000/predict'
```

Configure AeroDataBox in `.env` before running the operational demo:

```bash
AERODATABOX_MARKETPLACE=rapidapi
AERODATABOX_API_KEY=your_key_here
AERODATABOX_RAPIDAPI_HOST=aerodatabox.p.rapidapi.com
```

For API.Market, use:

```bash
AERODATABOX_MARKETPLACE=apimarket
AERODATABOX_API_KEY=your_key_here
```

If the key is missing, the command still fetches AviationWeather.gov METAR
weather and marks AeroDataBox operations as unavailable.

For an open-ended live run, remove `--max-iterations` and stop with `Ctrl+C`.

## Dataset Simulation Stream

This replay demonstrates that if live records arrive with the same feature
contract as the historical Gold training table, the platform can stream and
score them continuously. The script reads real Gold feature rows, publishes
each event to Kafka topic `simulation.prediction.requests`, calls the deployed
API, and writes JSONL evidence.

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.simulate_gold_stream_predict --year 2024 --month 1 --limit 100 --delay-seconds 0.1 --output-jsonl data/local_cache/live_predictions/gold_simulation.jsonl --api-url http://aviation-api:3000/predict'
```

For a slower visual demo:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.simulate_gold_stream_predict --year 2024 --month 1 --limit 25 --delay-seconds 1 --output-jsonl data/local_cache/live_predictions/gold_simulation_slow.jsonl --api-url http://aviation-api:3000/predict'
```

Open Kafka UI at <http://localhost:8085> and show topic
`simulation.prediction.requests`. Open Grafana and show dashboard
`Aviation Dataset Simulation Stream`.

## LLM Operations Assistant

The optional LLM layer uses Groq's OpenAI-compatible chat completions API with
Llama 3.3 70B. It answers questions from the latest JSONL live evidence and
Prometheus metrics.

Configure `.env`:

```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Run:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.llm_ops_assistant --prometheus-url http://prometheus:9090 --question "Explain what is happening in this aviation demo right now."'
```

If `GROQ_API_KEY` is missing, the assistant returns a local fallback summary
instead of failing.

Run the required 10x stability demonstration:

```bash
python3 api/load_test.py --requests 100 --concurrency 10
```

Open Grafana at <http://localhost:3001> and show:

1. Total prediction requests and current requests per second.
2. Failed API requests, if any.
3. Prediction latency p50 and p95.
4. Risk-band split across low and high predictions.
5. Latest disruption probability and probability trend/distribution.
6. Dataset simulation stream rate and simulated risk-band split.

## Airflow

Open Airflow at <http://localhost:8088>. Show the scheduled
`aviation_original_data_lakehouse` DAG and its Spark, Delta, and MLflow tasks.

## Verification

```bash
docker compose exec jupyter bash -lc 'cd /workspace && pytest -q'
docker compose ps
```
