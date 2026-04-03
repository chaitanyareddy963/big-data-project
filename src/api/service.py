from __future__ import annotations

import bentoml
import pandas as pd
from bentoml.io import JSON

from src.common.config import AppConfig
from src.common.contracts import FEATURE_COLUMNS, MODEL_NAME
from src.common.modeling import load_model_metadata
from src.common.schemas import PredictionRequest, PredictionResponse

model_ref = bentoml.sklearn.get(MODEL_NAME)
model = bentoml.sklearn.load_model(MODEL_NAME)
serving_metadata = load_model_metadata(AppConfig().model_export_uri)
svc = bentoml.Service("aviation_disruption_service")


@svc.api(input=JSON(pydantic_model=PredictionRequest), output=JSON(pydantic_model=PredictionResponse))
async def predict(payload: PredictionRequest) -> PredictionResponse:
    frame = pd.DataFrame([[getattr(payload, name) for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    score = float(model.predict_proba(frame)[0][1])
    label = int(score >= 0.5)
    return PredictionResponse(
        airport_code=payload.airport_code,
        event_time=payload.event_time,
        risk_score=score,
        risk_label=label,
        model_version=serving_metadata.get("run_id") or model_ref.tag.version or "latest",
    )


@svc.api(input=JSON(), output=JSON())
async def health(_: dict | None = None) -> dict:
    return {
        "status": "ok",
        "service": "aviation_disruption_service",
        "model_name": serving_metadata.get("model_name", MODEL_NAME),
        "model_version": serving_metadata.get("run_id") or model_ref.tag.version or "latest",
        "exported_at": serving_metadata.get("exported_at"),
        "feature_count": len(serving_metadata.get("feature_columns", FEATURE_COLUMNS)),
    }
