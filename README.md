# Real-Time Aviation Weather Disruption Intelligence Platform

Z5008 Big Data Lab course project.

## Project Overview

This project builds an aviation disruption intelligence platform from original
ARCO-ERA5 weather data and official BTS Reporting Carrier On-Time Performance
records.

The live demo combines:

```text
Original ARCO-ERA5 weather in MinIO
    -> bounded representative Kafka replay
    -> Kafka consumer micro-batches in MinIO raw storage
    -> Spark Bronze weather and BTS flight tables
    -> Spark Silver flight-weather join with real BTS outcomes
    -> Spark Gold leakage-conscious features
    -> Spark MLlib experiments
    -> MLflow diagnostic run comparison
```

The original raw datasets remain immutable. Kafka demonstrates the streaming
layer with a controlled replay slice; Spark batch jobs process the larger
monthly partitions directly.

## Original Dataset Scope

Raw datasets currently stored in MinIO:

| Dataset | Scope | MinIO path |
|---|---|---|
| ARCO-ERA5 airport-hour weather | 2015-2024, 720 Parquet files, 120 monthly partitions | `raw/arco_era5_us_airport_hourly/` |
| BTS on-time flight records | 2015-2024, 120 monthly ZIP archives | `raw/bts_on_time/raw_zip/` |
| OurAirports metadata | Airport and ERA5 grid mapping files | `raw/metadata/ourairports/` |

The first verified large-data proof uses January 2024:

| Layer | Rows |
|---|---:|
| Original ARCO-ERA5 weather | 18,693,744 |
| Bronze BTS flights | 547,271 |
| Silver matched flight-weather rows | 543,121 |
| Gold training rows | 543,121 |

The final large-data path is designed to run the same pipeline for all 12
months of a selected year across the available US airport coverage. January
2024 remains the fast proof; the full-year runner is used when enough demo time
and disk budget are available.

## Services

| Service | Purpose | URL |
|---|---|---|
| JupyterLab | Notebook demo environment | http://localhost:8888 |
| MinIO | S3-compatible storage | http://localhost:9001 |
| Kafka | Streaming ingestion | Internal: `kafka:9092` |
| Kafka UI | Topic inspection | http://localhost:8085 |
| Spark Master | Cluster manager | http://localhost:8080 |
| Spark Worker | Spark executor | http://localhost:8081 |
| MLflow | Experiment tracking | http://localhost:5000 |
| Airflow | Scheduled pipeline orchestration | http://localhost:8088 |
| BentoML API | Disruption prediction endpoint | http://localhost:3000 |
| LLM Chat UI | Groq/Llama operations assistant | http://localhost:7860 |
| Prometheus | API metrics collection | http://localhost:9090 |
| Grafana | Live monitoring dashboard | http://localhost:3001 |

Start services:

```bash
docker compose up -d minio mc kafka kafka-ui jupyter spark-master spark-worker mlflow
docker compose ps
```

Copy `.env.example` to `.env`, replace placeholder secrets, and keep `.env`
untracked.

## Fresh Clone Setup

This repository does **not** contain the large datasets, MinIO volumes, trained
model JSON, or secret API keys. A new user must restore or regenerate data
before running the PR2/final notebooks.

Minimum practical VM:

```text
Disk: 220 GiB recommended for one-year proof with raw + lakehouse copies
Memory: 16 GiB recommended
Docker + Docker Compose required
```

Clone and configure:

```bash
git clone <repo-url>
cd big-data-project
cp .env.example .env
```

Edit `.env` and set at least:

```bash
MINIO_ROOT_USER=...
MINIO_ROOT_PASSWORD=...
AWS_ACCESS_KEY_ID=<same as MINIO_ROOT_USER>
AWS_SECRET_ACCESS_KEY=<same as MINIO_ROOT_PASSWORD>
JUPYTER_TOKEN=...
HOST_UID=$(id -u)
HOST_GID=$(id -g)
```

Optional live-demo keys:

```bash
AERODATABOX_API_KEY=...
GROQ_API_KEY=...
```

Start storage and core services:

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
```

Then restore datasets into MinIO at these exact paths:

```text
raw/arco_era5_us_airport_hourly/
raw/bts_on_time/raw_zip/
raw/metadata/
```

See the complete data restoration guide:

```text
docs/setup_dataset.md
```

After data is restored, verify and build the one-year proof:

```bash
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.run_year_pipeline --year 2024 --with-delta --with-final-model'
```

Run the final notebook demo:

```text
notebooks/final/10_live_and_simulation_demo.ipynb
```

## Notebook Presentation Flow

The notebooks are the live presentation layer. They show important code,
schemas, previews, checks, charts, and conclusions cell by cell. See
`notebooks/README.md`.

### Phase 1: Ingestion and Storage

Run:

1. `notebooks/pr1/00_environment_smoke_test.ipynb`
2. `notebooks/pr1/01_download_era5_sample_to_minio.ipynb`
3. `notebooks/pr1/02_kafka_to_minio_consumer.ipynb`
4. `notebooks/pr1/03_kafka_replay_producer.ipynb`
5. `notebooks/pr1/04_validate_streamed_storage.ipynb`

Despite its historical filename, notebook `01` now inventories the original
large MinIO datasets. The producer no longer reads the old 72-row JFK fixture.

### Phase 2: Spark Lakehouse and ML Diagnostics

Run:

1. `notebooks/pr2/01_spark_smoke_test.ipynb`
2. `notebooks/pr2/02_spark_read_minio_raw.ipynb`
3. `notebooks/pr2/03_create_bronze_weather_table.ipynb`
4. `notebooks/pr2/04_create_labels.ipynb`
5. `notebooks/pr2/05_feature_engineering.ipynb`
6. `notebooks/pr2/06_train_spark_mllib_model.ipynb`
7. `notebooks/pr2/07_mlflow_experiments.ipynb`

Notebook `04` now creates or inspects Bronze BTS data. Notebook `05` creates
labels from actual BTS cancellation and arrival-delay outcomes. The removed
weather-rule proxy label must not be presented as model quality evidence.

## Production Spark Jobs

The course rubric requires production Spark jobs as `.py` files, not only
notebooks. Reusable jobs live under `spark_jobs/`:

```text
spark_jobs/validate_raw_weather.py
spark_jobs/build_bronze_weather.py
spark_jobs/build_bronze_bts.py
spark_jobs/build_silver_flight_weather.py
spark_jobs/build_gold_features.py
spark_jobs/train_mllib_experiments.py
spark_jobs/build_delta_lakehouse.py
spark_jobs/stream_kafka_weather_to_delta.py
```

Run the January proof from the Jupyter container:

```bash
docker compose exec jupyter bash
cd /workspace

python -m spark_jobs.validate_raw_weather --year 2024 --month 1
python -m spark_jobs.build_bronze_weather --year 2024 --month 1
python -m spark_jobs.build_bronze_bts --year 2024 --month 1
python -m spark_jobs.build_silver_flight_weather --year 2024 --month 1
python -m spark_jobs.build_gold_features --year 2024 --month 1
python -m spark_jobs.train_mllib_experiments --year 2024 --month 1
python -m spark_jobs.build_delta_lakehouse --year 2024 --month 1
python -m spark_jobs.stream_kafka_weather_to_delta --trigger-once
python -m ml.train_register_model
```

Run the one-year proof for all 2024 months:

```bash
docker compose exec jupyter bash
cd /workspace

python -m spark_jobs.run_year_pipeline --year 2024 --with-delta --with-final-model
```

The runner is resumable by month:

```bash
python -m spark_jobs.run_year_pipeline --year 2024 --start-month 4 --end-month 12
```

## Lakehouse Layout

```text
raw/arco_era5_us_airport_hourly/
raw/bts_on_time/raw_zip/
raw/metadata/
raw/kafka_weather_events_original/

lakehouse/bronze/weather/year=2024/month=01/
lakehouse/bronze/bts_on_time/year=2024/month=01/
lakehouse/silver/flight_weather_daily/year=2024/month=01/
lakehouse/gold/training_features/year=2024/month=01/

lakehouse/bronze_delta/weather/year=2024/month=01/
lakehouse/bronze_delta/bts_on_time/year=2024/month=01/
lakehouse/silver_delta/flight_weather_daily/year=2024/month=01/
lakehouse/gold_delta/training_features/year=2024/month=01/
lakehouse/bronze_delta/kafka_weather_events/
```

Partitioned Parquet remains as an auditable intermediate. Production Delta Lake
tables add transaction logs for the final platform and Structured Streaming
writes Kafka events into a Delta sink with a MinIO checkpoint.

## Final Platform Layers

Additional components:

- `dags/aviation_lakehouse_dag.py`: scheduled Airflow pipeline.
- `ml/train_register_model.py`: balanced chronological Spark MLlib model,
  MLflow artifact logging, registry version creation, and staging/production
  aliases.
- `api/service.py`: BentoML `POST /predict` endpoint.
- `api/load_test.py`: 100-request, 10-concurrent-request stability demo.
- `api/live_weather_predict.py`: live Open-Meteo inference demo. It can run
  once or continuously poll current airport weather and score every snapshot
  through the deployed API.
- `api/live_operational_predict.py`: recommended live final demo path. It
  combines AviationWeather.gov METAR observations with AeroDataBox airport
  arrivals/departures, scores the deployed model, and logs each live event.
- `api/simulate_gold_stream_predict.py`: replays real Gold feature rows as a
  simulated live stream, publishes each event to Kafka, calls the deployed API,
  and logs prediction evidence.
- `api/llm_ops_assistant.py`: optional Groq/Llama 3.3 70B assistant that
  answers demo questions using latest live events, simulation events, and
  Prometheus metrics as context.
- `api/llm_chat_ui.py`: browser chatbot UI for the same assistant, exposed by
  Docker Compose at <http://localhost:7860>.
- `spark_jobs/call_api_with_gold_sample.py`: calls the deployed API using a
  real row from the Gold feature table.
- `dashboards/`: Prometheus scrape configuration and provisioned Grafana
  dashboards for external live API traffic and dataset simulation replay.
- `tests/`: focused tests for BTS archive validation and API scoring.

Run the full final demonstration using:

```bash
docker compose up -d airflow
docker compose up -d aviation-api prometheus grafana
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m spark_jobs.call_api_with_gold_sample --year 2024 --month 1 --api-url http://aviation-api:3000/predict'
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.live_weather_predict --airport JFK --watch --interval-seconds 30 --max-iterations 10 --output-jsonl data/local_cache/live_predictions/jfk.jsonl --api-url http://aviation-api:3000/predict'
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.live_operational_predict --airport JFK --watch --interval-seconds 60 --max-iterations 10 --output-jsonl data/local_cache/live_predictions/jfk_operational.jsonl --api-url http://aviation-api:3000/predict'
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.simulate_gold_stream_predict --year 2024 --month 1 --limit 100 --delay-seconds 0.1 --output-jsonl data/local_cache/live_predictions/gold_simulation.jsonl --api-url http://aviation-api:3000/predict'
docker compose exec jupyter bash -lc \
  'cd /workspace && python -m api.llm_ops_assistant --prometheus-url http://prometheus:9090 --question "What is happening in the live demo right now?"'
docker compose up -d llm-chat
python3 api/load_test.py --requests 100 --concurrency 10
```

For a continuous live run, omit `--max-iterations` and stop it with
`Ctrl+C`. Open Grafana at <http://localhost:3001> while the live loop or load
test is running. AeroDataBox requires `AERODATABOX_API_KEY` in `.env`; without
that key, `live_operational_predict.py` still fetches AviationWeather.gov METAR
weather and clearly marks flight operations as unavailable in the JSON output.
The dataset simulation dashboard appears in Grafana as
`Aviation Dataset Simulation Stream`.
The LLM assistant requires `GROQ_API_KEY` in `.env`; without it, the command
prints a local fallback summary so the notebook remains runnable.
The browser chatbot is available at <http://localhost:7860>.

See `docs/final_demo/02_full_platform_runbook.md` and
`notebooks/final/08_full_platform_demo.ipynb`. For the larger final proof, see
`notebooks/final/09_one_year_real_data_pipeline.ipynb`.
