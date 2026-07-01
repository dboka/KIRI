from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUT_ROOT = PROJECT_DIR / "DATA_LAST_60"
HSAF_ROOT = PROJECT_DIR.parent / "FTP_TRYING" / "data" / "h28_latvia_nc"
SWI_DAILY_DIR = PROJECT_DIR.parent / "COPERNICUS_SWI" / "data" / "grid_tiffs" / "daily_swi"
GRID_BASE = BASE_DIR / "outputs" / "grid_1km_municipalities_centroid.csv"
DATE_DIR_RE = re.compile(r"\\(20\d{2})\\([01]\d)\\([0-3]\d)\\")
SWI_DATE_RE = re.compile(r"_(20\d{6})\.tif$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build KIRI-LV v0.1 daily P30/P90/P730/HSAF/SWI indicator grids for the last 60 H-SAF days."
    )
    parser.add_argument("--out-root", default=str(OUT_ROOT))
    parser.add_argument("--hsaf-root", default=str(HSAF_ROOT))
    parser.add_argument("--swi-dir", default=str(SWI_DAILY_DIR))
    parser.add_argument("--grid-base", default=str(GRID_BASE))
    parser.add_argument("--limit-days", type=int, default=None)
    return parser.parse_args()


def date_from_hsaf_path(path: Path) -> date | None:
    match = DATE_DIR_RE.search(str(path))
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def group_hsaf_files(root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(root.rglob("*.nc")):
        value = date_from_hsaf_path(path)
        if value:
            grouped[value.isoformat()].append(path)
    if not grouped:
        raise FileNotFoundError(f"No H-SAF netCDF files found under {root}")
    return dict(grouped)


def index_swi_files(root: Path) -> dict[str, Path]:
    out = {}
    for path in sorted(root.glob("*.tif")):
        match = SWI_DATE_RE.search(path.name)
        if not match:
            continue
        raw = match.group(1)
        out[f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"] = path
    return out


def sample_raster(path: Path | str, coords: list[tuple[float, float]]) -> tuple[np.ndarray, dict[str, object]]:
    with rasterio.open(path) as src:
        values = np.fromiter((sample[0] for sample in src.sample(coords)), dtype="float64")
        nodata = src.nodata
        if nodata is not None:
            values[np.isclose(values, nodata)] = np.nan
        values[~np.isfinite(values)] = np.nan
        meta = {
            "crs": str(src.crs),
            "nodata": nodata,
            "scale": float(src.scales[0]) if src.scales and src.scales[0] else 1.0,
            "offset": float(src.offsets[0]) if src.offsets and src.offsets[0] else 0.0,
            "tags": src.tags(),
            "band_tags": src.tags(1) if src.count else {},
        }
        return values, meta


def hsaf_subdataset(path: Path) -> str:
    return f"netcdf:{path}:surface_soil_moisture"


def sample_hsaf_for_date(paths: list[Path], x: np.ndarray, y: np.ndarray) -> tuple[pd.DataFrame, dict[str, object]]:
    n = len(x)
    value_sum = np.zeros(n, dtype="float64")
    value_count = np.zeros(n, dtype="int32")
    value_min = np.full(n, np.nan, dtype="float64")
    value_max = np.full(n, np.nan, dtype="float64")
    value_sq_sum = np.zeros(n, dtype="float64")
    transformers: dict[str, tuple[Transformer, list[tuple[float, float]]]] = {}
    files_meta = []

    for path in paths:
        dataset = hsaf_subdataset(path)
        with rasterio.open(dataset) as src:
            crs_key = str(src.crs)
            if crs_key not in transformers:
                transformer = Transformer.from_crs("EPSG:3059", src.crs, always_xy=True)
                hx, hy = transformer.transform(x, y)
                transformers[crs_key] = (transformer, list(zip(hx, hy)))
            coords = transformers[crs_key][1]

            raw = np.fromiter((sample[0] for sample in src.sample(coords)), dtype="float64")
            nodata = src.nodata
            if nodata is not None:
                raw[np.isclose(raw, nodata)] = np.nan
            raw[~np.isfinite(raw)] = np.nan

            scale = float(src.scales[0]) if src.scales and src.scales[0] else 1.0
            offset = float(src.offsets[0]) if src.offsets and src.offsets[0] else 0.0
            values = raw * scale + offset
            values[(values < 0) | (values > 100)] = np.nan
            valid = np.isfinite(values)

            value_sum[valid] += values[valid]
            value_sq_sum[valid] += values[valid] ** 2
            value_count[valid] += 1
            value_min[valid] = np.where(np.isnan(value_min[valid]), values[valid], np.minimum(value_min[valid], values[valid]))
            value_max[valid] = np.where(np.isnan(value_max[valid]), values[valid], np.maximum(value_max[valid], values[valid]))
            tags = src.tags()
            files_meta.append(
                {
                    "file": str(path),
                    "sensing_start_utc": tags.get("NC_GLOBAL#sensing_start_time_utc"),
                    "sensing_end_utc": tags.get("NC_GLOBAL#sensing_end_time_utc"),
                    "spacecraft": tags.get("NC_GLOBAL#spacecraft"),
                    "valid_sample_count": int(valid.sum()),
                }
            )

    mean = np.full(n, np.nan, dtype="float64")
    std = np.full(n, np.nan, dtype="float64")
    valid_any = value_count > 0
    mean[valid_any] = value_sum[valid_any] / value_count[valid_any]
    variance = np.maximum(value_sq_sum[valid_any] / value_count[valid_any] - mean[valid_any] ** 2, 0)
    std[valid_any] = np.sqrt(variance)

    out = pd.DataFrame(
        {
            "HSAF_SSM_pct": np.round(mean, 3),
            "HSAF_SSM_max_pct": np.round(value_max, 3),
            "HSAF_SSM_min_pct": np.round(value_min, 3),
            "HSAF_SSM_std_pct": np.round(std, 3),
            "HSAF_SSM_valid_overpasses": value_count,
        }
    )
    meta = {
        "input_file_count": len(paths),
        "aggregation": "Daily mean of valid H-SAF H28 surface_soil_moisture samples at grid centroids.",
        "units": "percent saturation",
        "files": files_meta,
    }
    return out, meta


def sample_swi(path: Path | None, lon: np.ndarray, lat: np.ndarray, x: np.ndarray, y: np.ndarray) -> tuple[pd.DataFrame, dict[str, object]]:
    if path is None:
        return pd.DataFrame({"SWI010_raw": np.nan, "SWI010_pct": np.nan}, index=np.arange(len(x))), {
            "file": None,
            "missing_reason": "No SWI daily TIFF for this target date.",
        }

    with rasterio.open(path) as src:
        coords = list(zip(x, y)) if src.crs and str(src.crs).upper().endswith("3059") else list(zip(lon, lat))
        raw = np.fromiter((sample[0] for sample in src.sample(coords)), dtype="float64")
        nodata = src.nodata
        if nodata is not None:
            raw[np.isclose(raw, nodata)] = np.nan
        raw[~np.isfinite(raw)] = np.nan
        raw[(raw < 0) | (raw > 100)] = np.nan
        out = pd.DataFrame({"SWI010_raw": np.round(raw, 3), "SWI010_pct": np.round(raw, 3)})
        meta = {
            "file": str(path),
            "crs": str(src.crs),
            "nodata": nodata,
            "valid_sample_count": int(np.isfinite(raw).sum()),
            "units": "%",
        }
        return out, meta


def qc_stats(df: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float | int | None]]:
    stats = {}
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce")
        stats[col] = {
            "missing": int(series.isna().sum()),
            "min": round(float(series.min()), 3) if series.notna().any() else None,
            "mean": round(float(series.mean()), 3) if series.notna().any() else None,
            "max": round(float(series.max()), 3) if series.notna().any() else None,
        }
    return stats


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    precip_dir = out_root / "precip_grids"
    indicator_dir = out_root / "indicator_grids"
    satellite_dir = out_root / "satellite_grids"
    metadata_dir = out_root / "metadata"
    indicator_dir.mkdir(parents=True, exist_ok=True)
    satellite_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    grid_base = pd.read_csv(
        args.grid_base,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "municipality_atvk": "string",
            "municipality_name": "string",
        },
        low_memory=False,
    )
    grid_base["grid_id"] = grid_base["grid_id"].astype(str)
    x = grid_base["x"].to_numpy(dtype="float64")
    y = grid_base["y"].to_numpy(dtype="float64")
    lon = grid_base["lon"].to_numpy(dtype="float64")
    lat = grid_base["lat"].to_numpy(dtype="float64")

    hsaf_by_date = group_hsaf_files(Path(args.hsaf_root))
    swi_by_date = index_swi_files(Path(args.swi_dir))
    dates = sorted(hsaf_by_date)
    if args.limit_days:
        dates = dates[: args.limit_days]

    metadata_rows = []
    for target_date in dates:
        print(f"\n== {target_date} ==")
        precip_path = precip_dir / f"grid_precip_P30_P90_P730_mm_{target_date.replace('-', '_')}.csv"
        if not precip_path.exists():
            raise FileNotFoundError(f"Missing precipitation grid for {target_date}: {precip_path}")

        precip = pd.read_csv(
            precip_path,
            dtype={
                "grid_id": "string",
                "municipality_code": "string",
                "municipality_atvk": "string",
                "municipality_name": "string",
            },
            low_memory=False,
        )
        precip["grid_id"] = precip["grid_id"].astype(str)

        hsaf, hsaf_meta = sample_hsaf_for_date(hsaf_by_date[target_date], x, y)
        hsaf.insert(0, "grid_id", grid_base["grid_id"].astype(str).to_numpy())

        swi, swi_meta = sample_swi(swi_by_date.get(target_date), lon, lat, x, y)
        swi.insert(0, "grid_id", grid_base["grid_id"].astype(str).to_numpy())

        hsaf_path = satellite_dir / f"grid_hsaf_ssm_{target_date}.csv"
        swi_path = satellite_dir / f"grid_swi010_{target_date}.csv"
        hsaf.to_csv(hsaf_path, index=False, encoding="utf-8")
        swi.to_csv(swi_path, index=False, encoding="utf-8")

        combined = precip.merge(hsaf, on="grid_id", how="left").merge(swi, on="grid_id", how="left")
        combined.insert(0, "date", target_date)
        combined_path = indicator_dir / f"grid_indicators_P30_P90_P730_HSAF_SWI_{target_date}.csv"
        combined.to_csv(combined_path, index=False, encoding="utf-8")

        stats = qc_stats(combined, ["P30_mm", "P90_mm", "P730_mm", "HSAF_SSM_pct", "SWI010_pct"])
        date_meta = {
            "date": target_date,
            "rows": int(len(combined)),
            "precip_grid": str(precip_path),
            "hsaf": hsaf_meta,
            "swi": swi_meta,
            "outputs": {
                "hsaf_grid": str(hsaf_path),
                "swi_grid": str(swi_path),
                "combined_grid": str(combined_path),
            },
            "qc": stats,
        }
        (metadata_dir / f"indicator_metadata_{target_date}.json").write_text(
            json.dumps(date_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metadata_rows.append(
            {
                "date": target_date,
                "rows": int(len(combined)),
                "hsaf_file_count": len(hsaf_by_date[target_date]),
                "swi_available": target_date in swi_by_date,
                "hsaf_missing": stats["HSAF_SSM_pct"]["missing"],
                "swi_missing": stats["SWI010_pct"]["missing"],
                "combined_grid": str(combined_path),
            }
        )
        print(f"Saved: {combined_path}")

    summary = pd.DataFrame(metadata_rows)
    summary_path = metadata_dir / "indicator_grids_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8")
    print(f"\nDONE indicator grids: {len(summary)} dates")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
