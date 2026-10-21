"""Build compact 1991–2020 precipitation reference curves for KIRI charts.

The source workbook is read only. Daily P30/P90/P730 sums require every day in
the rolling window. Station climatologies are calculated once and interpolated
to the grid with the same universal-kriging model as daily KIRI precipitation.
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
from scipy.linalg import solve
from scipy.spatial.distance import cdist


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = BASE_DIR / "frontend" / "data" / "precip_climatology"
FIELDS = ("p10", "p25", "p50", "p75", "p90", "mean", "count")
PERIODS = {"p30": 30, "p90": 90, "p730": 730}
REFERENCE_START = "1991-01-01"
REFERENCE_END = "2020-12-31"
RADIUS_DAYS = 7
MIN_SAMPLES = 60
KRIGING_RANGE_M = 45000
KRIGING_MODEL = "Exp"
KRIGING_DRIFT = "value ~ x + y + I(x^2) + I(y^2) + x * y + cont + h"


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


def drift_matrix(xy: np.ndarray, cont: np.ndarray, elevation: np.ndarray) -> np.ndarray:
    # Centering/scaling changes the basis, not the span of the operational R formula.
    x = (xy[:, 0] - 600000.0) / 100000.0
    y = (xy[:, 1] - 300000.0) / 100000.0
    return np.column_stack((
        np.ones(len(x)), x, y, x * x, y * y, x * y,
        (cont - 30.0) / 10.0, elevation / 100.0,
    ))


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
    station_cont = pd.to_numeric(stations["cont_pr"], errors="coerce").to_numpy()
    station_elev = pd.to_numeric(stations["ELEVATION"], errors="coerce").to_numpy()
    if not np.isfinite(coordinates).all() or not np.isfinite(station_cont).all() or not np.isfinite(station_elev).all():
        raise ValueError("Station geometry, elevation, and cont_pr must be complete")
    grid = pd.read_csv(
        grid_path,
        usecols=["grid_id", "x", "y", "h5", "cont_pr", "municipality_code"],
        dtype={"grid_id": str, "municipality_code": str},
    )
    unassigned_cells = int(grid["municipality_code"].isna().sum())
    grid = grid.dropna(subset=["municipality_code"]).reset_index(drop=True)
    if grid["grid_id"].duplicated().any() or not np.isfinite(grid[["x", "y", "h5", "cont_pr"]].to_numpy()).all():
        raise ValueError("Grid IDs must be unique and kriging covariates complete")

    # KIRI's R model is Exp(range=45000, nugget=0), with a fixed range and
    # fitted sill. The sill is a common covariance multiplier and cancels out
    # of the universal-kriging equations. The linear weights therefore match
    # gstat::krige for every station-normal field with these same 33 stations.
    station_drift = drift_matrix(coordinates, station_cont, station_elev)
    covariance = np.exp(-cdist(coordinates, coordinates) / KRIGING_RANGE_M)
    station_count = len(station_ids)
    drift_count = station_drift.shape[1]
    system = np.block([
        [covariance, station_drift],
        [station_drift.T, np.zeros((drift_count, drift_count))],
    ])
    grid_xy = grid[["x", "y"]].to_numpy()
    grid_drift = drift_matrix(grid_xy, grid["cont_pr"].to_numpy(), grid["h5"].to_numpy())
    weights = np.empty((len(grid), station_count), dtype=np.float64)
    for start in range(0, len(grid), 4096):
        end = min(start + 4096, len(grid))
        grid_covariance = np.exp(-cdist(coordinates, grid_xy[start:end]) / KRIGING_RANGE_M)
        right_hand_side = np.vstack((grid_covariance, grid_drift[start:end].T))
        weights[start:end] = solve(system, right_hand_side, assume_a="sym")[:station_count].T
    if not np.allclose(weights.sum(axis=1), 1, atol=1e-10):
        raise ValueError("Universal-kriging weights do not preserve constants")
    if not np.allclose(weights @ station_drift, grid_drift, atol=1e-9):
        raise ValueError("Universal-kriging weights do not reproduce the drift")
    files: dict[str, object] = {}
    for code, group in grid.groupby("municipality_code", sort=True):
        rows = []
        for row_number, grid_id in zip(group.index, group["grid_id"]):
            coefficients = [round(float(weight), 9) for weight in weights[row_number]]
            rows.append([str(grid_id), coefficients])
        path = out_dir / "weights" / f"{code}.json.gz"
        write_gzip_json(path, {"version": 2, "rows": rows})
        files[code] = {"cells": len(rows), "bytes": path.stat().st_size}
    return {
        "method": "universal kriging with exponential variogram, range 45000 m, zero nugget, all stations and operational drift; predictions clamped to station range",
        "variogram_model": KRIGING_MODEL,
        "range_m": KRIGING_RANGE_M,
        "nugget": 0,
        "drift": KRIGING_DRIFT,
        "station_count": station_count,
        "municipality_count": len(files),
        "cell_count": len(grid),
        "unassigned_cells": unassigned_cells,
        "maximum_absolute_weight": round(float(np.max(np.abs(weights))), 3),
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
        "version": 2,
        "source_workbook": args.source.name,
        "source_sha256": digest,
        "reference_start": REFERENCE_START,
        "reference_end": REFERENCE_END,
        "method": "complete rolling daily sums; 15-day calendar window; station quantiles interpolated with operational universal kriging",
        "window_radius_days": RADIUS_DAYS,
        "minimum_samples": MIN_SAMPLES,
        "periods": PERIODS,
        "input_quality": input_quality,
        "profile_quality": quality,
        "spatial": spatial,
        "profile_bytes": profile_path.stat().st_size,
    }
    (args.out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"profile_bytes": index["profile_bytes"], "profile_quality": quality, "spatial": {key: spatial[key] for key in ("municipality_count", "cell_count", "maximum_absolute_weight")}}, indent=2))


if __name__ == "__main__":
    main()
