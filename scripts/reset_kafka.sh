#!/usr/bin/env bash
set -euo pipefail

set -a
source ./.env
set +a

docker compose down
rm -rf volumes/kafka/*
docker compose up -d kafka
sleep 8
./scripts/init_topics.sh
