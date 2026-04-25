## Current Status

Progress Review 1 is complete.

Working flow:

```text
ARCO-ERA5 weather sample
    ↓
JupyterLab download notebook
    ↓
MinIO raw bucket
    ↓
Kafka replay producer notebook
    ↓
Kafka topic weather.raw
    ↓
Kafka consumer notebook
    ↓
MinIO raw/kafka_weather_events/
    ↓
Validation notebook