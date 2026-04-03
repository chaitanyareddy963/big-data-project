COMPOSE ?= docker compose
PROJECT ?= big-data-project
DEVBOX_RUN = $(COMPOSE) --profile dev run --rm devbox
SPARK_RUN = $(COMPOSE) exec -T -e PYTHONPATH=/workspace spark-master spark-submit

.PHONY: up down logs ps devbox init-topics smoke monitoring airflow prepare-local-data ingest-sample build-silver build-gold train serve replay reset-kafka reset-data reset-all

up:
	$(COMPOSE) up -d postgres minio minio-init kafka spark-master spark-worker mlflow

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs --tail=200 -f

ps:
	$(COMPOSE) ps

devbox:
	$(COMPOSE) --profile dev run --rm devbox bash

init-topics:
	./scripts/init_topics.sh

smoke:
	./scripts/smoke.sh

monitoring:
	$(COMPOSE) --profile monitoring up -d prometheus grafana

airflow:
	$(COMPOSE) --profile airflow up -d airflow-init airflow-webserver airflow-scheduler

prepare-local-data:
	$(DEVBOX_RUN) python -m src.jobs.prepare_local_data --output data/local/aviation_events_2024-01.csv

ingest-sample:
	$(SPARK_RUN) /workspace/src/jobs/ingest_batch.py --input /workspace/data/sample/aviation_events_smoke.csv

build-silver:
	$(SPARK_RUN) /workspace/src/jobs/build_silver.py

build-gold:
	$(SPARK_RUN) /workspace/src/jobs/build_gold.py

train:
	$(DEVBOX_RUN) python -m src.jobs.train_model

serve:
	$(DEVBOX_RUN) python -m src.api.bundle_model && \
	$(COMPOSE) --profile dev run --rm -p 127.0.0.1:3001:3001 devbox \
		bentoml serve src.api.service:svc --host 0.0.0.0 --port 3001

replay:
	$(DEVBOX_RUN) python -m src.producers.replay_producer --input data/sample/aviation_events_smoke.csv --topic weather.replay --speed 1.0

reset-kafka:
	./scripts/reset_kafka.sh

reset-data:
	./scripts/reset_data.sh

reset-all:
	./scripts/reset_all.sh
