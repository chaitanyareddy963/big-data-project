"""BentoML REST service for aviation disruption risk scoring."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import bentoml
from prometheus_client import Counter, Histogram

from api.scoring import linear_probability


REQUESTS = Counter("aviation_prediction_requests_total", "Prediction requests", ["risk_band"])
LATENCY = Histogram("aviation_prediction_latency_seconds", "Prediction latency")


@bentoml.service(name="aviation_disruption_api", traffic={"timeout": 10})
class AviationDisruptionService:
    def __init__(self) -> None:
        model_path = Path(os.getenv("AVIATION_MODEL_PATH", "/models/final_numeric_logistic_model.json"))
        self.model = json.loads(model_path.read_text())

    @bentoml.api
    def predict(self, features: dict[str, float]) -> dict[str, float | int | str]:
        started = time.perf_counter()
        probability = linear_probability(features, self.model)
        prediction = int(probability >= float(self.model.get("threshold", 0.5)))
        risk_band = "high" if prediction else "low"
        REQUESTS.labels(risk_band=risk_band).inc()
        LATENCY.observe(time.perf_counter() - started)
        return {
            "prediction": prediction,
            "disruption_probability": round(probability, 6),
            "risk_band": risk_band,
            "model_name": self.model["model_name"],
        }
