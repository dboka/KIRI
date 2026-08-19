from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUT_ROOT = PROJECT_DIR / "DATA_LAST_60"
SWI_DAILY_DIR = PROJECT_DIR.parent / "COPERNICUS_SWI" / "data" / "grid_tiffs" / "daily_swi"
GRID_BASE = BASE_DIR / "outputs" / "grid_1km_municipalities_centroid.csv"
INDICATOR_RE = re.compile(r"grid_indicators_P30_P90_P730_HSAF_SWI_(20\d{2}-\d{2}-\d{2})\.csv$")
SWI_DATE_RE = re.compile(r"_(20\d{6})\.tif$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh SWI010 columns in existing KIRI indicator CSVs when delayed SWI daily TIFFs arrive."
    )
    parser.add_argument("--out-root", default=str(OUT_ROOT))
    parser.add_argument("--swi-dir", default=str(SWI_DAILY_DIR))
    parser.add_argument("--grid-base", default=str(GRID_BASE))
    parser.add_argument("--dates", nargs="*", default=None, help="Optional YYYY-MM-DD dates to check.")
    parser.add_argument("--force", action="store_true", help="Refresh even if the indicator already has SWI values.")
    return parser.parse_args()


def index_swi_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.exists():
        return out
    for path in sorted(root.glob("*.tif")):
        match = SWI_DATE_RE.search(path.name)
        if not match:
            continue
        raw = match.group(1)
        out[f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"] = path
    return out


def indicator_date(path: Path) -> str | None:
    match = INDICATOR_RE.match(path.name)
    return match.group(1) if match else None


def sample_swi(path: Path, grid: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    x = grid["x"].to_numpy(dtype="float64")
    y = grid["y"].to_numpy(dtype="float64")
    lon = grid["lon"].to_numpy(dtype="float64")
    lat = grid["lat"].to_numpy(dtype="float64")

    with rasterio.open(path) as src:
        coords = list(zip(x, y)) if src.crs and str(src.crs).upper().endswith("3059") else list(zip(lon, lat))
        crs = str(src.crs)
        raw = np.fromiter((sample[0] for sample in src.sample(coords)), dtype="float64")
        nodata = src.nodata
        if nodata is not None:
            raw[np.isclose(raw, nodata)] = np.nan
        raw[~np.isfinite(raw)] = np.nan
        raw[(raw < 0) | (raw > 100)] = np.nan

    values = pd.DataFrame(
        {
            "grid_id": grid["grid_id"].astype(str).to_numpy(),
            "SWI010_raw": np.round(raw, 3),
            "SWI010_pct": np.round(raw, 3),
        }
    )
    meta = {
        "file": str(path),
        "crs": crs,
        "nodata": float(nodata) if nodata is not None else None,
        "valid_sample_count": int(np.isfinite(raw).sum()),
        "units": "%",
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
    }
    return values, meta


def qc_stats(series: pd.Series) -> dict[str, float | int | None]:
    values = pd.to_numeric(series, errors="coerce")
    return {
        "missing": int(values.isna().sum()),
        "min": round(float(values.min()), 3) if values.notna().any() else None,
        "mean": round(float(values.mean()), 3) if values.notna().any() else None,
        "max": round(float(values.max()), 3) if values.notna().any() else None,
    }


def should_refresh(indicator_path: Path, swi_path: Path, force: bool) -> bool:
    if force:
        return True
    try:
        current = pd.read_csv(indicator_path, usecols=["SWI010_pct"], low_memory=False)
    except ValueError:
        return True
    missing = pd.to_numeric(current["SWI010_pct"], errors="coerce").isna().sum()
    all_missing = int(missing) == len(current)
    return all_missing or swi_path.stat().st_mtime > indicator_path.stat().st_mtime


def refresh_date(
    date_text: str,
    indicator_path: Path,
    swi_path: Path,
    grid: pd.DataFrame,
    out_root: Path,
    force: bool,
) -> bool:
    if not should_refresh(indicator_path, swi_path, force):
        return False

    indicators = pd.read_csv(
        indicator_path,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "municipality_atvk": "string",
            "municipality_name": "string",
        },
        low_memory=False,
    )
    indicators["grid_id"] = indicators["grid_id"].astype(str)
    swi, swi_meta = sample_swi(swi_path, grid)
    swi["grid_id"] = swi["grid_id"].astype(str)
    swi_by_grid = swi.set_index("grid_id")

    indicators["SWI010_raw"] = indicators["grid_id"].map(swi_by_grid["SWI010_raw"])
    indicators["SWI010_pct"] = indicators["grid_id"].map(swi_by_grid["SWI010_pct"])
    indicators.to_csv(indicator_path, index=False, encoding="utf-8")

    satellite_dir = out_root / "satellite_grids"
    satellite_dir.mkdir(parents=True, exist_ok=True)
    swi.to_csv(satellite_dir / f"grid_swi010_{date_text}.csv", index=False, encoding="utf-8")

    metadata_path = out_root / "metadata" / f"indicator_metadata_{date_text}.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["swi"] = swi_meta
        metadata.setdefault("qc", {})["SWI010_pct"] = qc_stats(indicators["SWI010_pct"])
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return True


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    indicator_dir = out_root / "indicator_grids"
    log_dir = out_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    grid = pd.read_csv(
        args.grid_base,
        usecols=["grid_id", "x", "y", "lon", "lat"],
        dtype={"grid_id": "string"},
        low_memory=False,
    )
    grid["grid_id"] = grid["grid_id"].astype(str)
    swi_by_date = index_swi_files(Path(args.swi_dir))
    requested_dates = set(args.dates or [])
    updated_dates: list[str] = []
    checked_dates: list[str] = []

    for indicator_path in sorted(indicator_dir.glob("grid_indicators_P30_P90_P730_HSAF_SWI_*.csv")):
        date_text = indicator_date(indicator_path)
        if not date_text:
            continue
        if requested_dates and date_text not in requested_dates:
            continue
        checked_dates.append(date_text)
        swi_path = swi_by_date.get(date_text)
        if not swi_path:
            continue
        if refresh_date(date_text, indicator_path, swi_path, grid, out_root, args.force):
            updated_dates.append(date_text)
            print(f"Refreshed SWI in indicator grid: {date_text}")

    status = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "checked_dates": checked_dates,
        "updated_dates": updated_dates,
        "swi_daily_latest": sorted(swi_by_date)[-1] if swi_by_date else None,
    }
    status_path = log_dir / "swi_indicator_refresh_last_run.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
