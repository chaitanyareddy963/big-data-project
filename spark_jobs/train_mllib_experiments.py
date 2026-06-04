"""Train leakage-conscious Spark MLlib baselines on Gold flight-weather data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression, RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.sql import DataFrame

from spark_jobs.build_gold_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--output", default="data/local_cache/model_metrics/january_2024_mllib.json")
    return parser.parse_args()


def build_pipeline(classifier) -> Pipeline:
    indexers = [
        StringIndexer(inputCol=column, outputCol=f"{column}_index", handleInvalid="keep")
        for column in CATEGORICAL_FEATURES
    ]
    encoded_columns = [f"{column}_encoded" for column in CATEGORICAL_FEATURES]
    encoder = OneHotEncoder(
        inputCols=[f"{column}_index" for column in CATEGORICAL_FEATURES],
        outputCols=encoded_columns,
        handleInvalid="keep",
    )
    assembler = VectorAssembler(
        inputCols=NUMERIC_FEATURES + encoded_columns,
        outputCol="features",
        handleInvalid="error",
    )
    return Pipeline(stages=[*indexers, encoder, assembler, classifier])


def evaluate(predictions: DataFrame) -> dict[str, float]:
    binary = BinaryClassificationEvaluator(
        labelCol="label",
        rawPredictionCol="rawPrediction",
        metricName="areaUnderROC",
    )
    accuracy = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy"
    )
    f1 = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="f1"
    )
    precision = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="weightedPrecision"
    )
    recall = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="weightedRecall"
    )
    confusion = (
        predictions.agg(
            F.sum(
                F.when((F.col("label") == 1.0) & (F.col("prediction") == 1.0), 1).otherwise(0)
            ).alias("true_positive"),
            F.sum(
                F.when((F.col("label") == 0.0) & (F.col("prediction") == 0.0), 1).otherwise(0)
            ).alias("true_negative"),
            F.sum(
                F.when((F.col("label") == 0.0) & (F.col("prediction") == 1.0), 1).otherwise(0)
            ).alias("false_positive"),
            F.sum(
                F.when((F.col("label") == 1.0) & (F.col("prediction") == 0.0), 1).otherwise(0)
            ).alias("false_negative"),
        )
        .first()
        .asDict()
    )
    true_positive = int(confusion["true_positive"])
    false_positive = int(confusion["false_positive"])
    false_negative = int(confusion["false_negative"])
    positive_precision = true_positive / max(true_positive + false_positive, 1)
    positive_recall = true_positive / max(true_positive + false_negative, 1)

    return {
        "auc": float(binary.evaluate(predictions)),
        "accuracy": float(accuracy.evaluate(predictions)),
        "f1": float(f1.evaluate(predictions)),
        "weighted_precision": float(precision.evaluate(predictions)),
        "weighted_recall": float(recall.evaluate(predictions)),
        **{key: int(value) for key, value in confusion.items()},
        "positive_precision": positive_precision,
        "positive_recall": positive_recall,
    }


def main() -> None:
    args = parse_args()
    output = Path(args.output).resolve()
    settings = load_settings()
    spark = create_spark_session("train-january-mllib-experiments", settings)
    source = s3a_uri(
        settings.lakehouse_bucket,
        f"gold/training_features/year={args.year}/month={args.month:02d}",
    )

    try:
        gold_df = spark.read.parquet(source).cache()
        train_df, test_df = gold_df.randomSplit([0.8, 0.2], seed=42)
        train_count = train_df.count()
        test_count = test_df.count()
        print(f"Training rows: {train_count}")
        print(f"Test rows: {test_count}")
        train_df.groupBy("label").count().orderBy("label").show()

        experiments = [
            (
                "logistic_regression_reg_0_01",
                LogisticRegression(
                    labelCol="label",
                    featuresCol="features",
                    maxIter=30,
                    regParam=0.01,
                ),
            ),
            (
                "logistic_regression_reg_0_05",
                LogisticRegression(
                    labelCol="label",
                    featuresCol="features",
                    maxIter=30,
                    regParam=0.05,
                ),
            ),
            (
                "logistic_regression_reg_0_10",
                LogisticRegression(
                    labelCol="label",
                    featuresCol="features",
                    maxIter=30,
                    regParam=0.10,
                ),
            ),
            (
                "random_forest_trees_20_depth_6",
                RandomForestClassifier(
                    labelCol="label",
                    featuresCol="features",
                    numTrees=20,
                    maxDepth=6,
                    seed=42,
                ),
            ),
            (
                "random_forest_trees_40_depth_8",
                RandomForestClassifier(
                    labelCol="label",
                    featuresCol="features",
                    numTrees=40,
                    maxDepth=8,
                    seed=42,
                ),
            ),
        ]

        results = []
        for name, classifier in experiments:
            print(f"Training: {name}")
            model = build_pipeline(classifier).fit(train_df)
            metrics = evaluate(model.transform(test_df))
            result = {
                "run_name": name,
                "year": args.year,
                "month": args.month,
                "train_rows": train_count,
                "test_rows": test_count,
                **metrics,
            }
            results.append(result)
            print(json.dumps(result, indent=2))

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2) + "\n")
        print(f"Wrote experiment metrics: {output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
