# Real-Time Aviation Weather Disruption Intelligence Platform

Z5008 Big Data Lab course project.

## Project Overview

This project builds a real-time aviation weather disruption intelligence platform.

The system uses historical ARCO-ERA5 weather data, replays it as a Kafka stream, stores the streamed data in MinIO, processes it with Spark, trains a Spark MLlib model, and tracks experiments using MLflow.

The final project goal is to build an end-to-end Big Data + MLOps platform for airport-level disruption risk scoring.

---

## Current Status

### Progress Review 1 — Complete

Progress Review 1 demonstrates the ingestion and storage layer.

Working flow:

```text
ARCO-ERA5 weather sample
    ↓
JupyterLab download notebook
    ↓
MinIO raw bucket
    ↓
Kafka replay producer notebook
    ↓
Kafka topic weather.raw
    ↓
Kafka consumer notebook
    ↓
MinIO raw/kafka_weather_events/
    ↓
Validation notebook

Evidence is available in:

docs/screenshots/progress_review_1/
docs/review_notes/progress_review_1.md

Progress Review 2 — Complete

Progress Review 2 demonstrates Spark processing and ML training.

Working flow:

MinIO raw Kafka events
    ↓
Spark processing
    ↓
Bronze weather table
    ↓
Silver labeled table
    ↓
Gold training features
    ↓
Spark MLlib Random Forest model
    ↓
MLflow experiment tracking

Evidence is available in:

docs/screenshots/progress_review_2/
docs/review_notes/progress_review_2.md
Services

The project currently runs the following services through Docker Compose:

Service	Purpose	URL
JupyterLab	Main development and notebook execution environment	http://localhost:8888

MinIO	S3-compatible object storage / lakehouse storage	http://localhost:9001

Kafka	Real-time streaming ingestion	Internal: kafka:9092
Kafka UI	Kafka topic inspection	http://localhost:8085

Spark Master	Spark cluster manager	http://localhost:8080

Spark Worker	Spark execution worker	http://localhost:8081

MLflow	Experiment tracking	http://localhost:5000
Start Services
docker compose up -d minio mc kafka kafka-ui jupyter spark-master spark-worker mlflow

Check running containers:

docker compose ps

Open:

JupyterLab: http://localhost:8888
MinIO:      http://localhost:9001
Kafka UI:  http://localhost:8085
Spark UI:  http://localhost:8080
MLflow:    http://localhost:5000
Environment

The project uses environment variables from .env.

A sample file is provided:

.env.example

Do not commit the real .env file.

Progress Review 1 Notebooks

Run in this order:

notebooks/pr1/00_environment_smoke_test.ipynb
notebooks/pr1/01_download_era5_sample_to_minio.ipynb
notebooks/pr1/02_kafka_to_minio_consumer.ipynb
notebooks/pr1/03_kafka_replay_producer.ipynb
notebooks/pr1/04_validate_streamed_storage.ipynb
PR1 Demo Flow
ERA5 sample download
    ↓
Save sample to MinIO raw bucket
    ↓
Replay sample rows into Kafka
    ↓
Consume Kafka events
    ↓
Write streamed events to MinIO
    ↓
Validate stored rows
Progress Review 2 Notebooks

Run in this order:

notebooks/pr2/05_spark_smoke_test.ipynb
notebooks/pr2/06_spark_read_minio_raw.ipynb
notebooks/pr2/07_create_bronze_weather_table.ipynb
notebooks/pr2/08_create_labels.ipynb
notebooks/pr2/09_feature_engineering.ipynb
notebooks/pr2/10_train_spark_mllib_model.ipynb
notebooks/pr2/11_mlflow_experiments.ipynb
PR2 Demo Flow
Spark reads raw Kafka-streamed events from MinIO
    ↓
Bronze weather table is created
    ↓
Silver labeled table is created
    ↓
Gold training features are created
    ↓
Spark MLlib Random Forest model is trained
    ↓
MLflow logs experiment runs and metrics
Lakehouse Layout

MinIO buckets:

raw
lakehouse
warehouse
mlflow

Current lakehouse paths:

raw/era5_sample/
raw/kafka_weather_events/

lakehouse/bronze/weather_events_parquet/
lakehouse/bronze/weather_events_delta/

lakehouse/silver/weather_labeled_parquet/
lakehouse/silver/weather_labeled_delta/

lakehouse/gold/training_features_parquet/
lakehouse/gold/training_features_delta/
Model Artifact

The Spark MLlib model is saved inside a Docker named volume mounted at:

/spark-models/pr2_random_forest_model

MLflow Experiment

Experiment name:

aviation_disruption_pr2

The experiment contains multiple runs comparing:

Random Forest with different tree/depth settings
Logistic Regression baseline

Metrics logged:

accuracy
f1
auc
Current Dataset Scope

For Progress Reviews 1 and 2, the project uses a small ARCO-ERA5 sample:

Airport: JFK
Date range: 2022-01-01 to 2022-01-03
Frequency: hourly
Rows: 72

This small dataset is intentional for progress-review stability. The dataset will be expanded after Progress Review 2.

Next Planned Work

After Progress Review 2:

1. Expand dataset to more airports and longer time range.
2. Convert important notebook logic into production .py Spark jobs.
3. Add Spark Structured Streaming scoring.
4. Add Airflow orchestration.
5. Add BentoML REST API serving.
6. Add Prometheus + Grafana monitoring.
7. Prepare final live demo flow.
Repository Structure
aviation-weather-disruption/
  docker-compose.yml
  README.md
  .env.example
  docker/
    jupyter.Dockerfile
  configs/
    progress_review_1.yaml
  notebooks/
    pr1/
    pr2/
  docs/
    review_notes/
    screenshots/
  data/
    sample/
  spark_jobs/
  ml/
  models/