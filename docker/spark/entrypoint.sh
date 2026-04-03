#!/usr/bin/env bash
set -euo pipefail

SPARK_HOME="${SPARK_HOME:-/opt/spark}"

if [[ "${SPARK_MODE:-}" == "master" ]]; then
  exec "${SPARK_HOME}/bin/spark-class" org.apache.spark.deploy.master.Master \
    --host "${SPARK_MASTER_HOST:-spark-master}" \
    --port "${SPARK_MASTER_PORT_NUMBER:-7077}" \
    --webui-port "${SPARK_MASTER_WEBUI_PORT_NUMBER:-8080}"
fi

if [[ "${SPARK_MODE:-}" == "worker" ]]; then
  exec "${SPARK_HOME}/bin/spark-class" org.apache.spark.deploy.worker.Worker \
    --webui-port "${SPARK_WORKER_WEBUI_PORT_NUMBER:-8081}" \
    "${SPARK_MASTER_URL:?SPARK_MASTER_URL must be set}"
fi

exec "$@"
