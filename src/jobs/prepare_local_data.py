from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.contracts import DEFAULT_AIRPORTS
from src.common.logging_utils import configure_logging


def build_dataframe() -> pd.DataFrame:
    airports = DEFAULT_AIRPORTS
    airport_bias = {"ATL": 1.2, "JFK": 1.6, "ORD": 1.5, "DFW": 1.1, "DEN": 1.0}
    rng = np.random.default_rng(42)
    hours = pd.date_range("2024-01-01", "2024-01-31 23:00:00", freq="1H", tz="UTC")
    rows = []
    for airport in airports:
        for ts in hours:
            hour_factor = np.sin((ts.hour / 24) * 2 * np.pi)
            weekend = 1 if ts.dayofweek >= 5 else 0
            storm = max(0.0, rng.normal(0.8 if ts.day % 7 == 0 else 0.2, 0.4))
            wind = max(2.0, 10 + 8 * storm + rng.normal(0, 2))
            precip = max(0.0, storm * rng.uniform(0.0, 3.0))
            visibility = max(1.0, 10 - storm * rng.uniform(0.5, 4.0))
            pressure = 1016 - storm * rng.uniform(0.5, 4.0) + rng.normal(0, 0.8)
            dep_count = max(25, int(80 + 35 * max(hour_factor, 0) + rng.normal(0, 8)))
            arr_count = max(20, int(dep_count + rng.normal(0, 4)))
            avg_dep_delay = max(0.0, airport_bias[airport] * (4 + storm * 8 + weekend * 2 + rng.normal(0, 2)))
            avg_arr_delay = max(0.0, avg_dep_delay - rng.normal(0, 1.5))
            temperature = {
                "ATL": 12,
                "JFK": 5,
                "ORD": -3,
                "DFW": 10,
                "DEN": -1,
            }[airport] + 8 * hour_factor + rng.normal(0, 2)
            risk_signal = avg_dep_delay * 0.18 + avg_arr_delay * 0.12 + wind * 0.06 + precip * 0.5 - visibility * 0.2
            disruption = int(risk_signal > 4.2)
            rows.append(
                {
                    "event_id": f"{airport}-{ts.strftime('%Y%m%dT%H%M%SZ')}",
                    "airport_code": airport,
                    "event_time": ts.isoformat().replace("+00:00", "Z"),
                    "source_type": "synthetic",
                    "temperature_c": round(float(temperature), 2),
                    "wind_speed_kts": round(float(wind), 2),
                    "visibility_miles": round(float(visibility), 2),
                    "precip_mm": round(float(precip), 2),
                    "pressure_hpa": round(float(pressure), 2),
                    "dep_count": dep_count,
                    "arr_count": arr_count,
                    "avg_dep_delay_min": round(float(avg_dep_delay), 2),
                    "avg_arr_delay_min": round(float(avg_arr_delay), 2),
                    "disruption_label": disruption,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/local/aviation_events_2024-01.csv")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    build_dataframe().to_csv(output, index=False)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
