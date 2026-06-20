# Fresh Clone Dataset Setup

This guide is for a new user or evaluator cloning the repository on a new VM.
The repository does **not** include large raw datasets, generated lakehouse
outputs, Docker volumes, model artifacts, or secret `.env` values.

## Required Raw Data

The jobs expect these MinIO paths:

```text
raw/arco_era5_us_airport_hourly/
raw/bts_on_time/raw_zip/
raw/metadata/
```

Verified data sizes from the project VM:

| Data | Approximate size |
|---|---:|
| Prepared ARCO-ERA5 + metadata bundle | 44.5 GiB |
| BTS 2015-2024 ZIP archives | 3.0 GiB |
| Raw MinIO after restore | 47 GiB |
| Generated 2024 lakehouse outputs | 18 GiB |
| Recommended VM disk | 220 GiB |

Use at least a 150 GiB disk for a small proof and around 220 GiB for the
one-year proof plus raw/local/MinIO copies.

## 1. Clone And Configure

```bash
git clone <repo-url>
cd big-data-project
cp .env.example .env
```

Edit `.env`:

```bash
MINIO_ROOT_USER=your-minio-user
MINIO_ROOT_PASSWORD=your-minio-password
AWS_ACCESS_KEY_ID=your-minio-user
AWS_SECRET_ACCESS_KEY=your-minio-password
JUPYTER_TOKEN=your-jupyter-token
HOST_UID=<output of id -u>
HOST_GID=<output of id -g>
```

Optional Q&A assistant key:

```bash
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.3-70b-versatile
```

Start MinIO and core services:

```bash
docker compose up -d minio mc kafka kafka-ui spark-master spark-worker jupyter mlflow
```

## 2. Download Prepared ARCO-ERA5 + Metadata Bundle

Prepared Google Drive folder:

```text
https://drive.google.com/drive/folders/1vqFcJ7uuofHbDHvY4VMAMO5mJolVmgiu?usp=sharing
```

This folder is the prepared project data bundle used for ARCO-ERA5 airport-hour
weather and metadata. It is about **44.5 GiB**.

### Recommended: rclone

Install and configure rclone:

```bash
sudo apt-get update
sudo apt-get install -y rclone
rclone config
```

Create a Google Drive remote named `gdrive`. If the shared folder appears under
Shared with me, this usually works:

```bash
mkdir -p data/local_cache/google_drive

rclone copy \
  --drive-shared-with-me \
  "gdrive:aviation_weather_disruption_us_10y" \
  "data/local_cache/google_drive/aviation_weather_disruption_us_10y" \
  --progress \
  --transfers 4 \
  --checkers 8 \
  --drive-chunk-size 64M \
  --retries 5 \
  --low-level-retries 10 \
  --log-file "data/local_cache/google_drive_download.log" \
  --log-level INFO
```

If rclone cannot see the shared folder by name, use the folder ID from the URL:

```bash
FOLDER_ID="1vqFcJ7uuofHbDHvY4VMAMO5mJolVmgiu"

rclone copy \
  --drive-root-folder-id "$FOLDER_ID" \
  "gdrive:" \
  "data/local_cache/google_drive/aviation_weather_disruption_us_10y" \
  --progress \
  --transfers 4 \
  --checkers 8 \
  --drive-chunk-size 64M \
  --retries 5 \
  --low-level-retries 10 \
  --log-file "data/local_cache/google_drive_download.log" \
  --log-level INFO
```

Verify local restore:

```bash
DATA_ROOT="data/local_cache/google_drive/aviation_weather_disruption_us_10y"

du -sh "$DATA_ROOT"
find "$DATA_ROOT" -type f | wc -l
find "$DATA_ROOT/bronze/arco_era5_us_airport_hourly" -name '*.parquet' | wc -l
find "$DATA_ROOT/metadata" -type f | wc -l
```

Expected full bundle:

```text
Size: about 45G
ARCO parquet files: about 720
```

Browser download from Google Drive can work, but it is not recommended for a
45 GiB folder because partial failures are hard to resume.

## 3. Download Official BTS ZIP Archives

The BTS data is the official Reporting Carrier On-Time Performance dataset.
This project uses monthly ZIP archives named:

```text
On_Time_Reporting_Carrier_On_Time_Performance_1987_present_<YEAR>_<MONTH>.zip
```

Download 2015-2024 directly from BTS TranStats PREZIP:

```bash
BTS_DIR="$PWD/data/local_cache/bts_on_time/raw_zip"
mkdir -p "$BTS_DIR"

for year in $(seq 2015 2024); do
  for month in $(seq 1 12); do
    file="On_Time_Reporting_Carrier_On_Time_Performance_1987_present_${year}_${month}.zip"
    url="https://transtats.bts.gov/PREZIP/${file}"
    echo "Downloading $file"
    curl -fL --retry 5 --retry-delay 5 \
      "$url" \
      -o "$BTS_DIR/$file"
  done
done
```

Verify ZIPs:

```bash
du -sh "$BTS_DIR"
find "$BTS_DIR" -name '*.zip' | wc -l

FAILED=0
for zip_file in "$BTS_DIR"/*.zip; do
  if ! unzip -tq "$zip_file" >/dev/null; then
    echo "FAILED ZIP: $zip_file"
    FAILED=$((FAILED + 1))
  fi
done
echo "Failed ZIP files: $FAILED"
```

Expected full BTS restore:

```text
120 ZIP files
about 3.0G
Failed ZIP files: 0
```

For a faster first proof, download only 2024:

```bash
BTS_DIR="$PWD/data/local_cache/bts_on_time/raw_zip"
mkdir -p "$BTS_DIR"

for month in $(seq 1 12); do
  file="On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_${month}.zip"
  curl -fL --retry 5 --retry-delay 5 \
    "https://transtats.bts.gov/PREZIP/${file}" \
    -o "$BTS_DIR/$file"
done
```

## 4. Upload Raw Data To MinIO

Start MinIO:

```bash
docker compose up -d minio mc
```

Set paths:

```bash
NETWORK="$(basename "$PWD")_aviation-net"
DATA_ROOT="$PWD/data/local_cache/google_drive/aviation_weather_disruption_us_10y"
BTS_DIR="$PWD/data/local_cache/bts_on_time/raw_zip"
```

Create/check the raw bucket:

```bash
docker run --rm \
  --network "$NETWORK" \
  --env-file .env \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c 'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" && mc mb --ignore-existing local/raw && mc ls local'
```

Upload ARCO-ERA5:

```bash
docker run --rm \
  --network "$NETWORK" \
  --env-file .env \
  -v "$DATA_ROOT:/dataset:ro" \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
    mc mirror --overwrite --summary \
      /dataset/bronze/arco_era5_us_airport_hourly \
      local/raw/arco_era5_us_airport_hourly
  '
```

Upload metadata:

```bash
docker run --rm \
  --network "$NETWORK" \
  --env-file .env \
  -v "$DATA_ROOT:/dataset:ro" \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
    mc mirror --overwrite --summary \
      /dataset/metadata \
      local/raw/metadata
  '
```

Upload BTS:

```bash
docker run --rm \
  --network "$NETWORK" \
  --env-file .env \
  -v "$BTS_DIR:/bts:ro" \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
    mc mirror --overwrite --summary \
      /bts \
      local/raw/bts_on_time/raw_zip
  '
```

## 5. Verify MinIO Restore

```bash
docker run --rm \
  --network "$NETWORK" \
  --env-file .env \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
    echo "ARCO 2024 parquet files:" &&
    mc find local/raw/arco_era5_us_airport_hourly/year=2024 --name "*.parquet" | wc -l &&
    echo "BTS 2024 ZIP files:" &&
    mc find local/raw/bts_on_time/raw_zip --name "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_*.zip" | wc -l &&
    echo "Metadata:" &&
    mc ls local/raw/metadata
  '
```

Expected for 2024:

```text
ARCO 2024 parquet files: 72
BTS 2024 ZIP files: 12
```

## 6. Build Lakehouse Outputs

January proof:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m spark_jobs.validate_raw_weather --year 2024 --month 1 &&
  python -m spark_jobs.build_bronze_weather --year 2024 --month 1 &&
  python -m spark_jobs.build_bronze_bts --year 2024 --month 1 &&
  python -m spark_jobs.build_silver_flight_weather --year 2024 --month 1 &&
  python -m spark_jobs.build_gold_features --year 2024 --month 1 &&
  python -m spark_jobs.build_delta_lakehouse --year 2024 --month 1
'
```

Full 2024 proof:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m spark_jobs.run_year_pipeline --year 2024 --with-delta --with-final-model
'
```

Resume if interrupted:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m spark_jobs.run_year_pipeline --year 2024 --start-month 4 --end-month 12 --with-delta --with-final-model
'
```

## 7. Model, API, And Dataset Streaming Demo

The final API reads:

```text
models/final_numeric_logistic_model.json
```

The full-year runner creates this when `--with-final-model` is used. To train
or refresh manually:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m ml.train_register_model --year 2024
'

docker compose build aviation-api llm-chat
docker compose up -d aviation-api prometheus grafana kafka kafka-ui llm-chat
```

Run the streaming replay:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m api.simulate_gold_stream_predict \
    --year 2024 \
    --month 1 \
    --limit 100 \
    --delay-seconds 0.1 \
    --output-jsonl data/local_cache/streaming_predictions/gold_simulation.jsonl \
    --api-url http://aviation-api:3000/predict
'
```

Open:

```text
Jupyter:     http://localhost:8888
Kafka UI:    http://localhost:8085
MLflow:      http://localhost:5000
Grafana:     http://localhost:3001
LLM Chat UI: http://localhost:7860
```

Run:

```text
notebooks/final/10_dataset_streaming_demo.ipynb
```

## Common Issues

- If `raw/metadata` is missing, Spark joins can fail.
- If BTS names do not match the expected pattern, `build_bronze_bts.py` cannot
  find the archive.
- If notebooks run inside Docker, use internal hostnames such as
  `aviation-api`, `prometheus`, `grafana`, and `kafka`.
- If Grafana is empty, run the dataset streaming notebook or load test first.
- If disk is tight, delete local cache after MinIO upload or run only 2024.
