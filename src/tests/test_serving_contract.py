from src.common.contracts import FEATURE_COLUMNS, MODEL_EXPORT_URI, MODEL_NAME
from src.common.schemas import PredictionResponse


def test_model_export_uri_is_stable_serving_path():
    assert MODEL_EXPORT_URI == "s3://mlflow/serving/current/"


def test_prediction_response_fields():
    payload = PredictionResponse(
        airport_code="ATL",
        event_time="2024-01-01T00:00:00Z",
        risk_score=0.73,
        risk_label=1,
        model_version="demo-run-id",
    )
    assert payload.model_version == "demo-run-id"
    assert payload.risk_label in {0, 1}


def test_feature_columns_are_unique():
    assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS))
    assert MODEL_NAME == "disruption-risk-local"
