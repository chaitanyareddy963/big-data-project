from __future__ import annotations

import os
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_DIR = os.environ.get(
    "HOST_PROJECT_DIR", "/home/guggella-chaitanya-reddy/big-data-project"
)


with DAG(
    dag_id="aviation_disruption_mvp",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:
    ingest = BashOperator(
        task_id="ingest_sample",
        bash_command=f"cd {PROJECT_DIR} && make ingest-sample",
    )

    silver = BashOperator(
        task_id="build_silver",
        bash_command=f"cd {PROJECT_DIR} && make build-silver",
    )

    gold = BashOperator(
        task_id="build_gold",
        bash_command=f"cd {PROJECT_DIR} && make build-gold",
    )

    train = BashOperator(
        task_id="train_model",
        bash_command=f"cd {PROJECT_DIR} && make train",
    )

    replay = BashOperator(
        task_id="replay_sample",
        bash_command=f"cd {PROJECT_DIR} && make replay",
    )

    ingest >> silver >> gold >> train >> replay
