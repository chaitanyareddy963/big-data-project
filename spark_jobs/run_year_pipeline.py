"""Run the lakehouse pipeline for all months in a year.

This wrapper is intentionally simple and resumable: each month is processed by
the same production modules used in the PR2 notebooks, so the final demo can
scale from the January proof to a full-year proof without a second code path.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


MONTHLY_MODULES = [
    "spark_jobs.validate_raw_weather",
    "spark_jobs.build_bronze_weather",
    "spark_jobs.build_bronze_bts",
    "spark_jobs.build_silver_flight_weather",
    "spark_jobs.build_gold_features",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--start-month", type=int, default=1, choices=range(1, 13))
    parser.add_argument("--end-month", type=int, default=12, choices=range(1, 13))
    parser.add_argument("--with-delta", action="store_true")
    parser.add_argument("--with-final-model", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(command: list[str], *, dry_run: bool) -> None:
    print(">", " ".join(command), flush=True)
    if not dry_run:
        started = time.perf_counter()
        subprocess.run(command, check=True)
        print(f"Completed in {(time.perf_counter() - started) / 60:.2f} minutes", flush=True)


def main() -> None:
    args = parse_args()
    if args.end_month < args.start_month:
        raise SystemExit("--end-month must be greater than or equal to --start-month")

    for month in range(args.start_month, args.end_month + 1):
        print(f"\n=== {args.year}-{month:02d} monthly lakehouse build ===", flush=True)
        for module in MONTHLY_MODULES:
            run(
                [sys.executable, "-m", module, "--year", str(args.year), "--month", str(month)],
                dry_run=args.dry_run,
            )
        if args.with_delta:
            run(
                [
                    sys.executable,
                    "-m",
                    "spark_jobs.build_delta_lakehouse",
                    "--year",
                    str(args.year),
                    "--month",
                    str(month),
                ],
                dry_run=args.dry_run,
            )

    if args.with_final_model:
        print(f"\n=== {args.year} final full-year model registration ===", flush=True)
        run([sys.executable, "-m", "ml.train_register_model", "--year", str(args.year)], dry_run=args.dry_run)


if __name__ == "__main__":
    main()

