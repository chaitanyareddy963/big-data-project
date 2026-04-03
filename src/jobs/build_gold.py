from __future__ import annotations

from pyspark.sql import Window, functions as F

from src.common.contracts import GOLD_BUCKET, GOLD_EXPORT_PREFIX, GOLD_TABLE_PATH, SILVER_TABLE_PATH
from src.common.logging_utils import configure_logging
from src.common.spark import create_spark_session


def main() -> None:
    configure_logging()
    spark = create_spark_session("build-gold")
    df = spark.read.format("delta").load(SILVER_TABLE_PATH)
    window = Window.partitionBy("airport_code").orderBy("event_time").rowsBetween(-5, 0)
    gold = (
        df.withColumn("rolling_avg_dep_delay_6h", F.round(F.avg("avg_dep_delay_min").over(window), 3))
        .withColumn("rolling_avg_arr_delay_6h", F.round(F.avg("avg_arr_delay_min").over(window), 3))
        .withColumn("rolling_max_wind_6h", F.round(F.max("wind_speed_kts").over(window), 3))
        .withColumn("rolling_total_precip_6h", F.round(F.sum("precip_mm").over(window), 3))
        .withColumn(
            "delay_pressure_index",
            F.round((F.col("avg_dep_delay_min") + F.col("avg_arr_delay_min")) / F.col("pressure_hpa"), 6),
        )
    )
    (
        gold.write.format("delta")
        .mode("overwrite")
        .partitionBy("airport_code")
        .option("overwriteSchema", "true")
        .save(GOLD_TABLE_PATH)
    )
    (
        gold.coalesce(1)
        .write.mode("overwrite")
        .parquet(f"s3a://{GOLD_BUCKET}/{GOLD_EXPORT_PREFIX}")
    )
    print(f"gold rows={gold.count()}")
    spark.stop()


if __name__ == "__main__":
    main()
