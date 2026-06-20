# Aviation Weather Disruption Intelligence Platform

Z5008 Big Data Lab course project.

This project builds an aviation disruption intelligence platform from
downloaded real datasets: ARCO-ERA5 airport-hour weather and official BTS
Reporting Carrier On-Time Performance flight outcomes. The final demo trains
and serves a disruption model, then replays real Gold feature rows as a
streaming test-set simulation through Kafka, BentoML, Prometheus, Grafana, and
an optional Groq/Llama Q&A assistant.

## What This Demonstrates

```text
ARCO-ERA5 + BTS raw data in MinIO
  -> Kafka replay and raw storage checks
  -> Spark Bronze/Silver/Gold lakehouse
  -> BTS-based disruption labels
  -> Spark MLlib model and MLflow registry
  -> BentoML prediction API
  -> dataset streaming simulation through Kafka
  -> Prometheus + Grafana dashboards
  -> Groq Llama 3.3 70B project Q&A assistant
```

## Dataset

The large raw dataset is not stored in Git.

Prepared Google Drive dataset bundle:

```text
https://drive.google.com/drive/folders/1vqFcJ7uuofHbDHvY4VMAMO5mJolVmgiu?usp=sharing
```

Approximate sizes used in the verified VM:

| Data | Size |
|---|---:|
| Prepared ARCO-ERA5 + metadata bundle | ~44.5 GiB |
| Official BTS ZIP archives, 2015-2024 | ~3.0 GiB |
| Raw MinIO after restore | ~47 GiB |
| Generated 2024 lakehouse outputs | ~18 GiB |
| Recommended VM disk | 220 GiB |

Fresh-clone dataset and MinIO setup:

```text
docs/setup_dataset.md
```

## Quick Start

```bash
git clone <repo-url>
cd big-data-project
cp .env.example .env
```

Edit `.env`:

```bash
MINIO_ROOT_USER=...
MINIO_ROOT_PASSWORD=...
AWS_ACCESS_KEY_ID=<same as MINIO_ROOT_USER>
AWS_SECRET_ACCESS_KEY=<same as MINIO_ROOT_PASSWORD>
JUPYTER_TOKEN=...
HOST_UID=<output of id -u>
HOST_GID=<output of id -g>
```

Optional LLM key:

```bash
GROQ_API_KEY=...
```

Start core services:

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
```

Restore datasets into MinIO using:

```text
docs/setup_dataset.md
```

Run the final notebook:

```text
notebooks/final/10_dataset_streaming_demo.ipynb
```

## Main URLs

| Service | URL |
|---|---|
| JupyterLab | http://localhost:8888 |
| MinIO | http://localhost:9001 |
| Kafka UI | http://localhost:8085 |
| Spark Master | http://localhost:8080 |
| MLflow | http://localhost:5000 |
| BentoML API | http://localhost:3000 |
| Grafana | http://localhost:3001 |
| LLM Chat UI | http://localhost:7860 |

## Important Docs

| Document | Purpose |
|---|---|
| `docs/setup_dataset.md` | Fresh clone, dataset download, BTS download, MinIO upload, lakehouse build |
| `docs/final_demo/02_full_platform_runbook.md` | Final presentation runbook |
| `notebooks/README.md` | Notebook order for PR1, PR2, and final demo |

## Final Demo Notebook

Use this as the main presentation notebook:

```text
notebooks/final/10_dataset_streaming_demo.ipynb
```

It contains runnable cells for:

- service health checks
- real Gold dataset streaming replay through Kafka
- Kafka topic verification
- 10x API load test
- Prometheus source metrics
- Grafana dashboard pointers
- Groq/Llama project Q&A assistant
- browser chatbot UI check

## Project Structure

```text
api/                 BentoML API, scoring helpers, dataset replay, chatbot
spark_jobs/          Production Spark jobs for Bronze/Silver/Gold/Delta/modeling
ml/                  Final MLflow model registration/export
dags/                Airflow orchestration
dashboards/          Prometheus and Grafana provisioning
notebooks/           PR1, PR2, and final presentation notebooks
docs/                Setup guides and final runbooks
tests/               Focused API and archive tests
```

## Notes For New Users

- `.env`, raw data, MinIO volumes, generated lakehouse outputs, and model files
  are intentionally not committed.
- Restore raw data before running PR2/final notebooks.
- The final verified large-data proof uses all 2024 months.
- The final streaming demo replays historical Gold rows from the downloaded
  dataset as Kafka events.
