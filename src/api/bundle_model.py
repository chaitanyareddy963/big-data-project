from __future__ import annotations

import tempfile
from pathlib import Path

import bentoml
import joblib

from src.common.config import AppConfig
from src.common.contracts import MODEL_NAME
from src.common.io import download_bytes


def main() -> None:
    config = AppConfig()
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model.joblib"
        model_path.write_bytes(download_bytes(f"{config.model_export_uri.rstrip('/')}/model.joblib"))
        model = joblib.load(model_path)
        bentoml.sklearn.save_model(MODEL_NAME, model)
        print(f"bundled {MODEL_NAME}")


if __name__ == "__main__":
    main()
