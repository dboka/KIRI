from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
GRID_DIR = FRONTEND_DATA / "municipality_grids"
NORMALIZED_DIR = BASE_DIR / "outputs" / "kiri_normalized"
NORMALIZED_GPKG = NORMALIZED_DIR / "kiri_grid_2026_06_15.gpkg"
SUMMARY_CSV = NORMALIZED_DIR / "municipality_summary_2026_06_15.csv"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def clean_reason_text(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [part for part in str(value).split("|") if part]


def safe_float(value: object, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def safe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def grid_feature(row: pd.Series) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "grid_id": str(row["grid_id"]),
            "kiri_risk_level": safe_int(row["kiri_risk_level"]),
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
        "geometry": mapping(row.geometry),
    }


def update_overview_and_manifest(summary: pd.DataFrame) -> None:
    municipalities_path = FRONTEND_DATA / "municipalities.geojson"
    manifest_path = FRONTEND_DATA / "municipality_manifest.json"
    municipalities = load_json(municipalities_path)
    old_manifest = load_json(manifest_path)

    summary_by_code = summary.set_index("municipality_code").to_dict(orient="index")
    manifest = {}

    for feature in municipalities["features"]:
        props = feature["properties"]
        code = str(props["municipality_code"])
        row = summary_by_code.get(code)
        if row is None:
            continue

        overview_risk = int(row["p90_kiri_risk"])
        high_percent = round(float(row["percent_cells_risk_4_5"]), 1)
        dominant = clean_reason_text(row.get("dominant_reasons"))

        props.update(
            {
                "risk_level": overview_risk,
                "risk_color_basis": "p90_kiri_risk",
                "grid_cell_count": int(row["grid_cell_count"]),
                "valid_grid_cell_count": int(row["valid_grid_cell_count"]),
                "high_risk_percent": high_percent,
            }
        )

        manifest[code] = {
            "municipality_code": code,
            "municipality_name": row["municipality_name"],
            "grid_file": f"municipality_grids/{code}.geojson",
            "boundary_file": old_manifest[code]["boundary_file"],
            "grid_cell_count": int(row["grid_cell_count"]),
            "valid_grid_cell_count": int(row["valid_grid_cell_count"]),
            "overall_risk": overview_risk,
            "median_kiri_risk": safe_float(row["median_kiri_risk"], 1),
            "p90_kiri_risk": safe_float(row["p90_kiri_risk"], 1),
            "max_kiri_risk": safe_int(row["max_kiri_risk"]),
            "high_risk_percent": high_percent,
            "dominant_factors": dominant[:5],
            "recommendation": "Provizoriska v0.1 karte: pārbaudi grid šūnu un vietējos apstākļus pirms lēmuma.",
            "confidence_summary": row.get("confidence_summary"),
        }

    write_json(municipalities_path, municipalities)
    write_json(manifest_path, manifest)


def write_grid_files() -> None:
    gdf = gpd.read_file(NORMALIZED_GPKG, layer="kiri_grid_2026_06_15")
    gdf = gdf[gdf["municipality_code"].notna() & gdf["kiri_risk_level"].notna()].copy()
    gdf["municipality_code"] = gdf["municipality_code"].astype(str)
    gdf = gdf.to_crs("EPSG:4326")

    GRID_DIR.mkdir(parents=True, exist_ok=True)
    for path in GRID_DIR.glob("*.geojson"):
        path.unlink()

    for code, part in gdf.groupby("municipality_code", sort=True):
        features = [grid_feature(row) for _, row in part.iterrows()]
        write_json(GRID_DIR / f"{code}.geojson", {"type": "FeatureCollection", "features": features})


def main() -> None:
    summary = pd.read_csv(SUMMARY_CSV, dtype={"municipality_code": "string"})
    write_grid_files()
    update_overview_and_manifest(summary)

    metadata = {
        "source": str(NORMALIZED_GPKG),
        "municipality_count": int(len(summary)),
        "grid_file_count": len(list(GRID_DIR.glob("*.geojson"))),
        "projection_note": "Frontend GeoJSON is preprojected to EPSG:4326 for Leaflet; no browser-side reprojection.",
        "interaction_note": "Municipality hover only. Grid cells update stats on click only.",
    }
    write_json(FRONTEND_DATA / "frontend_kiri_data_metadata.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
