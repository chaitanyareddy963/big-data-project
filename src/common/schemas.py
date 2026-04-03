from __future__ import annotations

from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType
from pydantic import BaseModel, Field


BRONZE_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("airport_code", StringType(), False),
        StructField("event_time", StringType(), False),
        StructField("source_type", StringType(), False),
        StructField("temperature_c", DoubleType(), False),
        StructField("wind_speed_kts", DoubleType(), False),
        StructField("visibility_miles", DoubleType(), False),
        StructField("precip_mm", DoubleType(), False),
        StructField("pressure_hpa", DoubleType(), False),
        StructField("dep_count", IntegerType(), False),
        StructField("arr_count", IntegerType(), False),
        StructField("avg_dep_delay_min", DoubleType(), False),
        StructField("avg_arr_delay_min", DoubleType(), False),
        StructField("disruption_label", IntegerType(), False),
    ]
)

SCORE_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("airport_code", StringType(), False),
        StructField("event_time", StringType(), False),
        StructField("risk_score", DoubleType(), False),
        StructField("risk_label", IntegerType(), False),
        StructField("model_version", StringType(), False),
        StructField("scored_at", StringType(), False),
    ]
)


class PredictionRequest(BaseModel):
    airport_code: str = Field(..., min_length=3, max_length=4)
    event_time: str
    temperature_c: float
    wind_speed_kts: float
    visibility_miles: float
    precip_mm: float
    pressure_hpa: float
    dep_count: int
    arr_count: int
    avg_dep_delay_min: float
    avg_arr_delay_min: float
    event_hour: int
    is_weekend: int
    rolling_avg_dep_delay_6h: float
    rolling_avg_arr_delay_6h: float
    rolling_max_wind_6h: float
    rolling_total_precip_6h: float
    delay_pressure_index: float


class PredictionResponse(BaseModel):
    event_time: str
    airport_code: str
    risk_score: float
    risk_label: int
    model_version: str
