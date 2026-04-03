from __future__ import annotations

import json
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from src.common.config import AppConfig
from src.common.contracts import FEATURE_COLUMNS, GOLD_EXPORT_PREFIX, MODEL_EXPORT_URI, MODEL_NAME
from src.common.io import get_s3_client, upload_file
from src.common.logging_utils import configure_logging
from src.common.modeling import export_model_metadata, save_model_local


def load_gold_export(config: AppConfig) -> pd.DataFrame:
    client = get_s3_client(config)
    response = client.list_objects_v2(Bucket="gold", Prefix=GOLD_EXPORT_PREFIX)
    keys = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].endswith(".parquet")]
    if not keys:
        raise RuntimeError("No gold export parquet found. Run build-gold first.")
    tables = []
    for key in keys:
        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            client.download_file("gold", key, tmp.name)
            tables.append(pd.read_parquet(tmp.name))
    return pd.concat(tables, ignore_index=True)


def main() -> None:
    configure_logging()
    config = AppConfig()
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment("aviation-disruption-mvp")

    df = load_gold_export(config)
    X = df[FEATURE_COLUMNS]
    y = df["disruption_label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = LogisticRegression(max_iter=500)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    with mlflow.start_run(run_name="baseline-logreg") as run:
        mlflow.log_param("model_type", "logistic_regression")
        mlflow.log_param("feature_count", len(FEATURE_COLUMNS))
        mlflow.log_metric("accuracy", accuracy_score(y_test, pred))
        mlflow.log_metric("roc_auc", roc_auc_score(y_test, proba))

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.joblib"
            features_path = Path(tmpdir) / "feature_columns.json"
            save_model_local(model, str(model_path))
            features_path.write_text(json.dumps(FEATURE_COLUMNS, indent=2))
            mlflow.log_artifact(str(model_path), artifact_path="model")
            mlflow.log_artifact(str(features_path), artifact_path="metadata")

            bucket = "mlflow"
            export_prefix = "serving/current"
            client = get_s3_client(config)
            client.upload_file(str(model_path), bucket, f"{export_prefix}/model.joblib")
            export_model_metadata(model, MODEL_EXPORT_URI.rstrip("/"))

        mlflow.set_tag("model_name", MODEL_NAME)
        print(f"run_id={run.info.run_id}")


if __name__ == "__main__":
    main()
