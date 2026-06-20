# Phase 1 Demo: Original Data Ingestion and Storage

## Scope

This revised presentation demonstrates:

```text
Original ARCO-ERA5 MinIO partition
  -> Spark-selected representative replay slice
  -> Kafka topic weather.raw
  -> Kafka consumer
  -> MinIO raw/kafka_weather_events_original/
  -> validation notebook
```

The old 72-row JFK review fixture is no longer the presentation source.

## Notebook Order

1. `notebooks/pr1/00_environment_smoke_test.ipynb`
2. `notebooks/pr1/01_download_era5_sample_to_minio.ipynb`
3. `notebooks/pr1/02_kafka_to_minio_consumer.ipynb`
4. `notebooks/pr1/03_kafka_replay_producer.ipynb`
5. `notebooks/pr1/04_validate_streamed_storage.ipynb`

## Evidence

- MinIO contains the original 2015-2024 ARCO-ERA5 dataset.
- Kafka replay records are selected from an original monthly Parquet partition.
- The consumer stores replay JSONL micro-batches in MinIO.
- The validation notebook reports row count, airport count, timestamp range,
  and stored object count for the latest replay.
