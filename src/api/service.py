from __future__ import annotations

import bentoml
import pandas as pd
from bentoml.io import JSON

from src.common.contracts import FEATURE_COLUMNS, MODEL_NAME
from src.common.schemas import PredictionRequest, PredictionResponse

model_ref = bentoml.sklearn.get(MODEL_NAME)
model = bentoml.sklearn.load_model(MODEL_NAME)
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
        model_version=model_ref.tag.version or "latest",
    )
