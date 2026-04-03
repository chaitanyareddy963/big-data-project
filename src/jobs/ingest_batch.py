from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import functions as F

from src.common.contracts import BRONZE_TABLE_PATH, RAW_BUCKET
from src.common.io import upload_file
from src.common.logging_utils import configure_logging
from src.common.schemas import BRONZE_SCHEMA
from src.common.spark import create_spark_session


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    object_key = f"{input_path.stem}/{input_path.name}"
    upload_file(input_path, RAW_BUCKET, object_key)

    spark = create_spark_session("ingest-batch")
    df = (
        spark.read.option("header", True)
        .schema(BRONZE_SCHEMA)
        .csv(str(input_path))
        .withColumn("event_time", F.to_timestamp("event_time"))
        .withColumn("ingest_time", F.lit(datetime.now(timezone.utc).isoformat()))
    )
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(BRONZE_TABLE_PATH)
    )
    print(f"bronze rows={df.count()}")
    spark.stop()


if __name__ == "__main__":
    main()
