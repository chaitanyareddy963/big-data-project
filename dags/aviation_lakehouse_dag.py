"""Scheduled January proof pipeline executed inside the Jupyter Spark driver container."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


def jupyter_job(module: str, arguments: str = "--year 2024 --month 1") -> str:
    return f"docker exec aviation-jupyter bash -lc 'cd /workspace && python -m {module} {arguments}'"


with DAG(
    dag_id="aviation_original_data_lakehouse",
    description="Build January aviation lakehouse tables and register the final model",
    start_date=datetime(2026, 5, 31),
    schedule="@weekly",
    catchup=False,
    tags=["aviation", "spark", "minio", "mlflow"],
) as dag:
    validate_weather = BashOperator(
        task_id="validate_original_weather",
        bash_command=jupyter_job("spark_jobs.validate_raw_weather"),
    )
    build_weather = BashOperator(
        task_id="build_bronze_weather",
        bash_command=jupyter_job("spark_jobs.build_bronze_weather"),
    )
    build_bts = BashOperator(
        task_id="build_bronze_bts",
        bash_command=jupyter_job("spark_jobs.build_bronze_bts"),
    )
    build_silver = BashOperator(
        task_id="build_silver",
        bash_command=jupyter_job("spark_jobs.build_silver_flight_weather"),
    )
    build_gold = BashOperator(
        task_id="build_gold",
        bash_command=jupyter_job("spark_jobs.build_gold_features"),
    )
    build_delta = BashOperator(
        task_id="build_delta_tables",
        bash_command=jupyter_job("spark_jobs.build_delta_lakehouse"),
    )
    register_model = BashOperator(
        task_id="train_and_register_model",
        bash_command=jupyter_job("ml.train_register_model", ""),
    )

    validate_weather >> build_weather >> build_bts >> build_silver >> build_gold >> build_delta
    build_gold >> register_model
