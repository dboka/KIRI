"""Build compact 1991–2020 precipitation reference curves for KIRI charts.

The source workbook is read only. Daily P30/P90/P730 sums require every day in
the rolling window. Station climatologies are calculated once and are spatially
adapted to a grid cell in the browser using eight nearby stations.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = BASE_DIR / "frontend" / "data" / "precip_climatology"
FIELDS = ("p10", "p25", "p50", "p75", "p90", "mean", "count")
PERIODS = {"p30": 30, "p90": 90, "p730": 730}
REFERENCE_START = "1991-01-01"
REFERENCE_END = "2020-12-31"
RADIUS_DAYS = 7
MIN_SAMPLES = 60
NEIGHBORS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Daily precipitation workbook")
    parser.add_argument("--stations", type=Path, required=True, help="Station GeoPackage with GH_ID in EPSG:3059")
    parser.add_argument("--grid", type=Path, required=True, help="KIRI 1 km centroid CSV")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def write_gzip_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def workbook_daily(source: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    workbook = pd.read_excel(source, engine="openpyxl")
    if list(workbook.columns[:3]) != ["Gads", "Menesis", "Diena"]:
        raise ValueError("Expected Gads, Menesis, Diena in the first three workbook columns")
    station_ids = [str(column).strip() for column in workbook.columns[3:]]
    if len(station_ids) != len(set(station_ids)) or not station_ids:
        raise ValueError("Station identifiers must be unique and nonempty")
    dates = pd.to_datetime(
        workbook[["Gads", "Menesis", "Diena"]].rename(
            columns={"Gads": "year", "Menesis": "month", "Diena": "day"}
        ),
        errors="raise",
    )
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Workbook dates must be unique and increasing")
    required_dates = pd.date_range("1989-01-01", REFERENCE_END, freq="D")
    if not required_dates.isin(dates).all():
        raise ValueError("Workbook lacks calendar days needed for 1989–2020 rolling windows")
    raw = workbook.iloc[:, 3:].copy()
    raw.columns = station_ids
    values = raw.replace(",", ".", regex=True).apply(pd.to_numeric, errors="coerce")
    values.index = dates
    values = values.loc["1989-01-01":REFERENCE_END]
    if (values < 0).any().any():
        raise ValueError("Negative daily precipitation found in the reference input")
    source_nonempty = raw.loc[(dates >= "1989-01-01") & (dates <= REFERENCE_END)].notna().sum().sum()
    invalid_values = int(source_nonempty - values.notna().sum().sum())
    if invalid_values:
        raise ValueError(f"Found {invalid_values} nonnumeric daily precipitation values")
    return values, {"station_count": len(station_ids), "invalid_values": invalid_values}


def station_profiles(daily: pd.DataFrame) -> tuple[dict[str, object], dict[str, object]]:
    reference_dates = daily.loc[REFERENCE_START:REFERENCE_END].index
    mapped_dates = pd.to_datetime(
        {"year": 2000, "month": reference_dates.month, "day": reference_dates.day}
    )
    day_bins = mapped_dates.dt.dayofyear.to_numpy() - 1
    periods: dict[str, object] = {}
    quality: dict[str, object] = {}
    for key, window_days in PERIODS.items():
        rolling = daily.rolling(window_days, min_periods=window_days).sum().loc[REFERENCE_START:REFERENCE_END]
        values = rolling.to_numpy(dtype=np.float64)
        profile = [[None] * 366 for _ in daily.columns]
        sample_counts: list[int] = []
        for day_index in range(366):
            circular_distance = np.abs(day_bins - day_index)
            selected = values[np.minimum(circular_distance, 366 - circular_distance) <= RADIUS_DAYS]
            for station_index in range(len(daily.columns)):
                samples = selected[:, station_index]
                samples = samples[np.isfinite(samples)]
                if len(samples) < MIN_SAMPLES:
                    continue
                quantiles = np.percentile(samples, [10, 25, 50, 75, 90])
                profile[station_index][day_index] = [
                    *[round(float(value), 1) for value in quantiles],
                    round(float(samples.mean()), 1),
                    int(len(samples)),
                ]
                sample_counts.append(len(samples))
        periods[key] = {"window_days": window_days, "profiles": profile}
        quality[key] = {
            "complete_station_days": int(np.isfinite(values).sum()),
            "available_station_day_profiles": len(sample_counts),
            "expected_station_day_profiles": len(daily.columns) * 366,
            "minimum_profile_samples": min(sample_counts) if sample_counts else 0,
        }
        if len(sample_counts) < len(daily.columns) * 366:
            raise ValueError(f"Insufficient reference samples for {key} station profiles")
    return periods, quality


def build_weights(station_ids: list[str], station_path: Path, grid_path: Path, out_dir: Path) -> dict[str, object]:
    stations = gpd.read_file(station_path, layer="stations")
    if stations.crs is None:
        raise ValueError("Station GeoPackage has no coordinate reference system")
    stations = stations.to_crs(3059)
    stations["GH_ID"] = stations["GH_ID"].astype(str).str.strip()
    stations = stations.set_index("GH_ID").reindex(station_ids)
    if stations.geometry.isna().any():
        missing = [station_ids[i] for i, invalid in enumerate(stations.geometry.isna()) if invalid]
        raise ValueError(f"Station coordinates missing for: {missing}")
    coordinates = np.column_stack((stations.geometry.x.to_numpy(), stations.geometry.y.to_numpy()))
    grid = pd.read_csv(
        grid_path,
        usecols=["grid_id", "x", "y", "municipality_code"],
        dtype={"grid_id": str, "municipality_code": str},
    )
    unassigned_cells = int(grid["municipality_code"].isna().sum())
    grid = grid.dropna(subset=["municipality_code"]).reset_index(drop=True)
    if grid["grid_id"].duplicated().any() or grid[["x", "y"]].isna().any().any():
        raise ValueError("Grid IDs must be unique and coordinates complete")
    distances, indices = cKDTree(coordinates).query(grid[["x", "y"]].to_numpy(), k=NEIGHBORS)
    inverse_square = 1.0 / np.maximum(distances, 1.0) ** 2
    weights = inverse_square / inverse_square.sum(axis=1, keepdims=True)
    exact = distances[:, 0] < 1.0
    weights[exact] = 0.0
    weights[exact, 0] = 1.0
    files: dict[str, object] = {}
    for code, group in grid.groupby("municipality_code", sort=True):
        rows = []
        for row_number, grid_id in zip(group.index, group["grid_id"]):
            neighbors = [[int(index), round(float(weight), 6)] for index, weight in zip(indices[row_number], weights[row_number])]
            rows.append([str(grid_id), neighbors])
        path = out_dir / "weights" / f"{code}.json.gz"
        write_gzip_json(path, {"version": 1, "rows": rows})
        files[code] = {"cells": len(rows), "bytes": path.stat().st_size}
    return {
        "method": "inverse-distance-squared of 8 nearest stations in EPSG:3059",
        "municipality_count": len(files),
        "cell_count": len(grid),
        "unassigned_cells": unassigned_cells,
        "maximum_nearest_station_distance_km": round(float(distances[:, 0].max() / 1000), 1),
        "files": files,
    }


def main() -> None:
    args = parse_args()
    daily, input_quality = workbook_daily(args.source)
    profiles, quality = station_profiles(daily)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = args.out_dir / "stations.json.gz"
    write_gzip_json(
        profile_path,
        {
            "version": 1,
            "reference_start": REFERENCE_START,
            "reference_end": REFERENCE_END,
            "window_radius_days": RADIUS_DAYS,
            "minimum_samples": MIN_SAMPLES,
            "fields": FIELDS,
            "stations": list(daily.columns),
            "periods": profiles,
        },
    )
    spatial = build_weights(list(daily.columns), args.stations, args.grid, args.out_dir)
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    index = {
        "version": 1,
        "source_workbook": args.source.name,
        "source_sha256": digest,
        "reference_start": REFERENCE_START,
        "reference_end": REFERENCE_END,
        "method": "complete rolling daily sums; 15-day calendar window; station quantiles interpolated to grid",
        "window_radius_days": RADIUS_DAYS,
        "minimum_samples": MIN_SAMPLES,
        "periods": PERIODS,
        "input_quality": input_quality,
        "profile_quality": quality,
        "spatial": spatial,
        "profile_bytes": profile_path.stat().st_size,
    }
    (args.out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"profile_bytes": index["profile_bytes"], "profile_quality": quality, "spatial": {key: spatial[key] for key in ("municipality_count", "cell_count", "maximum_nearest_station_distance_km")}}, indent=2))


if __name__ == "__main__":
    main()
