from src.common.contracts import FEATURE_COLUMNS, RAW_COLUMNS, SCORE_COLUMNS
from src.common.schemas import PredictionRequest


def test_feature_column_count():
    assert len(FEATURE_COLUMNS) == 16


def test_raw_has_event_id():
    assert RAW_COLUMNS[0] == "event_id"


def test_score_schema_payload():
    payload = PredictionRequest(
        airport_code="ATL",
        event_time="2024-01-01T00:00:00Z",
        temperature_c=10.0,
        wind_speed_kts=12.0,
        visibility_miles=9.0,
        precip_mm=0.2,
        pressure_hpa=1012.0,
        dep_count=100,
        arr_count=99,
        avg_dep_delay_min=10.0,
        avg_arr_delay_min=9.0,
        event_hour=0,
        is_weekend=0,
        rolling_avg_dep_delay_6h=10.0,
        rolling_avg_arr_delay_6h=9.0,
        rolling_max_wind_6h=12.0,
        rolling_total_precip_6h=0.2,
        delay_pressure_index=0.02,
    )
    assert payload.airport_code == "ATL"
    assert SCORE_COLUMNS[-1] == "scored_at"
