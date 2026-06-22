# Notebook Demo Flow

The notebooks are the presentation layer. They intentionally show the
important transformations, checks, schemas, previews, and conclusions cell by
cell. Reusable production Spark implementations remain in `spark_jobs/` because
the course rubric requires production `.py` jobs in addition to notebooks.

## Phase 1: Original Data Ingestion and Storage

Run:

1. `pr1/00_environment_smoke_test.ipynb`
2. `pr1/01_download_era5_sample_to_minio.ipynb`
3. `pr1/02_kafka_to_minio_consumer.ipynb`
4. `pr1/03_kafka_replay_producer.ipynb`
5. `pr1/04_validate_streamed_storage.ipynb`

The producer replays a bounded representative slice from the original ARCO-ERA5
monthly partition stored in MinIO. It no longer depends on the old 72-row JFK
fixture.

## Phase 2: Spark Lakehouse and ML Diagnostics

Run:

1. `pr2/01_spark_smoke_test.ipynb`
2. `pr2/02_spark_read_minio_raw.ipynb`
3. `pr2/03_create_bronze_weather_table.ipynb`
4. `pr2/04_create_labels.ipynb`
5. `pr2/05_feature_engineering.ipynb`
6. `pr2/06_train_spark_mllib_model.ipynb`
7. `pr2/07_mlflow_experiments.ipynb`

Phase 2 reads the original January 2024 weather and BTS data through Spark S3A,
shows the Bronze, Silver, and Gold transformations, and presents MLlib baseline
diagnostics using actual BTS cancellation and delay outcomes.

## Final Platform Layers

After PR1 and PR2, run:

1. `final/08_full_platform_demo.ipynb`
2. `final/09_one_year_historical_data_pipeline.ipynb`
3. `final/10_dataset_streaming_demo.ipynb`

These notebooks present Delta Lake, Structured Streaming, Airflow, MLflow
registry, BentoML API serving, Prometheus, Grafana, tests, load testing, the
one-year production runner, API prediction from a historical Gold feature row from the downloaded lakehouse, and
dataset streaming replay through Kafka.
