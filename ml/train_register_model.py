"""Train, export, log, and register a balanced Spark MLlib disruption model."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import mlflow
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from pyspark.sql import functions as F

from spark_jobs.build_gold_features import NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


MODEL_NAME = "aviation-disruption-balanced-logistic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1, choices=range(1, 13))
    parser.add_argument("--output", default="/workspace/models/final_numeric_logistic_model.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    spark = create_spark_session("train-register-balanced-logistic", settings)
    source = s3a_uri(
        settings.lakehouse_bucket,
        f"gold/training_features/year={args.year}/month={args.month:02d}",
    )

    try:
        gold_df = spark.read.parquet(source)
        assembler = VectorAssembler(inputCols=NUMERIC_FEATURES, outputCol="features")
        model_df = assembler.transform(gold_df).select("flight_date", "features", "label")
        train_df = model_df.filter(F.dayofmonth("flight_date") <= 24)
        test_df = model_df.filter(F.dayofmonth("flight_date") > 24)
        counts = {row["label"]: row["count"] for row in train_df.groupBy("label").count().collect()}
        positive_weight = counts[0.0] / counts[1.0]
        weighted_train_df = train_df.withColumn(
            "class_weight",
            F.when(F.col("label") == 1.0, F.lit(positive_weight)).otherwise(F.lit(1.0)),
        )
        classifier = LogisticRegression(
            featuresCol="features",
            labelCol="label",
            weightCol="class_weight",
            maxIter=50,
            regParam=0.01,
        )
        model = classifier.fit(weighted_train_df)
        predictions = model.transform(test_df)
        auc = BinaryClassificationEvaluator(labelCol="label", metricName="areaUnderROC").evaluate(
            predictions
        )
        confusion = predictions.agg(
            F.sum(F.when((F.col("label") == 1) & (F.col("prediction") == 1), 1).otherwise(0)).alias("tp"),
            F.sum(F.when((F.col("label") == 0) & (F.col("prediction") == 0), 1).otherwise(0)).alias("tn"),
            F.sum(F.when((F.col("label") == 0) & (F.col("prediction") == 1), 1).otherwise(0)).alias("fp"),
            F.sum(F.when((F.col("label") == 1) & (F.col("prediction") == 0), 1).otherwise(0)).alias("fn"),
        ).first().asDict()
        tp, fp, fn = confusion["tp"], confusion["fp"], confusion["fn"]
        payload = {
            "model_name": MODEL_NAME,
            "model_type": "spark_mllib_balanced_logistic_regression",
            "feature_names": NUMERIC_FEATURES,
            "coefficients": list(model.coefficients),
            "intercept": model.intercept,
            "threshold": model.getThreshold(),
            "training_scope": f"{args.year}-{args.month:02d}-01_to_24",
            "test_scope": f"{args.year}-{args.month:02d}-25_to_end",
            "positive_weight": positive_weight,
            "metrics": {
                "auc": auc,
                **confusion,
                "positive_precision": tp / max(tp + fp, 1),
                "positive_recall": tp / max(tp + fn, 1),
            },
        }
        output.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
        mlflow.set_experiment("aviation_disruption_final_model")
        with mlflow.start_run(run_name="balanced_logistic_chronological_split") as run:
            mlflow.log_params(
                {
                    "model_type": payload["model_type"],
                    "training_scope": payload["training_scope"],
                    "test_scope": payload["test_scope"],
                    "positive_weight": positive_weight,
                    "feature_count": len(NUMERIC_FEATURES),
                }
            )
            mlflow.log_metrics(payload["metrics"])
            mlflow.log_artifact(str(output), artifact_path="model")
            artifact_uri = f"{run.info.artifact_uri}/model/{output.name}"
            client = mlflow.tracking.MlflowClient()
            try:
                client.create_registered_model(MODEL_NAME)
            except mlflow.exceptions.MlflowException:
                pass
            version = client.create_model_version(MODEL_NAME, artifact_uri, run.info.run_id)
            client.set_registered_model_alias(MODEL_NAME, "staging", version.version)
            client.set_registered_model_alias(MODEL_NAME, "production", version.version)
            print(f"Registered {MODEL_NAME} version {version.version} as staging and production")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
