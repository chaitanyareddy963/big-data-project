# Original-Data Demonstration Track

The original PR1 and PR2 notebook filenames are retained so the presentation
order remains familiar. Their content now demonstrates the real datasets and
the corrected modeling path.

## Raw MinIO Layout

```text
raw/arco_era5_us_airport_hourly/
raw/bts_on_time/raw_zip/
raw/metadata/
raw/kafka_weather_events_original/
```

Verified source datasets:

- ARCO-ERA5 weather: 2015-2024, 720 Parquet files, 120 monthly partitions.
- BTS Reporting Carrier On-Time Performance: 2015-2024, 120 monthly ZIP files.

## First Proof Scope

January 2024 is the verified first proof:

```text
Original weather: 18,693,744 rows
Bronze BTS flights: 547,271 rows
Silver matched flights: 543,121 rows
Gold training features: 543,121 rows
```

## Presentation Design

- Phase 1 notebooks show original-data inventory and a bounded Kafka replay.
- Phase 2 notebooks show Spark S3A reads, transformations, schemas, previews,
  validations, charts, MLlib diagnostics, and MLflow logging.
- Reusable production Spark code remains in `spark_jobs/` because `.py` batch
  jobs are mandatory in the project rubric.
- The old 72-row JFK fixture is not used as final-model evidence.
- The old generated weather-rule label is replaced by actual BTS outcomes.

## Final Platform Status

- Delta Lake conversion is implemented in `spark_jobs/build_delta_lakehouse.py`.
- Spark Structured Streaming writes Kafka events to Delta in
  `spark_jobs/stream_kafka_weather_to_delta.py`.
- Airflow orchestration is implemented in `dags/aviation_lakehouse_dag.py`.
- The selected Spark MLlib model uses class weighting and chronological
  validation in `ml/train_register_model.py`.
- MLflow logs the selected model artifact and registers staging/production
  aliases.
- BentoML serving, Grafana monitoring, tests, load testing, and the final
  runbook are present.
- The larger final proof can run the same monthly jobs for a full selected year
  through `spark_jobs/run_year_pipeline.py`.
