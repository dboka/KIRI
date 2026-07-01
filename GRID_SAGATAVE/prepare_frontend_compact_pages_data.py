from __future__ import annotations

import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
DATES_DIR = FRONTEND_DATA / "dates"
STATIC_DIR = FRONTEND_DATA / "grid_static"
VALUES_DIR = FRONTEND_DATA / "grid_values"

VALUE_FIELDS = [
    "grid_id",
    "kiri_risk_level",
    "kiri_risk_label_lv",
    "main_reasons",
    "confidence",
    "p30_risk",
    "p90_risk",
    "p730_risk",
    "hsaf_ssm_risk",
    "swi_risk",
    "P30_mm",
    "P90_mm",
    "P730_mm",
    "HSAF_SSM_pct",
    "SWI010_pct",
    "legal_status",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def compact_value(value):
    if isinstance(value, float):
        return round(value, 2)
    return value


def build_static_geometry(source_date_dir: Path) -> int:
    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in sorted((source_date_dir / "municipality_grids").glob("*.geojson")):
        payload = read_json(path)
        features = []
        for feature in payload["features"]:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"grid_id": str(feature["properties"]["grid_id"])},
                    "geometry": feature["geometry"],
                }
            )
        write_json(STATIC_DIR / path.name, {"type": "FeatureCollection", "features": features})
        count += 1
    return count


def build_daily_values() -> int:
    if VALUES_DIR.exists():
        shutil.rmtree(VALUES_DIR)
    VALUES_DIR.mkdir(parents=True, exist_ok=True)

    file_count = 0
    for date_dir in sorted(path for path in DATES_DIR.iterdir() if path.is_dir()):
        out_dir = VALUES_DIR / date_dir.name
        for path in sorted((date_dir / "municipality_grids").glob("*.geojson")):
            payload = read_json(path)
            rows = []
            for feature in payload["features"]:
                props = feature["properties"]
                rows.append([compact_value(props.get(field)) for field in VALUE_FIELDS])
            write_json(out_dir / f"{path.stem}.json", {"fields": VALUE_FIELDS, "rows": rows})
            file_count += 1
    return file_count


def update_manifests() -> None:
    calendar = read_json(FRONTEND_DATA / "calendar_manifest.json")
    for item in calendar["dates"]:
        manifest_path = FRONTEND_DATA / item["manifest_file"]
        manifest = read_json(manifest_path)
        for code, entry in manifest.items():
            entry["static_grid_file"] = f"grid_static/{code}.geojson"
            entry["grid_values_file"] = f"grid_values/{item['date']}/{code}.json"
            entry.pop("grid_file", None)
        write_json(manifest_path, manifest)

    calendar["data_layout"] = {
        "overview": "dates/<date>/overview.geojson",
        "municipality_manifest": "dates/<date>/manifest.json",
        "static_grid_geometry": "grid_static/<municipality_code>.geojson",
        "daily_grid_values": "grid_values/<date>/<municipality_code>.json",
    }
    write_json(FRONTEND_DATA / "calendar_manifest.json", calendar)


def main() -> None:
    date_dirs = sorted(path for path in DATES_DIR.iterdir() if path.is_dir())
    if not date_dirs:
        raise FileNotFoundError(f"No date folders found in {DATES_DIR}")

    static_count = build_static_geometry(date_dirs[0])
    values_count = build_daily_values()
    update_manifests()
    print(
        json.dumps(
            {
                "static_grid_files": static_count,
                "daily_value_files": values_count,
                "static_dir": str(STATIC_DIR),
                "values_dir": str(VALUES_DIR),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
