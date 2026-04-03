from __future__ import annotations

from pyspark.sql import Window, functions as F

from src.common.contracts import BRONZE_TABLE_PATH, SILVER_TABLE_PATH
from src.common.logging_utils import configure_logging
from src.common.spark import create_spark_session


def main() -> None:
    configure_logging()
    spark = create_spark_session("build-silver")
    df = spark.read.format("delta").load(BRONZE_TABLE_PATH)
    silver = (
        df.withColumn("event_date", F.to_date("event_time"))
        .withColumn("event_hour", F.hour("event_time"))
        .withColumn("is_weekend", F.when(F.dayofweek("event_time").isin([1, 7]), 1).otherwise(0))
        .withColumn("temperature_c", F.round("temperature_c", 2))
        .withColumn("wind_speed_kts", F.round("wind_speed_kts", 2))
        .withColumn("visibility_miles", F.greatest(F.col("visibility_miles"), F.lit(0.1)))
        .withColumn("precip_mm", F.greatest(F.col("precip_mm"), F.lit(0.0)))
    )
    (
        silver.write.format("delta")
        .mode("overwrite")
        .partitionBy("airport_code")
        .option("overwriteSchema", "true")
        .save(SILVER_TABLE_PATH)
    )
    print(f"silver rows={silver.count()}")
    spark.stop()


if __name__ == "__main__":
    main()
