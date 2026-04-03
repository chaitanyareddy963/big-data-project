from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np

from src.common.contracts import FEATURE_COLUMNS
from src.common.io import download_bytes, upload_json


def sigmoid(value):
    return 1.0 / (1.0 + np.exp(-value))


def export_model_metadata(model, uri_prefix: str, extra_metadata: dict | None = None) -> dict:
    metadata = {
        "model_name": "disruption-risk-local",
        "feature_columns": FEATURE_COLUMNS,
        "coefficients": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "serving_uri": uri_prefix.rstrip("/"),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    upload_json(metadata, f"{uri_prefix.rstrip('/')}/metadata.json")
    return metadata


def load_model_metadata(uri_prefix: str) -> dict:
    return json.loads(download_bytes(f"{uri_prefix.rstrip('/')}/metadata.json").decode("utf-8"))


def score_with_metadata(features, metadata: dict) -> tuple[float, int]:
    vector = np.array([features[name] for name in metadata["feature_columns"]], dtype=float)
    score = float(sigmoid(np.dot(vector, np.array(metadata["coefficients"])) + metadata["intercept"]))
    return score, int(score >= 0.5)


def save_model_local(model, path: str) -> None:
    joblib.dump(model, path)
