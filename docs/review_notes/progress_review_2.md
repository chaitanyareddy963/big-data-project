# Phase 2 Demo: Spark Lakehouse and ML Diagnostics

## Scope

This revised presentation demonstrates:

```text
Original ARCO-ERA5 weather + official BTS flights in MinIO
  -> Spark S3A direct reads
  -> Bronze weather and BTS flight tables
  -> Silver flight-weather join with real BTS outcomes
  -> Gold leakage-conscious features
  -> Spark MLlib diagnostic runs
  -> MLflow comparison
```

## Notebook Order

1. `notebooks/pr2/01_spark_smoke_test.ipynb`
2. `notebooks/pr2/02_spark_read_minio_raw.ipynb`
3. `notebooks/pr2/03_create_bronze_weather_table.ipynb`
4. `notebooks/pr2/04_create_labels.ipynb`
5. `notebooks/pr2/05_feature_engineering.ipynb`
6. `notebooks/pr2/06_train_spark_mllib_model.ipynb`
7. `notebooks/pr2/07_mlflow_experiments.ipynb`

## Verified January 2024 Evidence

- Original weather rows: 18,693,744.
- Official BTS flight rows: 547,271.
- Flights matched to weather: 543,121.
- Non-disrupted flights: 397,465.
- Disrupted flights: 145,656.
- Labels come from BTS cancellations or arrival delays of at least 15 minutes.
- Outcome columns are excluded from Gold model features.

## Notes

The initial diagnostic uses a random split. Before final model selection, add
class-imbalance handling, threshold tuning, and chronological validation.
