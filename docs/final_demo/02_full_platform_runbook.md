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

Run the required 10x stability demonstration:

```bash
python3 api/load_test.py --requests 100 --concurrency 10
```

Open Grafana at <http://localhost:3001> and show:

1. Prediction requests per second.
2. Prediction latency p95.
3. Predictions by risk band.

## Airflow

Open Airflow at <http://localhost:8088>. Show the scheduled
`aviation_original_data_lakehouse` DAG and its Spark, Delta, and MLflow tasks.

## Verification

```bash
docker compose exec jupyter bash -lc 'cd /workspace && pytest -q'
docker compose ps
```
