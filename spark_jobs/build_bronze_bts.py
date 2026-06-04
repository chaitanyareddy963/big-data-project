"""Convert one BTS monthly ZIP archive from MinIO into cleaned Bronze Parquet."""

from __future__ import annotations

import argparse
import csv
import tempfile
import zipfile
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from spark_jobs.common import create_s3_client, create_spark_session, load_settings, s3a_uri


SELECTED_COLUMNS = [
    "Year",
    "Month",
    "FlightDate",
    "Reporting_Airline",
    "Flight_Number_Reporting_Airline",
    "OriginAirportID",
    "Origin",
    "DestAirportID",
    "Dest",
    "CRSDepTime",
    "DepDelayMinutes",
    "ArrDelayMinutes",
    "ArrDel15",
    "Cancelled",
    "Diverted",
    "Distance",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    parser.add_argument("--keep-extracted-csv", action="store_true")
    return parser.parse_args()


def archive_name(year: int, month: int) -> str:
    return f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"


def csv_schema(csv_path: Path) -> StructType:
    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        header = next(csv.reader(csv_file))
    fields = [StructField(name, StringType(), True) for name in header if name]
    return StructType(fields)


def extract_csv(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise RuntimeError(f"Expected exactly one CSV in {zip_path}, found: {csv_members}")
        archive.extract(csv_members[0], destination)
        return destination / csv_members[0]


def main() -> None:
    args = parse_args()
    settings = load_settings()
    s3 = create_s3_client(settings)
    spark = create_spark_session("build-bronze-bts-on-time", settings)
    name = archive_name(args.year, args.month)
    key = f"bts_on_time/raw_zip/{name}"
    extracted_key = f"bts_on_time/extracted_csv/year={args.year}/month={args.month:02d}/flights.csv"
    destination = s3a_uri(
        settings.lakehouse_bucket,
        f"bronze/bts_on_time/year={args.year}/month={args.month:02d}",
    )

    try:
        with tempfile.TemporaryDirectory(prefix="bts-on-time-") as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / name
            s3.download_file(settings.raw_bucket, key, str(zip_path))
            csv_path = extract_csv(zip_path, temp_path)
            schema = csv_schema(csv_path)
            missing = sorted(set(SELECTED_COLUMNS) - set(schema.fieldNames()))
            if missing:
                raise RuntimeError(f"BTS CSV schema is missing columns: {missing}")

            # Workers cannot see the driver's temporary directory. Stage the
            # extracted CSV in MinIO for the duration of the Spark conversion.
            s3.upload_file(str(csv_path), settings.raw_bucket, extracted_key)
            extracted_uri = s3a_uri(settings.raw_bucket, extracted_key)
            raw_df = spark.read.option("header", True).schema(schema).csv(extracted_uri)
            scheduled_time = F.lpad(F.col("CRSDepTime"), 4, "0")
            scheduled_hour = (
                F.when(scheduled_time == "2400", F.lit(0))
                .otherwise(F.substring(scheduled_time, 1, 2).cast("int"))
                .alias("scheduled_departure_hour_local")
            )

            bronze_df = raw_df.select(
                F.col("Year").cast("int").alias("year"),
                F.col("Month").cast("int").alias("month"),
                F.to_date("FlightDate").alias("flight_date"),
                F.col("Reporting_Airline").alias("reporting_airline"),
                F.col("Flight_Number_Reporting_Airline").alias("flight_number"),
                F.col("OriginAirportID").cast("int").alias("origin_airport_id"),
                F.col("Origin").alias("origin"),
                F.col("DestAirportID").cast("int").alias("destination_airport_id"),
                F.col("Dest").alias("destination"),
                F.col("CRSDepTime").alias("scheduled_departure_hhmm"),
                scheduled_hour,
                F.col("DepDelayMinutes").cast("double").alias("departure_delay_minutes"),
                F.col("ArrDelayMinutes").cast("double").alias("arrival_delay_minutes"),
                F.col("ArrDel15").cast("double").alias("arrival_delayed_15_minutes"),
                F.col("Cancelled").cast("double").alias("cancelled"),
                F.col("Diverted").cast("double").alias("diverted"),
                F.col("Distance").cast("double").alias("distance_miles"),
            )

            bronze_df.write.mode(args.mode).parquet(destination)
            print(f"Wrote Bronze BTS Parquet: {destination}")
            print(f"Rows: {bronze_df.count()}")
    finally:
        if not args.keep_extracted_csv:
            s3.delete_object(Bucket=settings.raw_bucket, Key=extracted_key)
        spark.stop()


if __name__ == "__main__":
    main()
