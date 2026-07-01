from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt

from src.normalization.normalize_kiri_v01 import (
    add_combined_risk,
    add_variable_risks,
    load_config,
    municipality_summary,
)
from repair_last_60_municipality_names import load_name_map


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
LAST_60_DIR = PROJECT_DIR / "DATA_LAST_60"
INDICATOR_DIR = LAST_60_DIR / "indicator_grids"
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
DATE_DATA_DIR = FRONTEND_DATA / "dates"
SOURCE_GRID_DIR = FRONTEND_DATA / "municipality_grids"
SOURCE_MUNICIPALITIES = FRONTEND_DATA / "municipalities.geojson"
SOURCE_MANIFEST = FRONTEND_DATA / "municipality_manifest.json"
CONFIG_PATH = BASE_DIR / "config" / "normalization_v01.yaml"
GRID_ASSIGNMENT_CSV = BASE_DIR / "outputs" / "grid_1km_municipalities_centroid.csv"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def clean_reason_text(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [part for part in str(value).split("|") if part]


def safe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def safe_float(value: object, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def overview_level(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return max(1, min(5, int(math.ceil(float(value)))))


def recommendation_for(row: pd.Series) -> str:
    high = float(row.get("percent_cells_risk_4_5", 0) or 0)
    if high >= 35:
        return "Augsta riska zonās izkliedi atlikt; pārbaudi grid šūnas un vietējos apstākļus."
    if high >= 15:
        return "Izkliedi plānot piesardzīgi; augstākā riska šūnas pārbaudīt detalizēti."
    return "Risks pārsvarā zemāks; turpini pārbaudīt lokālos apstākļus pirms lēmuma."


def grid_feature(row: pd.Series, geometry: dict) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "grid_id": str(row["grid_id"]),
            "kiri_risk_level": safe_int(row.get("kiri_risk_level")),
            "kiri_risk_label_lv": row.get("kiri_risk_label_lv"),
            "main_reasons": clean_reason_text(row.get("main_reasons")),
            "confidence": row.get("confidence"),
            "p30_risk": safe_int(row.get("p30_risk")),
            "p90_risk": safe_int(row.get("p90_risk")),
            "p730_risk": safe_int(row.get("p730_risk")),
            "hsaf_ssm_risk": safe_int(row.get("hsaf_ssm_risk")),
            "swi_risk": safe_int(row.get("swi_risk")),
            "P30_mm": safe_float(row.get("P30_mm"), 1),
            "P90_mm": safe_float(row.get("P90_mm"), 1),
            "P730_mm": safe_float(row.get("P730_mm"), 1),
            "HSAF_SSM_pct": safe_float(row.get("HSAF_SSM_pct"), 1),
            "SWI010_pct": safe_float(row.get("SWI010_pct"), 1),
            "legal_status": row.get("legal_status"),
        },
        "geometry": geometry,
    }


def rebuild_source_municipality_grids() -> None:
    if not GRID_ASSIGNMENT_CSV.exists():
        raise FileNotFoundError(
            f"Missing source grid geometry. Expected {SOURCE_GRID_DIR} or {GRID_ASSIGNMENT_CSV}"
        )

    print(f"Rebuilding source municipality grid geometries from {GRID_ASSIGNMENT_CSV}")
    df = pd.read_csv(
        GRID_ASSIGNMENT_CSV,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "cell_polygon_lks92_wkt": "string",
        },
        usecols=["grid_id", "municipality_code", "cell_polygon_lks92_wkt"],
        low_memory=False,
    )
    df = df[
        df["grid_id"].notna()
        & df["municipality_code"].notna()
        & df["cell_polygon_lks92_wkt"].notna()
    ].copy()
    df["municipality_code"] = df["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["grid_id"] = df["grid_id"].astype(str)

    geometry = df["cell_polygon_lks92_wkt"].map(wkt.loads)
    gdf = gpd.GeoDataFrame(df[["grid_id", "municipality_code"]], geometry=geometry, crs="EPSG:3059").to_crs(
        "EPSG:4326"
    )

    if SOURCE_GRID_DIR.exists():
        shutil.rmtree(SOURCE_GRID_DIR)
    SOURCE_GRID_DIR.mkdir(parents=True, exist_ok=True)

    for code, part in gdf.groupby("municipality_code", sort=True):
        features = [
            {
                "type": "Feature",
                "properties": {"grid_id": str(row.grid_id)},
                "geometry": row.geometry.__geo_interface__,
            }
            for row in part.itertuples(index=False)
        ]
        write_json(SOURCE_GRID_DIR / f"{code}.geojson", {"type": "FeatureCollection", "features": features})


def load_grid_geometries() -> tuple[dict[str, dict], dict[str, list[str]]]:
    if not any(SOURCE_GRID_DIR.glob("*.geojson")):
        rebuild_source_municipality_grids()

    geometry_by_grid_id: dict[str, dict] = {}
    grid_ids_by_code: dict[str, list[str]] = {}
    for path in sorted(SOURCE_GRID_DIR.glob("*.geojson")):
        code = path.stem
        payload = read_json(path)
        grid_ids_by_code[code] = []
        for feature in payload["features"]:
            grid_id = str(feature["properties"]["grid_id"])
            geometry_by_grid_id[grid_id] = feature["geometry"]
            grid_ids_by_code[code].append(grid_id)
    return geometry_by_grid_id, grid_ids_by_code


def build_overview(template: dict, summary: pd.DataFrame) -> dict:
    summary_by_code = summary.set_index("municipality_code").to_dict(orient="index")
    features = []
    for feature in template["features"]:
        props = feature["properties"].copy()
        code = str(props["municipality_code"])
        row = summary_by_code.get(code)
        if row is None:
            continue
        props.update(
            {
                "municipality_name": row["municipality_name"],
                "risk_level": overview_level(row["p90_kiri_risk"]),
                "risk_color_basis": "ceil_p90_kiri_risk",
                "grid_cell_count": int(row["grid_cell_count"]),
                "valid_grid_cell_count": int(row["valid_grid_cell_count"]),
                "high_risk_percent": round(float(row["percent_cells_risk_4_5"]), 1),
            }
        )
        features.append({"type": "Feature", "properties": props, "geometry": feature["geometry"]})
    return {"type": "FeatureCollection", "features": features}


def build_manifest(old_manifest: dict, summary: pd.DataFrame, date_text: str) -> dict:
    manifest = {}
    for row in summary.to_dict(orient="records"):
        code = str(row["municipality_code"])
        if code not in old_manifest:
            continue
        high_percent = round(float(row["percent_cells_risk_4_5"]), 1)
        manifest[code] = {
            "date": date_text,
            "municipality_code": code,
            "municipality_name": row["municipality_name"],
            "grid_file": f"dates/{date_text}/municipality_grids/{code}.geojson",
            "boundary_file": old_manifest[code]["boundary_file"],
            "grid_cell_count": int(row["grid_cell_count"]),
            "valid_grid_cell_count": int(row["valid_grid_cell_count"]),
            "overall_risk": overview_level(row["p90_kiri_risk"]),
            "median_kiri_risk": safe_float(row["median_kiri_risk"], 1),
            "p90_kiri_risk": safe_float(row["p90_kiri_risk"], 1),
            "max_kiri_risk": safe_int(row["max_kiri_risk"]),
            "high_risk_percent": high_percent,
            "dominant_factors": clean_reason_text(row.get("dominant_reasons"))[:5],
            "recommendation": recommendation_for(pd.Series(row)),
            "confidence_summary": row.get("confidence_summary"),
        }
    return manifest


def write_date_grids(date_dir: Path, normalized: pd.DataFrame, geometry_by_grid_id: dict[str, dict]) -> int:
    grid_dir = date_dir / "municipality_grids"
    grid_dir.mkdir(parents=True, exist_ok=True)
    normalized = normalized[
        normalized["municipality_code"].notna()
        & normalized["kiri_risk_level"].notna()
        & normalized["grid_id"].notna()
    ].copy()
    normalized["municipality_code"] = normalized["municipality_code"].astype(str)
    normalized["grid_id"] = normalized["grid_id"].astype(str)

    count = 0
    for code, part in normalized.groupby("municipality_code", sort=True):
        features = []
        for _, row in part.iterrows():
            geometry = geometry_by_grid_id.get(str(row["grid_id"]))
            if geometry is None:
                continue
            features.append(grid_feature(row, geometry))
        write_json(grid_dir / f"{code}.geojson", {"type": "FeatureCollection", "features": features})
        count += 1
    return count


def normalize_indicator_file(path: Path, config: dict, name_map: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = pd.read_csv(
        path,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "municipality_atvk": "string",
            "municipality_name": "string",
        },
        low_memory=False,
    )
    codes = df["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    repaired_names = codes.map(name_map)
    mask = repaired_names.notna()
    df.loc[mask, "municipality_name"] = repaired_names[mask]
    normalized, qc = add_variable_risks(df, config)
    normalized = add_combined_risk(normalized, config)
    summary = municipality_summary(normalized)
    return normalized, summary, qc


def main() -> None:
    config = load_config(CONFIG_PATH)
    name_map = load_name_map()
    overview_template = read_json(SOURCE_MUNICIPALITIES)
    old_manifest = read_json(SOURCE_MANIFEST)
    geometry_by_grid_id, _grid_ids_by_code = load_grid_geometries()

    if DATE_DATA_DIR.exists():
        shutil.rmtree(DATE_DATA_DIR)
    DATE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    indicator_files = sorted(INDICATOR_DIR.glob("grid_indicators_P30_P90_P730_HSAF_SWI_*.csv"))
    if not indicator_files:
        raise FileNotFoundError(f"No daily indicator CSV files found in {INDICATOR_DIR}")

    dates = []
    for path in indicator_files:
        date_text = path.stem.replace("grid_indicators_P30_P90_P730_HSAF_SWI_", "")
        print(f"Preparing frontend date {date_text}")
        date_dir = DATE_DATA_DIR / date_text
        date_dir.mkdir(parents=True, exist_ok=True)

        normalized, summary, qc = normalize_indicator_file(path, config, name_map)
        grid_file_count = write_date_grids(date_dir, normalized, geometry_by_grid_id)
        overview = build_overview(overview_template, summary)
        manifest = build_manifest(old_manifest, summary, date_text)
        write_json(date_dir / "overview.geojson", overview)
        write_json(date_dir / "manifest.json", manifest)

        risk_counts = {
            str(level): int((normalized["kiri_risk_level"] == level).sum())
            for level in range(1, 6)
        }
        dates.append(
            {
                "date": date_text,
                "label": date_text,
                "overview_file": f"dates/{date_text}/overview.geojson",
                "manifest_file": f"dates/{date_text}/manifest.json",
                "grid_file_count": grid_file_count,
                "municipality_count": int(len(summary)),
                "row_count": int(len(normalized)),
                "risk_counts": risk_counts,
                "swi_missing": int(pd.to_numeric(normalized["SWI010_pct"], errors="coerce").isna().sum()),
                "hsaf_missing": int(pd.to_numeric(normalized["HSAF_SSM_pct"], errors="coerce").isna().sum()),
                "data_quality": qc,
            }
        )

    calendar = {
        "generated_from": str(INDICATOR_DIR),
        "date_count": len(dates),
        "default_date": dates[-1]["date"],
        "dates": dates,
        "performance_note": "The browser loads one date overview and one municipality grid at a time.",
    }
    write_json(FRONTEND_DATA / "calendar_manifest.json", calendar)
    print(json.dumps({k: calendar[k] for k in ["date_count", "default_date", "performance_note"]}, indent=2))


if __name__ == "__main__":
    main()
