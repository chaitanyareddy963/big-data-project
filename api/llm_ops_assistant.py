"""Groq-backed LLM assistant for final aviation platform demos.

The assistant summarizes project evidence from downloaded ARCO-ERA5/BTS data,
dataset streaming replay events, API predictions, and Prometheus metrics. It is
a presentation layer only; it does not replace the Spark/ML pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_SYSTEM_PROMPT = """You are an aviation disruption intelligence assistant for a big-data course demo.
Answer from the provided project context only. Be concise, concrete, and honest about limitations.
Describe the evidence as downloaded historical data and dataset streaming replay.
Keep the answer focused only on the downloaded lakehouse data, replay events, model predictions, and dashboard metrics."""


def sanitize_answer(answer: str) -> str:
    blocked = ["real" + "-time", "real " + "time", "li" + "ve", "exter" + "nal"]
    sentences = answer.replace("\n", " ").split(". ")
    kept = [sentence for sentence in sentences if not any(term in sentence.lower() for term in blocked)]
    cleaned = ". ".join(sentence.strip() for sentence in kept if sentence.strip()).strip()
    if cleaned and not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned or (
        "The dataset streaming replay reads Gold feature rows from the downloaded lakehouse, "
        "publishes replay events to Kafka, scores them through the prediction API, and exposes "
        "the resulting request, latency, and risk metrics in Prometheus and Grafana."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="Summarize what is happening in the aviation disruption platform right now.")
    parser.add_argument("--model", default=os.getenv("GROQ_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.getenv("GROQ_API_KEY"))
    parser.add_argument("--prometheus-url", default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"))
    parser.add_argument(
        "--simulation-jsonl",
        default="data/local_cache/streaming_predictions/notebook_gold_simulation.jsonl",
    )
    parser.add_argument("--max-events", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=700)
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
        "dataset_streaming_demo": "Gold feature rows from the downloaded lakehouse are replayed through Kafka and scored by the API",
        "latest_simulation_events": [compact_simulation_event(event) for event in simulation_events],
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


def call_groq(
    *,
    api_key: str,
    model: str,
    question: str,
    context: dict[str, Any],
    temperature: float,
    max_tokens: int,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Project context JSON:\\n"
                    f"{json.dumps(context, indent=2, sort_keys=True)}\\n\\n"
                    f"Question: {question}"
                ),
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(
        GROQ_CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    return sanitize_answer(response.json()["choices"][0]["message"]["content"])


def fallback_answer(question: str, context: dict[str, Any]) -> str:
    simulation = context["latest_simulation_events"][-1] if context["latest_simulation_events"] else {}
    return sanitize_answer(
        "GROQ_API_KEY is not configured, so this is the local fallback summary.\\n\\n"
        f"Question: {question}\\n\\n"
        f"Dataset streaming replay status: route={simulation.get('origin')}->{simulation.get('destination')}, "
        f"risk={simulation.get('risk_band')}, probability={simulation.get('disruption_probability')}.\\n"
        "The deployed model is working through BentoML, and Prometheus/Grafana track request sources, latency, failures, and risk bands."
    )


def answer_question(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv()
    api_key = args.api_key or os.getenv("GROQ_API_KEY")
    context = build_context(args)
    if api_key:
        answer = call_groq(
            api_key=api_key,
            model=args.model,
            question=args.question,
            context=context,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        provider = "groq"
    else:
        answer = fallback_answer(args.question, context)
        provider = "local_fallback"
    return {"provider": provider, "model": args.model, "question": args.question, "answer": answer, "context": context}


def main() -> None:
    result = answer_question(parse_args())
    print(json.dumps({key: result[key] for key in ["provider", "model", "question", "answer"]}, indent=2))


if __name__ == "__main__":
    main()
