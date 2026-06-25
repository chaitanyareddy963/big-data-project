# Aviation Weather Disruption Intelligence Platform

Z5008 Big Data Lab course project.

This repository builds an aviation disruption intelligence platform from
downloaded historical datasets: ARCO-ERA5 airport-hour weather and official BTS
Reporting Carrier On-Time Performance flight outcomes. The final demo trains
and serves a disruption model, then runs a historical test-set replay where
Gold feature rows from the downloaded lakehouse are published to Kafka for
streaming evidence and separately scored by the BentoML API.

## Start Here

For grading and final presentation, start with the **final demo track**:
[Final Runbook](docs/final_demo/02_full_platform_runbook.md),
[09_one_year_historical_data_pipeline.ipynb](notebooks/final/09_one_year_historical_data_pipeline.ipynb),
and [10_dataset_streaming_demo.ipynb](notebooks/final/10_dataset_streaming_demo.ipynb).
The PR1 and PR2 notebooks remain in the repository as progress-review evidence
and infrastructure proof: they show that MinIO, Kafka, Spark, lakehouse stages,
MLflow diagnostics, and earlier monthly pipeline pieces were configured and
validated. They are not the main final demo path.

| Need | Go to |
|---|---|
| Fresh clone, dataset download, BTS download, MinIO upload, lakehouse build | [Dataset Setup](docs/setup_dataset.md) |
| Customize or regenerate the ARCO-ERA5 Google Drive bundle | [ARCO ERA5 Colab Download Notebook](ARCO_ERA5_Dataset_Download_Script.ipynb) |
| Notebook order for PR1, PR2, and final demo | [Notebook Demo Flow](notebooks/README.md) |
| Final presentation commands and talking points | [Final Runbook](docs/final_demo/02_full_platform_runbook.md) |
| Original-data scope and phase alignment | [Original-Data Demonstration Track](docs/final_demo/01_original_data_bronze.md) |
| PR1 review notes | [Progress Review 1](docs/review_notes/progress_review_1.md) |
| PR2 review notes | [Progress Review 2](docs/review_notes/progress_review_2.md) |

## Project Flow

```text
ARCO-ERA5 + BTS raw data in MinIO
  -> Kafka replay and raw storage checks
  -> Spark Bronze/Silver/Gold lakehouse
  -> BTS-based disruption labels
  -> Spark MLlib model and MLflow registry
  -> BentoML prediction API
  -> historical test-set replay with Kafka evidence and API scoring
  -> Prometheus + Grafana dashboards
  -> Gemini 3.5 Flash project Q&A assistant
```

## Dataset

The large raw dataset is not stored in Git. Use the setup guide before running
PR2 or final notebooks.

Prepared Google Drive dataset bundle:

[Google Drive dataset folder](https://drive.google.com/drive/folders/1vqFcJ7uuofHbDHvY4VMAMO5mJolVmgiu?usp=sharing)

Approximate verified VM sizes:

| Data | Size |
|---|---:|
| Prepared ARCO-ERA5 + metadata bundle | ~44.5 GiB |
| Official BTS ZIP archives, 2015-2024 | ~3.0 GiB |
| Raw MinIO after restore | ~47 GiB |
| Generated 2024 lakehouse outputs | ~18 GiB |
| Recommended VM disk | 220 GiB |

Detailed commands are in [docs/setup_dataset.md](docs/setup_dataset.md).

The ARCO-ERA5 bundle was prepared with
[ARCO_ERA5_Dataset_Download_Script.ipynb](ARCO_ERA5_Dataset_Download_Script.ipynb).
Run this notebook in Google Colab when you want to regenerate the Drive dataset
or customize the airport scope, year range, month range, or output layout. No
API key is required for this ARCO-ERA5 download path; the notebook downloads
public ARCO-ERA5 data and writes the prepared bundle to Google Drive.

## Quick Start

```bash
git clone https://github.com/chaitanyareddy963/big-data-project.git
cd big-data-project
cp .env.example .env
```

Set MinIO, AWS/S3A, Jupyter, and optional Gemini values in `.env`. See
[Fresh Clone Dataset Setup](docs/setup_dataset.md#1-clone-and-configure) for
the full variable list.

Start core services:

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
```

Restore datasets with [Dataset Setup](docs/setup_dataset.md), then run the
presentation notebooks in the order listed in [notebooks/README.md](notebooks/README.md).

## Main Services

| Service | URL | Used for |
|---|---|---|
| JupyterLab | http://localhost:8888 | PR1, PR2, and final notebooks |
| MinIO | http://localhost:9001 | raw, lakehouse, warehouse, and artifact buckets |
| Kafka UI | http://localhost:8085 | replay topics and message evidence |
| Spark Master | http://localhost:8080 | Spark applications, jobs, and stages |
| Spark Worker | http://localhost:8081 | worker/executor activity |
| MLflow | http://localhost:5000 | experiments, metrics, artifacts, model registry |
| BentoML API | http://localhost:3000 | prediction endpoint |
| Airflow | http://localhost:8088 | DAG graph and orchestration evidence |
| Grafana | http://localhost:3001 | API and dataset replay metrics |
| LLM Chat UI | http://localhost:7860 | project/codebase/status Q&A assistant |

## Notebooks

Use [notebooks/README.md](notebooks/README.md) as the canonical notebook index.
For final grading, focus on the final notebooks. PR1/PR2 notebooks are kept as
reproducible proof that the earlier infrastructure and processing layers work.

| Stage | Notebook/document |
|---|---|
| PR1 ingestion smoke test | [00_environment_smoke_test.ipynb](notebooks/pr1/00_environment_smoke_test.ipynb) |
| PR1 raw data inventory | [01_download_era5_sample_to_minio.ipynb](notebooks/pr1/01_download_era5_sample_to_minio.ipynb) |
| PR1 Kafka consumer | [02_kafka_to_minio_consumer.ipynb](notebooks/pr1/02_kafka_to_minio_consumer.ipynb) |
| PR1 Kafka replay producer | [03_kafka_replay_producer.ipynb](notebooks/pr1/03_kafka_replay_producer.ipynb) |
| PR1 storage validation | [04_validate_streamed_storage.ipynb](notebooks/pr1/04_validate_streamed_storage.ipynb) |
| PR2 Spark/ML notebooks | [Notebook Demo Flow](notebooks/README.md#phase-2-spark-lakehouse-and-ml-diagnostics) |
| Final platform checklist | [08_full_platform_demo.ipynb](notebooks/final/08_full_platform_demo.ipynb) |
| One-year historical pipeline | [09_one_year_historical_data_pipeline.ipynb](notebooks/final/09_one_year_historical_data_pipeline.ipynb) |
| Main final demo | [10_dataset_streaming_demo.ipynb](notebooks/final/10_dataset_streaming_demo.ipynb) |

## Presentation Evidence

The final presentation should use Grafana only for API and replay metrics. Use
the native service UIs for MLflow, Airflow, Spark, and Kafka evidence. The full
sequence is in [Final Dataset Streaming Demo Runbook](docs/final_demo/02_full_platform_runbook.md).
Fresh screenshots for the final demo are stored in
[docs/screenshots/final_demo](docs/screenshots/final_demo).

| Evidence | Where to show it | Details |
|---|---|---|
| Final API + replay metrics | Grafana dashboard `Aviation Final Demo Dashboard` | total requests, dataset replay records, request rates, failures, p50/p95 latency, risk-band splits, probability trend, probability distribution |
| Dataset replay alerts | Grafana dashboard `Aviation Final Demo Dashboard` and Prometheus `/alerts` | replay inactivity, replay-window API failures, high replay scoring latency, high-risk replay share |
| Model metrics and registry | MLflow UI | registered model, AUC, positive precision/recall, confusion metrics, model artifact, staging/production alias |
| Orchestration | Airflow UI | `aviation_original_data_lakehouse` DAG graph and run status |
| Spark processing | Spark UI | applications, jobs, stages, worker activity |
| Replay messages | Kafka UI | `simulation.prediction.requests` topic messages |

Grafana dashboards are provisioned from:

- [Aviation Final Demo Dashboard](dashboards/aviation-final-demo-dashboard.json)

Prometheus dataset-replay alert rules are provisioned from:

- [prometheus_rules.yml](dashboards/prometheus_rules.yml)

## Production Code Map

| Area | Path |
|---|---|
| Spark jobs | [spark_jobs/](spark_jobs/) |
| Model training/registration | [ml/](ml/) |
| BentoML API, replay script, LLM assistant | [api/](api/) |
| Airflow DAG | [dags/](dags/) |
| Grafana/Prometheus provisioning | [dashboards/](dashboards/) |
| Tests | [tests/](tests/) |

Key implementation files:

- [run_year_pipeline.py](spark_jobs/run_year_pipeline.py): full-year monthly runner.
- [train_register_model.py](ml/train_register_model.py): selected model training and MLflow registration.
- [simulate_gold_stream_predict.py](api/simulate_gold_stream_predict.py): historical test-set replay, Kafka evidence publishing, API scoring, JSONL output.
- [service.py](api/service.py): BentoML prediction service.
- [llm_ops_assistant.py](api/llm_ops_assistant.py): optional Gemini-backed project Q&A assistant.

## LLM Chat Scope

The LLM chat UI is intended to answer project-specific questions, not generic
aviation questions. It builds context from:

- source code, README/docs, dashboard JSON, Compose config, and notebooks
- latest dataset replay JSONL evidence
- Prometheus prediction metrics
- MLflow experiments, runs, registered models, metrics, and artifacts exposed by MLflow REST
- Airflow DAG status exposed by Airflow REST
- Kafka topic list and sample `simulation.prediction.requests` messages
- MinIO bucket/object samples
- Spark applications/jobs exposed by the Spark UI REST endpoints
- bounded Docker service log tails for known project containers

For prompt safety and cost, the assistant sends a bounded codebase index plus
selected file excerpts rather than every byte of every file. It excludes local
secrets, raw datasets, generated lakehouse data, and model binaries.

## Notes For New Users

- `.env`, raw data, MinIO volumes, generated lakehouse outputs, model files, and
  local streaming evidence are intentionally not committed.
- Restore raw data before running PR2/final notebooks.
- The final verified large-data proof uses all 2024 months.
- The final dataset-only simulation publishes historical Gold rows to Kafka for
  replay evidence and separately calls the API for scoring.

## AI Assistance Declaration

I used AI tools as coding and documentation assistants during development.

AI assistance was used for:

- generating and refining boilerplate code, documentation, and runbook text
- debugging Docker, Spark, Airflow, Kafka, MinIO, MLflow, Grafana, and notebook issues
- improving README structure, presentation flow, and final-demo explanations
- reviewing code for consistency, missing documentation, and reproducibility gaps

All final design decisions, dataset setup, execution, validation, screenshots,
and presentation understanding are my responsibility. I reviewed, tested, and
modified the generated suggestions before including them in the final project.
