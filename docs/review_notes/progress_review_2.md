# Progress Review 2 — Spark Processing + ML Training

## Scope

This review demonstrates Spark processing and ML training on aviation weather lakehouse data.

## Flow

MinIO raw Kafka events → Spark DataFrame → Bronze table → Silver labels → Gold training features → Spark MLlib model → MLflow runs.

## Services

- JupyterLab
- MinIO
- Apache Spark master
- Apache Spark worker
- MLflow

## Notebooks

1. `notebooks/pr2/05_spark_smoke_test.ipynb`
2. `notebooks/pr2/06_spark_read_minio_raw.ipynb`
3. `notebooks/pr2/07_create_bronze_weather_table.ipynb`
4. `notebooks/pr2/08_create_labels.ipynb`
5. `notebooks/pr2/09_feature_engineering.ipynb`
6. `notebooks/pr2/10_train_spark_mllib_model.ipynb`
7. `notebooks/pr2/11_mlflow_experiments.ipynb`

## Evidence

- Spark connects to the Spark master and worker.
- Spark reads Kafka-streamed weather data from MinIO.
- Bronze, Silver, and Gold lakehouse tables are created.
- A Spark MLlib Random Forest model is trained.
- The model is saved to `/spark-models/pr2_random_forest_model`.
- MLflow records experiment runs under `aviation_disruption_pr2`.
- Screenshots are saved under `docs/screenshots/progress_review_2/`.

## Notes

The PR2 dataset is intentionally small because the goal is to demonstrate pipeline correctness. The full dataset scaling will be done after PR2.