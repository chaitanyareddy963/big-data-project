import csv
from pathlib import Path

from src.common.contracts import DEFAULT_AIRPORTS, RAW_COLUMNS


SAMPLE_PATH = Path("data/sample/aviation_events_smoke.csv")


def test_sample_header_matches_contract():
    with SAMPLE_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    assert header == RAW_COLUMNS


def test_sample_airports_stay_in_subset():
    with SAMPLE_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {row["airport_code"] for row in rows}.issubset(set(DEFAULT_AIRPORTS))


def test_sample_contains_expected_row_count():
    with SAMPLE_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 15
