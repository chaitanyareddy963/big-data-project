#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<EOSQL
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${AIRFLOW_DB_USER}') THEN
      CREATE ROLE ${AIRFLOW_DB_USER} LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
   END IF;
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${MLFLOW_DB_USER}') THEN
      CREATE ROLE ${MLFLOW_DB_USER} LOGIN PASSWORD '${MLFLOW_DB_PASSWORD}';
   END IF;
END
$$;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tc "SELECT 1 FROM pg_database WHERE datname='${AIRFLOW_DB}'" | grep -q 1 || \
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE ${AIRFLOW_DB} OWNER ${AIRFLOW_DB_USER};"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tc "SELECT 1 FROM pg_database WHERE datname='${MLFLOW_DB}'" | grep -q 1 || \
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE ${MLFLOW_DB} OWNER ${MLFLOW_DB_USER};"
