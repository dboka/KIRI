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
    validation_summary,
)
from repair_last_60_municipality_names import load_name_map


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
LAST_60_DIR = PROJECT_DIR / "DATA_LAST_60"
INDICATOR_DIR = LAST_60_DIR / "indicator_grids"
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
DATE_DATA_DIR = FRONTEND_DATA / "dates"
STATIC_DIR = FRONTEND_DATA / "grid_static"
VALUES_DIR = FRONTEND_DATA / "grid_values"
SOURCE_MUNICIPALITIES = FRONTEND_DATA / "municipalities.geojson"
SOURCE_MANIFEST = FRONTEND_DATA / "municipality_manifest.json"
CONFIG_PATH = BASE_DIR / "config" / "normalization_v01.yaml"
GRID_ASSIGNMENT_CSV = BASE_DIR / "outputs" / "grid_1km_municipalities_centroid.csv"
HSAF_FALLBACK_DAYS = 3

VALUE_FIELDS = [
    "cell_id",
    "date",
    "grid_id",
    "kiri_risk_level",
    "kiri_risk_label_lv",
    "active_risk",
    "p730_context",
    "p730_modifier",
    "final_risk_level",
    "final_risk_label_lv",
    "main_reasons",
    "active_reasons",
    "context_reasons",
    "data_warnings",
    "confidence",
    "p30_risk",
    "p90_risk",
    "p730_risk",
    "hsaf_ssm_risk",
    "swi_risk",
    "P30_mm",
    "P90_mm",
    "P730_mm",
    "hsaf_ssm",
    "swi",
    "HSAF_SSM_pct",
    "SWI010_pct",
    "hsaf_source_date",
    "hsaf_age_days",
    "hsaf_is_stale",
    "hsaf_fallback_used",
    "legal_status",
    "map_visible",
]


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


def compact_value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 2)
    if hasattr(value, "item"):
        return compact_value(value.item())
    return value


def compact_row(row: pd.Series) -> list:
    values = []
    for field in VALUE_FIELDS:
        value = row.get(field)
        if field in {"main_reasons", "active_reasons", "context_reasons", "data_warnings"}:
            values.append(clean_reason_text(value))
        else:
            values.append(compact_value(value))
    return values


def rebuild_static_grid_geometries() -> None:
    if not GRID_ASSIGNMENT_CSV.exists():
        raise FileNotFoundError(
            f"Missing static grid geometry. Expected {STATIC_DIR} or {GRID_ASSIGNMENT_CSV}"
        )

    print(f"Rebuilding static grid geometries from {GRID_ASSIGNMENT_CSV}")
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

    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    for code, part in gdf.groupby("municipality_code", sort=True):
        features = [
            {
                "type": "Feature",
                "properties": {"grid_id": str(row.grid_id)},
                "geometry": row.geometry.__geo_interface__,
            }
            for row in part.itertuples(index=False)
        ]
        write_json(STATIC_DIR / f"{code}.geojson", {"type": "FeatureCollection", "features": features})


def ensure_static_grid_geometries() -> None:
    if not any(STATIC_DIR.glob("*.geojson")):
        rebuild_static_grid_geometries()


def build_static_grid_geometry() -> int:
    ensure_static_grid_geometries()
    return len(list(STATIC_DIR.glob("*.geojson")))


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
            "static_grid_file": f"grid_static/{code}.geojson",
            "grid_values_file": f"grid_values/{date_text}/{code}.json",
            "boundary_file": old_manifest[code]["boundary_file"],
            "grid_cell_count": int(row["grid_cell_count"]),
            "valid_grid_cell_count": int(row["valid_grid_cell_count"]),
            "overall_risk": overview_level(row["p90_kiri_risk"]),
            "median_kiri_risk": safe_float(row["median_kiri_risk"], 1),
            "p90_kiri_risk": safe_float(row["p90_kiri_risk"], 1),
            "max_kiri_risk": safe_int(row["max_kiri_risk"]),
            "high_risk_percent": high_percent,
            "dominant_factors": clean_reason_text(row.get("dominant_reasons"))[:5],
            "context_factors": clean_reason_text(row.get("dominant_context_reasons"))[:5],
            "recommendation": recommendation_for(pd.Series(row)),
            "confidence_summary": row.get("confidence_summary"),
        }
    return manifest


def write_daily_values(date_text: str, normalized: pd.DataFrame) -> int:
    values_dir = VALUES_DIR / date_text
    if values_dir.exists():
        shutil.rmtree(values_dir)
    values_dir.mkdir(parents=True, exist_ok=True)

    normalized = normalized[
        normalized["municipality_code"].notna()
        & normalized["grid_id"].notna()
    ].copy()
    normalized["municipality_code"] = normalized["municipality_code"].astype(str)
    normalized["grid_id"] = normalized["grid_id"].astype(str)

    count = 0
    for code, part in normalized.groupby("municipality_code", sort=True):
        rows = [compact_row(row) for _, row in part.iterrows()]
        write_json(values_dir / f"{code}.json", {"fields": VALUE_FIELDS, "rows": rows})
        count += 1
    return count


def apply_hsaf_fallback(
    df: pd.DataFrame,
    date_text: str,
    hsaf_history: dict[str, tuple[pd.Timestamp, float]],
) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    date = pd.Timestamp(date_text)
    out["grid_id"] = out["grid_id"].astype(str)
    out["HSAF_SSM_pct"] = pd.to_numeric(out["HSAF_SSM_pct"], errors="coerce")
    out["hsaf_source_date"] = date_text
    out["hsaf_age_days"] = 0
    out["hsaf_is_stale"] = False
    out["hsaf_fallback_used"] = False

    missing_mask = out["HSAF_SSM_pct"].isna()
    filled_count = 0
    still_missing_count = 0
    for idx in out.index[missing_mask]:
        grid_id = str(out.at[idx, "grid_id"])
        previous = hsaf_history.get(grid_id)
        if previous is None:
            still_missing_count += 1
            out.at[idx, "hsaf_source_date"] = None
            out.at[idx, "hsaf_age_days"] = None
            continue
        source_date, value = previous
        age_days = int((date - source_date).days)
        if 1 <= age_days <= HSAF_FALLBACK_DAYS:
            out.at[idx, "HSAF_SSM_pct"] = value
            out.at[idx, "hsaf_source_date"] = source_date.strftime("%Y-%m-%d")
            out.at[idx, "hsaf_age_days"] = age_days
            out.at[idx, "hsaf_is_stale"] = True
            out.at[idx, "hsaf_fallback_used"] = True
            filled_count += 1
        else:
            still_missing_count += 1
            out.at[idx, "hsaf_source_date"] = None
            out.at[idx, "hsaf_age_days"] = None

    current_valid = out["HSAF_SSM_pct"].notna() & ~out["hsaf_fallback_used"].astype(bool)
    for grid_id, value in out.loc[current_valid, ["grid_id", "HSAF_SSM_pct"]].itertuples(index=False):
        hsaf_history[str(grid_id)] = (date, float(value))

    return out, {
        "hsaf_fallback_filled": filled_count,
        "hsaf_missing_after_fallback": still_missing_count,
        "hsaf_fallback_max_age_days": HSAF_FALLBACK_DAYS,
    }


def normalize_indicator_file(
    path: Path,
    config: dict,
    name_map: dict[str, str],
    hsaf_history: dict[str, tuple[pd.Timestamp, float]],
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
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
    date_text = path.stem.replace("grid_indicators_P30_P90_P730_HSAF_SWI_", "")
    df, hsaf_qc = apply_hsaf_fallback(df, date_text, hsaf_history)
    codes = df["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    repaired_names = codes.map(name_map)
    mask = repaired_names.notna()
    df.loc[mask, "municipality_name"] = repaired_names[mask]
    normalized, qc = add_variable_risks(df, config)
    normalized = add_combined_risk(normalized, config)
    qc["hsaf_ssm"].update(hsaf_qc)
    summary = municipality_summary(normalized)
    return normalized, summary, qc


def main() -> None:
    config = load_config(CONFIG_PATH)
    name_map = load_name_map()
    overview_template = read_json(SOURCE_MUNICIPALITIES)
    old_manifest = read_json(SOURCE_MANIFEST)
    static_grid_count = build_static_grid_geometry()

    if DATE_DATA_DIR.exists():
        shutil.rmtree(DATE_DATA_DIR)
    DATE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if VALUES_DIR.exists():
        shutil.rmtree(VALUES_DIR)
    VALUES_DIR.mkdir(parents=True, exist_ok=True)

    indicator_files = sorted(INDICATOR_DIR.glob("grid_indicators_P30_P90_P730_HSAF_SWI_*.csv"))
    if not indicator_files:
        raise FileNotFoundError(f"No daily indicator CSV files found in {INDICATOR_DIR}")

    dates = []
    hsaf_history: dict[str, tuple[pd.Timestamp, float]] = {}
    for path in indicator_files:
        date_text = path.stem.replace("grid_indicators_P30_P90_P730_HSAF_SWI_", "")
        print(f"Preparing frontend date {date_text}")
        date_dir = DATE_DATA_DIR / date_text
        date_dir.mkdir(parents=True, exist_ok=True)

        normalized, summary, qc = normalize_indicator_file(path, config, name_map, hsaf_history)
        normalized["date"] = date_text
        normalized["cell_id"] = normalized["grid_id"].astype(str)
        grid_file_count = write_daily_values(date_text, normalized)
        overview = build_overview(overview_template, summary)
        manifest = build_manifest(old_manifest, summary, date_text)
        write_json(date_dir / "overview.geojson", overview)
        write_json(date_dir / "manifest.json", manifest)

        visible_normalized = normalized[normalized["map_visible"].astype(bool)].copy()
        risk_counts = {
            str(level): int((normalized["kiri_risk_level"] == level).sum())
            for level in range(1, 6)
        }
        visible_risk_counts = {
            str(level): int((visible_normalized["final_risk_level"] == level).sum())
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
                "risk_counts": visible_risk_counts,
                "raw_risk_counts": risk_counts,
                "swi_missing": int(pd.to_numeric(normalized["SWI010_pct"], errors="coerce").isna().sum()),
                "hsaf_missing": int(pd.to_numeric(normalized["HSAF_SSM_pct"], errors="coerce").isna().sum()),
                "data_quality": qc,
                "validation_summary": validation_summary(normalized),
            }
        )

    calendar = {
        "generated_from": str(INDICATOR_DIR),
        "date_count": len(dates),
        "default_date": dates[-1]["date"],
        "dates": dates,
        "performance_note": "Static geometry is generated once; the browser loads one date overview and one municipality value file at a time.",
        "data_layout": {
            "overview": "dates/<date>/overview.geojson",
            "municipality_manifest": "dates/<date>/manifest.json",
            "static_grid_geometry": "grid_static/<municipality_code>.geojson",
            "daily_grid_values": "grid_values/<date>/<municipality_code>.json",
        },
    }
    write_json(FRONTEND_DATA / "calendar_manifest.json", calendar)
    print(
        json.dumps(
            {
                **{k: calendar[k] for k in ["date_count", "default_date", "performance_note"]},
                "static_grid_files": static_grid_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
