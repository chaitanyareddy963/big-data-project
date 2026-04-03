#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists --topic weather.live --partitions 1 --replication-factor 1

docker compose exec -T kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists --topic weather.replay --partitions 1 --replication-factor 1

docker compose exec -T kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists --topic disruption.scores --partitions 1 --replication-factor 1

docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092 --list
