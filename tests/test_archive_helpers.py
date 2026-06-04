from pathlib import Path
from zipfile import ZipFile

from spark_jobs.build_bronze_bts import archive_name, extract_csv


def test_archive_name_matches_bts_monthly_pattern() -> None:
    assert archive_name(2024, 1).endswith("_2024_1.zip")


def test_extract_csv_rejects_multiple_csv_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("first.csv", "a\n1\n")
        archive.writestr("second.csv", "a\n2\n")
    try:
        extract_csv(zip_path, tmp_path / "out")
    except RuntimeError as error:
        assert "exactly one CSV" in str(error)
    else:
        raise AssertionError("Expected multiple CSV members to be rejected")
