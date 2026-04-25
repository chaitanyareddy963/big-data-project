# Progress Review 1 — Ingestion + Storage Demo

## Project

Real-Time Aviation Weather Disruption Intelligence Platform

## Scope

This review demonstrates the ingestion and storage slice:

ARCO-ERA5 sample → Kafka topic → Kafka consumer → MinIO raw storage → validation notebook.

## Services

- JupyterLab
- Apache Kafka
- Kafka UI
- MinIO
- Python Kafka producer notebook
- Python Kafka consumer notebook

## Data

- Source: ARCO-ERA5
- Airport: JFK
- Time range: 2022-01-01 to 2022-01-03
- Frequency: hourly
- Records: 72
- Variables:
  - 2m temperature
  - 10m U wind
  - 10m V wind
  - total precipitation
  - surface pressure
  - CAPE

## Demo Flow

1. Show containers running.
2. Show real ERA5 data downloaded in Notebook 01.
3. Show sample stored in MinIO raw bucket.
4. Show Kafka topic `weather.raw`.
5. Run consumer notebook.
6. Run producer notebook.
7. Show messages flowing.
8. Show streamed JSONL objects written to MinIO.
9. Run validation notebook and show row count.

## Evidence

- Real data is used, not fake generated rows.
- Kafka is used for streaming ingestion.
- MinIO stores both downloaded sample and streamed events.
- Jupyter notebooks document every step clearly.