"""BentoML REST service for aviation disruption risk scoring."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import bentoml
from prometheus_client import Counter, Gauge, Histogram

from api.scoring import linear_probability


REQUESTS = Counter("aviation_prediction_requests_total", "Prediction requests", ["risk_band"])
REQUESTS_BY_SOURCE = Counter(
    "aviation_prediction_requests_by_source_total",
    "Prediction requests by source and risk band",
    ["source", "risk_band"],
)
ERRORS = Counter("aviation_prediction_errors_total", "Prediction request errors")
LATENCY = Histogram("aviation_prediction_latency_seconds", "Prediction latency")
PROBABILITY = Histogram(
    "aviation_disruption_probability",
    "Predicted disruption probability",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
LATEST_PROBABILITY = Gauge(
    "aviation_latest_disruption_probability",
    "Most recent disruption probability by predicted risk band",
    ["risk_band"],
)
LATEST_SOURCE_PROBABILITY = Gauge(
    "aviation_latest_disruption_probability_by_source",
    "Most recent disruption probability by request source and risk band",
    ["source", "risk_band"],
)


def clean_source(value: str | None) -> str:
    if not value:
        return "unknown"
    cleaned = "".join(character if character.isalnum() or character in ("_", "-") else "_" for character in value)
    return cleaned[:64] or "unknown"


@bentoml.service(name="aviation_disruption_api", traffic={"timeout": 10})
class AviationDisruptionService:
    def __init__(self) -> None:
        model_path = Path(os.getenv("AVIATION_MODEL_PATH", "/models/final_numeric_logistic_model.json"))
        self.model = json.loads(model_path.read_text())

    @bentoml.api
    def predict(self, features: dict[str, float], source: str = "direct_api") -> dict[str, float | int | str]:
        started = time.perf_counter()
        try:
            source_label = clean_source(source)
            probability = linear_probability(features, self.model)
            prediction = int(probability >= float(self.model.get("threshold", 0.5)))
            risk_band = "high" if prediction else "low"
            REQUESTS.labels(risk_band=risk_band).inc()
            REQUESTS_BY_SOURCE.labels(source=source_label, risk_band=risk_band).inc()
            PROBABILITY.observe(probability)
            LATEST_PROBABILITY.labels(risk_band=risk_band).set(probability)
            LATEST_SOURCE_PROBABILITY.labels(source=source_label, risk_band=risk_band).set(probability)
            return {
                "prediction": prediction,
                "disruption_probability": round(probability, 6),
                "risk_band": risk_band,
                "model_name": self.model["model_name"],
                "source": source_label,
            }
        except Exception:
            ERRORS.inc()
            raise
        finally:
            LATENCY.observe(time.perf_counter() - started)
