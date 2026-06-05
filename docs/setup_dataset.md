# Dataset Setup for a Fresh Clone

This project expects large raw datasets in MinIO. They are intentionally not
committed to Git.

## What Is Not In The Repo

The following are local/runtime artifacts:

```text
data/local_cache/
models/
Docker volumes: minio-data, mlflow-data, grafana-data, kafka-data
.env
```

They are ignored because the raw data and lakehouse outputs are too large for
Git and `.env` contains secrets.

## Expected Raw MinIO Layout

The Spark jobs and notebooks expect:

```text
raw/arco_era5_us_airport_hourly/
raw/bts_on_time/raw_zip/
raw/metadata/
```

The verified project scope is:

```text
ARCO-ERA5 airport-hour weather: 2015-2024, 720 parquet files
BTS on-time ZIP archives:       2015-2024, 120 monthly ZIP files
OurAirports metadata:           airport/grid mapping parquet files
```

For a faster proof, restore at least all **2024** ARCO/BTS/monthly metadata
files. For the final demonstrated setup, the repo was verified with all 12
months of 2024 processed through Bronze, Silver, Gold, Delta, MLflow, and API
serving.

## Option A: Restore Prepared Dataset Bundle

If the dataset bundle is available in Google Drive or another object store,
download it to the ignored local cache:

```bash
cd /home/$USER/big-data-project
mkdir -p data/local_cache/google_drive

rclone copy \
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

Expected restored local layout:

```text
data/local_cache/google_drive/aviation_weather_disruption_us_10y/
  bronze/arco_era5_us_airport_hourly/
  metadata/
```

The ARCO weather directory should contain monthly/year partitions such as:

```text
bronze/arco_era5_us_airport_hourly/year=2024/month=01/*.parquet
```

## Option B: Regenerate Source Data

If the prepared Drive bundle is unavailable:

1. Use `ARCO_ERA5_Dataset_Download_Script.ipynb` to rebuild the ARCO-ERA5
   airport-hour dataset.
2. Download official BTS Reporting Carrier On-Time Performance monthly ZIP
   files for the target years.
3. Generate or restore the OurAirports airport/grid metadata.

This path is slower and depends on external source availability. The rest of
the project does not care how the raw files are produced as long as they are
placed in the MinIO paths listed above.

## Start MinIO

```bash
docker compose up -d minio mc
docker compose ps minio
```

Check buckets:

```bash
docker run --rm \
  --network big-data-project_aviation-net \
  --env-file .env \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c 'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" && mc ls local'
```

If needed, create the raw bucket:

```bash
docker run --rm \
  --network big-data-project_aviation-net \
  --env-file .env \
  --entrypoint /bin/sh \
  minio/mc:latest \
  -c 'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" && mc mb --ignore-existing local/raw'
```

## Upload ARCO-ERA5 To MinIO

From the prepared bundle:

```bash
DATA_ROOT="$PWD/data/local_cache/google_drive/aviation_weather_disruption_us_10y"

docker run --rm \
  --network big-data-project_aviation-net \
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
  --network big-data-project_aviation-net \
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

## Upload BTS ZIP Archives To MinIO

Place the official BTS monthly ZIP files locally:

```text
data/local_cache/bts_on_time/raw_zip/
```

Expected file naming pattern:

```text
On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_1.zip
On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_2.zip
...
On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_12.zip
```

Verify local ZIP files:

```bash
BTS_DIR="$PWD/data/local_cache/bts_on_time/raw_zip"

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

Mirror to MinIO:

```bash
docker run --rm \
  --network big-data-project_aviation-net \
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

## Verify MinIO Raw Data

```bash
docker run --rm \
  --network big-data-project_aviation-net \
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

For the verified setup:

```text
ARCO 2024 parquet files: 72
BTS 2024 ZIP files: 12
```

## Build Lakehouse Data

Fast January proof:

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

If interrupted, resume by month:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m spark_jobs.run_year_pipeline --year 2024 --start-month 4 --end-month 12 --with-delta --with-final-model
'
```

## Train/Refresh API Model

The API expects:

```text
models/final_numeric_logistic_model.json
```

The one-year runner creates it when `--with-final-model` is used. If needed,
run manually:

```bash
docker compose exec jupyter bash -lc '
  cd /workspace &&
  python -m ml.train_register_model --year 2024
'
docker compose build aviation-api
docker compose up -d aviation-api
```

## Final Demo Services

```bash
docker compose up -d aviation-api prometheus grafana kafka kafka-ui llm-chat
```

Open:

```text
Jupyter:     http://localhost:8888
MinIO:       http://localhost:9001
Kafka UI:    http://localhost:8085
MLflow:      http://localhost:5000
Grafana:     http://localhost:3001
LLM Chat UI: http://localhost:7860
```

Run:

```text
notebooks/final/10_live_and_simulation_demo.ipynb
```

## Optional External API Keys

For live flight operations:

```bash
AERODATABOX_MARKETPLACE=rapidapi
AERODATABOX_API_KEY=...
AERODATABOX_RAPIDAPI_HOST=aerodatabox.p.rapidapi.com
```

For the LLM chatbot:

```bash
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
```

After editing `.env`, recreate services that read those keys:

```bash
docker compose up -d --force-recreate llm-chat jupyter
```

## Common Problems

- `Airport not found in metadata`: `raw/metadata/ourairports/` is missing or
  incomplete.
- `BTS archive not found`: monthly ZIP names do not match the expected BTS
  pattern.
- `Connection refused` from notebooks: use internal Docker hostnames
  (`aviation-api`, `prometheus`, `grafana`) inside containers, not localhost.
- `No data in Grafana`: generate requests first by running live/demo notebook
  cells or the load test.
- Disk pressure: raw + MinIO + lakehouse copies can exceed 100 GiB. Keep at
  least 50-70 GiB free before running the full-year pipeline.
