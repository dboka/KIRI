from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUT_ROOT = PROJECT_DIR / "DATA_LAST_60"


def fix_mojibake(value: object) -> str:
    text = str(value)
    for encoding in ("cp1252", "latin1"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if "\ufffd" not in candidate:
            return candidate
    return text


def load_name_map() -> dict[str, str]:
    novadi = gpd.read_file(BASE_DIR / "Novadi.shp", encoding="cp1257", ignore_geometry=True)
    cities = gpd.read_file(BASE_DIR / "Pilsetas.shp", encoding="cp1257", ignore_geometry=True)
    cities = cities[pd.to_numeric(cities["CITY_TYPE"], errors="coerce") == 2].copy()

    mapping = {
        str(row["CODE"]): fix_mojibake(row["LABEL"])
        for _, row in pd.concat([novadi[["CODE", "LABEL"]], cities[["CODE", "LABEL"]]], ignore_index=True).iterrows()
    }
    mapping.update(
        {
            "100015243": "Līvānu nov.",
            "100016300": "Varakļānu nov.",
            "100016462": "Augšdaugavas nov.",
            "100016583": "Mārupes nov.",
            "100016743": "Krāslavas nov.",
        }
    )
    mapping["100003044"] = "Liepāja"
    return mapping


def repair_file(path: Path, mapping: dict[str, str]) -> tuple[int, int]:
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
    if "municipality_code" not in df.columns or "municipality_name" not in df.columns:
        return 0, 0
    before_missing = int(df["municipality_name"].isna().sum())
    codes = df["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    repaired = codes.map(mapping)
    mask = repaired.notna()
    df.loc[mask, "municipality_name"] = repaired[mask]
    df.to_csv(path, index=False, encoding="utf-8")
    return int(mask.sum()), before_missing


def main() -> None:
    mapping = load_name_map()
    folders = [
        OUT_ROOT / "precip_grids",
        OUT_ROOT / "indicator_grids",
    ]
    repaired_files = 0
    repaired_rows = 0
    for folder in folders:
        for path in sorted(folder.glob("*.csv")):
            rows, _missing = repair_file(path, mapping)
            if rows:
                repaired_files += 1
                repaired_rows += rows
                print(f"Repaired {rows} rows: {path}")
    print(f"Done. Files repaired: {repaired_files}; rows touched: {repaired_rows}")


if __name__ == "__main__":
    main()
