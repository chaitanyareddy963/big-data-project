"""Gemini-backed LLM assistant for final aviation platform demos.

The assistant summarizes project evidence from downloaded ARCO-ERA5/BTS data,
dataset streaming replay events, API predictions, and Prometheus metrics. It is
a presentation layer only; it does not replace the Spark/ML pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
from typing import Any

import requests


GEMINI_GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_SYSTEM_PROMPT = """You are an aviation disruption intelligence assistant for a big-data course demo.
Answer from the provided project context only. Be concise, concrete, and honest about limitations.
Describe the evidence as downloaded historical data and dataset streaming replay.
You may answer questions about code, docs, notebooks, MLflow, Airflow, Kafka, MinIO, Spark, Grafana, replay events, model predictions, and dashboard metrics when that context is provided."""

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".ipynb",
    ".example",
}
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".ipynb_checkpoints",
    "data",
    "models",
    ".venv",
    "venv",
}
IMPORTANT_PATHS = [
    "README.md",
    "docker-compose.yml",
    ".env.example",
    "docs/setup_dataset.md",
    "docs/final_demo/01_original_data_bronze.md",
    "docs/final_demo/02_full_platform_runbook.md",
    "docs/review_notes/progress_review_1.md",
    "docs/review_notes/progress_review_2.md",
    "notebooks/README.md",
    "notebooks/final/08_full_platform_demo.ipynb",
    "notebooks/final/09_one_year_historical_data_pipeline.ipynb",
    "notebooks/final/10_dataset_streaming_demo.ipynb",
    "dashboards/aviation-final-demo-dashboard.json",
    "dashboards/prometheus.yml",
    "api/service.py",
    "api/scoring.py",
    "api/simulate_gold_stream_predict.py",
    "api/llm_ops_assistant.py",
    "api/llm_chat_ui.py",
    "ml/train_register_model.py",
    "dags/aviation_lakehouse_dag.py",
    "spark_jobs/run_year_pipeline.py",
    "spark_jobs/build_gold_features.py",
    "spark_jobs/train_mllib_experiments.py",
    "spark_jobs/stream_kafka_weather_to_delta.py",
]
LOG_CONTAINERS = [
    "aviation-api",
    "aviation-llm-chat",
    "aviation-prometheus",
    "aviation-grafana",
    "aviation-kafka",
    "aviation-kafka-ui",
    "aviation-minio",
    "aviation-mlflow",
    "aviation-airflow",
    "aviation-spark-master",
    "aviation-spark-worker",
    "aviation-jupyter",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)([\"'=:\\s]+)([^\\s\"']+)"),
    re.compile(r"AIza[0-9A-Za-z\\-_]{20,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
]


def sanitize_answer(answer: str) -> str:
    cleaned = answer.strip()
    replacements = {
        r"(?i)real[- ]time": "dataset streaming",
        r"(?i)live data": "dataset replay data",
        r"(?i)live api": "prediction API",
        r"(?i)live flight": "historical flight",
        r"(?i)live weather": "historical weather",
        r"(?i)external live": "external",
    }
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned or (
        "The dataset streaming replay reads Gold feature rows from the downloaded lakehouse, "
        "publishes replay events to Kafka, scores them through the prediction API, and exposes "
        "the resulting request, latency, and risk metrics in Prometheus and Grafana."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="Summarize what is happening in the aviation disruption platform right now.")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--prometheus-url", default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"))
    parser.add_argument("--repo-root", default=os.getenv("REPO_ROOT", "."))
    parser.add_argument("--mlflow-url", default=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    parser.add_argument("--airflow-url", default=os.getenv("AIRFLOW_URL", "http://localhost:8088"))
    parser.add_argument("--kafka-bootstrap", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--minio-url", default=os.getenv("MINIO_ENDPOINT_INTERNAL", "http://localhost:9000"))
    parser.add_argument("--spark-master-url", default=os.getenv("SPARK_MASTER_UI_URL", "http://localhost:8080"))
    parser.add_argument("--docker-socket", default=os.getenv("DOCKER_SOCKET", "/var/run/docker.sock"))
    parser.add_argument(
        "--simulation-jsonl",
        default="data/local_cache/streaming_predictions/notebook_gold_simulation.jsonl",
    )
    parser.add_argument("--max-events", type=int, default=3)
    parser.add_argument("--max-file-chars", type=int, default=1600)
    parser.add_argument("--max-context-files", type=int, default=25)
    parser.add_argument("--log-tail", type=int, default=40)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1800)
    return parser.parse_args()


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def read_jsonl_tail(path: str, max_events: int) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    lines = [line for line in file_path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines[-max_events:]]


def prometheus_query(prometheus_url: str, query: str) -> Any:
    try:
        response = requests.get(
            f"{prometheus_url.rstrip('/')}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["data"]["result"]
    except Exception as error:
        return {"error": str(error)}


def safe_get_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 8) -> Any:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as error:
        return {"error": str(error)}


def safe_post_json(url: str, payload: dict[str, Any], *, timeout: int = 8) -> Any:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as error:
        return {"error": str(error)}


def text_from_notebook(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return f"[notebook parse error: {error}]"
    parts = []
    for index, cell in enumerate(data.get("cells", []), start=1):
        cell_type = cell.get("cell_type", "unknown")
        source = "".join(cell.get("source", []))
        outputs = cell.get("outputs", [])
        output_summary = f" outputs={len(outputs)}" if outputs else ""
        if source.strip():
            parts.append(f"[cell {index} {cell_type}{output_summary}]\n{source.strip()}")
    return "\n\n".join(parts)


def read_text_file(path: Path) -> str:
    if path.suffix == ".ipynb":
        return text_from_notebook(path)
    return path.read_text(encoding="utf-8", errors="replace")


def should_include_file(path: Path, repo_root: Path) -> bool:
    rel_parts = path.relative_to(repo_root).parts
    if any(part in EXCLUDED_DIRS for part in rel_parts):
        return False
    if path.name == ".env":
        return False
    if path.suffix in TEXT_EXTENSIONS:
        return True
    return path.name in {"Dockerfile", ".gitignore"}


def compact_file_entry(path: Path, repo_root: Path, max_chars: int) -> dict[str, Any]:
    rel = path.relative_to(repo_root).as_posix()
    try:
        raw = path.read_bytes()
        digest = hashlib.sha1(raw).hexdigest()[:12]
        text = read_text_file(path)
        truncated = len(text) > max_chars
        return {
            "path": rel,
            "bytes": len(raw),
            "sha1_12": digest,
            "content_excerpt": text[:max_chars],
            "truncated": truncated,
        }
    except Exception as error:
        return {"path": rel, "error": str(error)}


def collect_codebase_context(repo_root_value: str, max_files: int, max_chars: int) -> dict[str, Any]:
    repo_root = Path(repo_root_value).resolve()
    if not repo_root.exists():
        return {"error": f"repo root not found: {repo_root}"}

    included_paths = []
    for path in repo_root.rglob("*"):
        if path.is_file() and should_include_file(path, repo_root):
            included_paths.append(path)
    included_paths = sorted(included_paths, key=lambda item: item.relative_to(repo_root).as_posix())

    important = []
    seen = set()
    for rel in IMPORTANT_PATHS:
        path = repo_root / rel
        if path.exists() and path.is_file() and should_include_file(path, repo_root):
            important.append(path)
            seen.add(path.resolve())

    for path in included_paths:
        if len(important) >= max_files:
            break
        if path.resolve() not in seen:
            important.append(path)
            seen.add(path.resolve())

    counts_by_suffix: dict[str, int] = {}
    for path in included_paths:
        suffix = path.suffix or path.name
        counts_by_suffix[suffix] = counts_by_suffix.get(suffix, 0) + 1

    return {
        "repo_root": str(repo_root),
        "indexed_file_count": len(included_paths),
        "counts_by_suffix": counts_by_suffix,
        "file_tree": [path.relative_to(repo_root).as_posix() for path in included_paths[:250]],
        "selected_file_contents": [
            compact_file_entry(path, repo_root, max_chars=max_chars) for path in important
        ],
    }


def collect_grafana_dashboard_context(repo_root_value: str) -> dict[str, Any]:
    root = Path(repo_root_value).resolve()
    dashboards = []
    for path in sorted((root / "dashboards").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            dashboards.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "title": data.get("title"),
                    "uid": data.get("uid"),
                    "panels": [
                        {
                            "title": panel.get("title"),
                            "type": panel.get("type"),
                            "queries": [target.get("expr") for target in panel.get("targets", []) if target.get("expr")],
                        }
                        for panel in data.get("panels", [])
                    ],
                }
            )
        except Exception as error:
            dashboards.append({"path": str(path), "error": str(error)})
    return {"dashboards": dashboards}


def collect_mlflow_context(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    registered = safe_get_json(f"{base}/api/2.0/mlflow/registered-models/search")
    experiments = safe_get_json(f"{base}/api/2.0/mlflow/experiments/search", params={"max_results": 10})
    runs = []
    if isinstance(experiments, dict):
        for experiment in experiments.get("experiments", [])[:5]:
            experiment_id = experiment.get("experiment_id")
            result = safe_post_json(
                f"{base}/api/2.0/mlflow/runs/search",
                {"experiment_ids": [experiment_id], "max_results": 5, "order_by": ["attributes.start_time DESC"]},
            )
            runs.append({"experiment": experiment, "latest_runs": result})
    return {"registered_models": registered, "experiments": experiments, "runs_by_experiment": runs}


def collect_airflow_context(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    return {
        "health": safe_get_json(f"{base}/api/v2/monitor/health"),
        "dags": safe_get_json(f"{base}/api/v2/dags", params={"limit": 20}),
    }


def collect_spark_context(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    master_json = safe_get_json(f"{base}/json/")
    if isinstance(master_json, dict) and "error" not in master_json:
        return {
            "status": master_json.get("status"),
            "url": master_json.get("url"),
            "alive_workers": master_json.get("aliveworkers"),
            "cores": {
                "total": master_json.get("cores"),
                "used": master_json.get("coresused"),
            },
            "memory_mb": {
                "total": master_json.get("memory"),
                "used": master_json.get("memoryused"),
            },
            "active_apps": master_json.get("activeapps", []),
            "completed_apps": master_json.get("completedapps", [])[:10],
        }
    return {
        "master_json": master_json,
    }


def collect_kafka_context(bootstrap: str, topic: str = "simulation.prediction.requests") -> dict[str, Any]:
    try:
        from kafka import KafkaConsumer
    except Exception as error:
        return {"error": f"kafka-python unavailable: {error}"}
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap,
            enable_auto_commit=False,
            consumer_timeout_ms=2500,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: value.decode("utf-8", errors="replace"),
        )
        topics = sorted(consumer.topics())
        messages = []
        if topic in topics:
            consumer.subscribe([topic])
            for message in consumer:
                messages.append(
                    {
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "key": message.key.decode("utf-8", errors="replace") if message.key else None,
                        "value_excerpt": message.value[:1200],
                    }
                )
                if len(messages) >= 10:
                    break
        consumer.close()
        return {"topics": topics, "sample_topic": topic, "sample_messages": messages[-5:]}
    except Exception as error:
        return {"error": str(error)}


def collect_minio_context(endpoint_url: str) -> dict[str, Any]:
    try:
        import boto3
    except Exception as error:
        return {"error": f"boto3 unavailable: {error}"}
    access_key = os.getenv("MINIO_ROOT_USER") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD") or os.getenv("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        return {"error": "MinIO credentials are not configured in environment"}
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        buckets = [bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])]
        bucket_summaries = []
        for bucket in buckets:
            paginator = client.get_paginator("list_objects_v2")
            count = 0
            size = 0
            samples = []
            for page in paginator.paginate(Bucket=bucket, PaginationConfig={"MaxItems": 200}):
                for item in page.get("Contents", []):
                    count += 1
                    size += int(item.get("Size", 0))
                    if len(samples) < 10:
                        samples.append({"key": item.get("Key"), "size": item.get("Size")})
            bucket_summaries.append({"bucket": bucket, "sampled_object_count": count, "sampled_bytes": size, "sample_keys": samples})
        return {"buckets": bucket_summaries}
    except Exception as error:
        return {"error": str(error)}


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: int = 8) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


def redact_log_line(line: str) -> str:
    redacted = line
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]" if len(match.groups()) >= 3 else "[REDACTED]", redacted)
    return redacted


def is_log_issue_line(line: str) -> bool:
    lower = line.lower()
    ignored_fragments = [
        "# dags # errors",
        "# errors last duration",
        "errors: 0",
        "0 errors",
    ]
    if any(fragment in lower for fragment in ignored_fragments):
        return False
    return any(term in lower for term in ["error", "exception", "traceback", "failed", "warning", "warn"])


def strip_docker_log_headers(payload: bytes) -> str:
    chunks = []
    index = 0
    while index + 8 <= len(payload):
        stream_type = payload[index]
        size = int.from_bytes(payload[index + 4 : index + 8], "big")
        if stream_type not in {0, 1, 2} or size < 0 or index + 8 + size > len(payload):
            break
        chunks.append(payload[index + 8 : index + 8 + size])
        index += 8 + size
    if chunks:
        return b"".join(chunks).decode("utf-8", errors="replace")
    return payload.decode("utf-8", errors="replace")


def docker_get(socket_path: str, path: str) -> tuple[int, bytes]:
    connection = UnixSocketHTTPConnection(socket_path)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def collect_service_logs(socket_path: str, tail: int) -> dict[str, Any]:
    if not Path(socket_path).exists():
        return {"error": f"Docker socket not found at {socket_path}"}
    logs = []
    for name in LOG_CONTAINERS:
        path = f"/containers/{name}/logs?stdout=1&stderr=1&timestamps=1&tail={max(1, tail)}"
        try:
            status, payload = docker_get(socket_path, path)
            if status >= 400:
                logs.append({"container": name, "error": payload.decode("utf-8", errors="replace")[:400]})
                continue
            text = strip_docker_log_headers(payload)
            lines = [redact_log_line(line) for line in text.splitlines() if line.strip()]
            logs.append({"container": name, "tail_lines": lines[-tail:]})
        except Exception as error:
            logs.append({"container": name, "error": str(error)})
    return {"containers": logs, "tail": tail}


def compact_simulation_event(event: dict[str, Any]) -> dict[str, Any]:
    source = event.get("source_event", {})
    response = event.get("api_response", {})
    return {
        "sequence": event.get("sequence"),
        "flight_date": source.get("flight_date"),
        "origin": source.get("origin"),
        "destination": source.get("destination"),
        "actual_label": source.get("label"),
        "prediction": response.get("prediction"),
        "risk_band": response.get("risk_band"),
        "disruption_probability": response.get("disruption_probability"),
    }


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    simulation_events = read_jsonl_tail(args.simulation_jsonl, args.max_events)
    return {
        "project": "Aviation Weather Disruption Intelligence Platform",
        "data_sources": "Downloaded ARCO-ERA5 airport-hour weather and official BTS on-time flight outcomes",
        "model": "Spark MLlib balanced logistic regression registered in MLflow and served by BentoML",
        "dataset_streaming_demo": "Gold feature rows from the downloaded lakehouse are published to Kafka for replay evidence and separately scored by the API",
        "latest_simulation_events": [compact_simulation_event(event) for event in simulation_events],
        "codebase": collect_codebase_context(args.repo_root, args.max_context_files, args.max_file_chars),
        "grafana_dashboards": collect_grafana_dashboard_context(args.repo_root),
        "mlflow": collect_mlflow_context(args.mlflow_url),
        "airflow": collect_airflow_context(args.airflow_url),
        "spark": collect_spark_context(args.spark_master_url),
        "kafka": collect_kafka_context(args.kafka_bootstrap),
        "minio": collect_minio_context(args.minio_url),
        "service_logs": collect_service_logs(args.docker_socket, args.log_tail),
        "prometheus_metrics": {
            "prediction_requests_by_source": prometheus_query(
                args.prometheus_url,
                "sum by (source, risk_band) (aviation_prediction_requests_by_source_total)",
            ),
            "failed_api_requests": prometheus_query(
                args.prometheus_url,
                'sum(bentoml_service_request_total{http_response_code!="200"})',
            ),
            "p95_latency_seconds": prometheus_query(
                args.prometheus_url,
                "histogram_quantile(0.95, sum(rate(aviation_prediction_latency_seconds_bucket[1m])) by (le))",
            ),
        },
        "known_limitations": [
            "The current deployed model uses weather/time/route-distance features.",
            "The streaming demonstration replays downloaded historical Gold rows from the lakehouse.",
            "The LLM assistant explains project evidence but is not part of model training or prediction.",
        ],
    }


def call_gemini(
    *,
    api_key: str,
    model: str,
    question: str,
    context: dict[str, Any],
    temperature: float,
    max_tokens: int,
) -> str:
    prompt = (
        f"{DEFAULT_SYSTEM_PROMPT}\n\n"
        "Project context JSON:\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}\n\n"
        f"Question: {question}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    response = requests.post(
        GEMINI_GENERATE_CONTENT_URL.format(model=model),
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    parts = data["candidates"][0]["content"].get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    return sanitize_answer(text)


def fallback_answer(question: str, context: dict[str, Any]) -> str:
    simulation = context["latest_simulation_events"][-1] if context["latest_simulation_events"] else {}
    question_lower = question.lower()
    if "file" in question_lower or "implement" in question_lower or "code" in question_lower:
        files = [
            "api/simulate_gold_stream_predict.py: reads historical Gold rows, publishes Kafka replay evidence, calls the prediction API, and writes JSONL.",
            "api/service.py: BentoML prediction service endpoint.",
            "api/scoring.py: model loading and numeric scoring helpers.",
            "spark_jobs/call_api_with_gold_sample.py: sends a historical Gold-row feature vector to the API.",
            "spark_jobs/build_gold_features.py: builds the model feature table consumed by replay and training.",
            "ml/train_register_model.py: trains/registers the selected model in MLflow.",
            "dashboards/aviation-final-demo-dashboard.json: merged Grafana dashboard for API and dataset replay metrics.",
            "notebooks/final/10_dataset_streaming_demo.ipynb: runnable final presentation flow.",
        ]
        return "\n".join(files)
    if "status" in question_lower or "mlflow" in question_lower or "kafka" in question_lower or "minio" in question_lower:
        kafka = context.get("kafka", {})
        minio = context.get("minio", {})
        spark = context.get("spark", {})
        grafana = context.get("grafana_dashboards", {})
        mlflow = context.get("mlflow", {})
        airflow = context.get("airflow", {})
        buckets = [
            {
                "bucket": bucket.get("bucket"),
                "sampled_object_count": bucket.get("sampled_object_count"),
                "sampled_gib": round(float(bucket.get("sampled_bytes", 0)) / (1024**3), 2),
            }
            for bucket in minio.get("buckets", [])
        ] if isinstance(minio, dict) else []
        spark_summary = {
            "status": spark.get("status"),
            "alive_workers": spark.get("alive_workers"),
            "cores": spark.get("cores"),
            "active_apps": len(spark.get("active_apps", [])) if isinstance(spark.get("active_apps"), list) else "unavailable",
            "completed_apps": [
                {
                    "name": app.get("name"),
                    "state": app.get("state"),
                    "duration_ms": app.get("duration"),
                }
                for app in spark.get("completed_apps", [])[:5]
            ] if isinstance(spark.get("completed_apps"), list) else [],
        } if isinstance(spark, dict) and "error" not in spark else spark.get("error", "unavailable")
        return (
            "Current collected status summary:\n"
            f"- MLflow: registered model payload keys={list(mlflow.get('registered_models', {}).keys()) if isinstance(mlflow.get('registered_models'), dict) else 'unavailable'}.\n"
            f"- Kafka: topics={kafka.get('topics', kafka.get('error', 'unavailable'))}.\n"
            f"- MinIO: buckets={buckets or minio.get('error', 'unavailable')}.\n"
            f"- Spark: {spark_summary}.\n"
            f"- Airflow: health={airflow.get('health', 'unavailable')}.\n"
            f"- Grafana dashboards: {[item.get('title') for item in grafana.get('dashboards', [])]}."
        )
    if "log" in question_lower or "error" in question_lower:
        service_logs = context.get("service_logs", {})
        summaries = []
        for item in service_logs.get("containers", []) if isinstance(service_logs, dict) else []:
            lines = item.get("tail_lines", [])
            error_lines = [line for line in lines if is_log_issue_line(line)]
            summaries.append(
                {
                    "container": item.get("container"),
                    "errors_or_warnings": error_lines[-5:],
                    "line_count": len(lines),
                    "collector_error": item.get("error"),
                }
            )
        return "Recent service log summary:\n" + json.dumps(summaries, indent=2)
    return sanitize_answer(
        "GEMINI_API_KEY is not configured, so this is the local fallback summary.\\n\\n"
        f"Question: {question}\\n\\n"
        f"Dataset streaming replay status: route={simulation.get('origin')}->{simulation.get('destination')}, "
        f"risk={simulation.get('risk_band')}, probability={simulation.get('disruption_probability')}.\\n"
        "The deployed model is working through BentoML, and Prometheus/Grafana track request sources, latency, failures, and risk bands."
    )


def answer_question(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv()
    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    context = build_context(args)
    if api_key:
        try:
            answer = call_gemini(
                api_key=api_key,
                model=args.model,
                question=args.question,
                context=context,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            provider = "gemini"
        except Exception as error:
            answer = fallback_answer(args.question, context) + f"\n\n[Gemini unavailable: {error}]"
            provider = "local_fallback"
    else:
        answer = fallback_answer(args.question, context)
        provider = "local_fallback"
    return {"provider": provider, "model": args.model, "question": args.question, "answer": answer, "context": context}


def main() -> None:
    result = answer_question(parse_args())
    print(json.dumps({key: result[key] for key in ["provider", "model", "question", "answer"]}, indent=2))


if __name__ == "__main__":
    main()
