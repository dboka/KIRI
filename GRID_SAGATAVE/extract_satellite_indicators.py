from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


BASE_DIR = Path(__file__).resolve().parent
DEMO_DIR = BASE_DIR.parent / "DEMO_STUFFS"
PRECIP_GRID = BASE_DIR / "precip_outputs" / "interpolated" / "grid_precip_P30_P90_P730_mm.csv"
OUT_DIR = BASE_DIR / "indicator_outputs"


def sample_raster(path: Path, coords: list[tuple[float, float]]) -> np.ndarray:
    with rasterio.open(path) as src:
        values = np.array([sample[0] for sample in src.sample(coords)], dtype="float64")
        nodata = src.nodata
        if nodata is not None:
            values[np.isclose(values, nodata)] = np.nan
        values[~np.isfinite(values)] = np.nan
        return values


def extract_hsaf(grid: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    hsaf_files = sorted((DEMO_DIR / "HSAF_15062026").glob("*_ssm.tif"))
    if not hsaf_files:
        raise FileNotFoundError(f"No H-SAF SSM TIFF files found in {DEMO_DIR / 'HSAF_15062026'}")

    coords = list(zip(grid["x"].astype(float), grid["y"].astype(float)))
    sampled = []
    file_meta = []

    for path in hsaf_files:
        with rasterio.open(path) as src:
            tags = src.tags()
        values = sample_raster(path, coords)
        sampled.append(values)
        file_meta.append(
            {
                "file": str(path),
                "satellite": tags.get("satellite"),
                "sensing_start_utc": tags.get("sensing_start_utc"),
                "sensing_end_utc": tags.get("sensing_end_utc"),
                "valid_sample_count": int(np.isfinite(values).sum()),
            }
        )

    stack = np.vstack(sampled)
    valid_count = np.isfinite(stack).sum(axis=0)

    out = pd.DataFrame(
        {
            "grid_id": grid["grid_id"].astype(str),
            "HSAF_SSM_pct": np.nanmean(stack, axis=0),
            "HSAF_SSM_max_pct": np.nanmax(stack, axis=0),
            "HSAF_SSM_min_pct": np.nanmin(stack, axis=0),
            "HSAF_SSM_std_pct": np.nanstd(stack, axis=0),
            "HSAF_SSM_valid_overpasses": valid_count,
        }
    )
    for col in ["HSAF_SSM_pct", "HSAF_SSM_max_pct", "HSAF_SSM_min_pct", "HSAF_SSM_std_pct"]:
        out[col] = out[col].round(3)

    metadata = {
        "input_file_count": len(hsaf_files),
        "aggregation": "HSAF_SSM_pct is mean of valid 2026-06-15 H-SAF H28 overpass samples at each grid centroid",
        "units": "percent saturation",
        "files": file_meta,
    }
    return out, metadata


def extract_swi(grid: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    swi_files = sorted((DEMO_DIR / "SWI_15062026").glob("*.tif*"))
    if len(swi_files) != 1:
        raise FileNotFoundError(f"Expected one SWI TIFF in {DEMO_DIR / 'SWI_15062026'}, found {len(swi_files)}")

    path = swi_files[0]
    coords = list(zip(grid["lon"].astype(float), grid["lat"].astype(float)))
    raw_values = sample_raster(path, coords)

    # Copernicus SWI products use 255 as nodata and reserve 241-254 for flags/masks.
    # Keep only the ordinary data range for the first KIRI-LV indicator table.
    raw_values[(raw_values >= 241) & (raw_values <= 255)] = np.nan
    physical_values = raw_values * 0.5

    out = pd.DataFrame(
        {
            "grid_id": grid["grid_id"].astype(str),
            "SWI010_raw": np.round(raw_values, 3),
            "SWI010_pct": np.round(physical_values, 3),
        }
    )

    with rasterio.open(path) as src:
        metadata = {
            "file": str(path),
            "description": src.descriptions[0] if src.descriptions else None,
            "crs": str(src.crs),
            "nodata": src.nodata,
            "tags": src.tags(),
            "band_tags": src.tags(1),
            "scale_factor_applied": 0.5,
            "valid_sample_count": int(np.isfinite(physical_values).sum()),
        }
    return out, metadata


def qc_stats(df: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float | int]]:
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grid = pd.read_csv(
        PRECIP_GRID,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "municipality_atvk": "string",
            "municipality_name": "string",
        },
    )

    hsaf, hsaf_meta = extract_hsaf(grid)
    swi, swi_meta = extract_swi(grid)

    hsaf_path = OUT_DIR / "grid_hsaf_ssm_2026-06-15.csv"
    swi_path = OUT_DIR / "grid_swi010_2026-06-15.csv"
    hsaf.to_csv(hsaf_path, index=False, encoding="utf-8")
    swi.to_csv(swi_path, index=False, encoding="utf-8")

    combined = grid.merge(hsaf, on="grid_id", how="left").merge(swi, on="grid_id", how="left")
    combined_path = OUT_DIR / "grid_indicators_P30_P90_P730_HSAF_SWI_2026-06-15.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8")

    metadata = {
        "purpose": "KIRI-LV v0.1 raw indicator grid. Values are not normalized and not risk levels.",
        "date": "2026-06-15",
        "precip_source": str(PRECIP_GRID),
        "hsaf": hsaf_meta,
        "swi": swi_meta,
        "outputs": {
            "hsaf_grid": str(hsaf_path),
            "swi_grid": str(swi_path),
            "combined_grid": str(combined_path),
        },
        "qc": {
            "rows": int(len(combined)),
            "stats": qc_stats(
                combined,
                ["P30_mm", "P90_mm", "P730_mm", "HSAF_SSM_pct", "HSAF_SSM_max_pct", "SWI010_pct"],
            ),
        },
    }
    metadata_path = OUT_DIR / "indicator_extraction_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Rows:", len(combined))
    print("H-SAF files:", len(hsaf_meta["files"]))
    print("Saved:", combined_path)
    print("Metadata:", metadata_path)
    print(json.dumps(metadata["qc"]["stats"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
