from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import box


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = BASE_DIR / "config" / "normalization_v01.yaml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify_threshold(value: float, thresholds: list[float]) -> float:
    if pd.isna(value) or not np.isfinite(value):
        return np.nan
    return float(1 + sum(float(value) >= float(threshold) for threshold in thresholds))


def maybe_convert_fraction_to_percent(series: pd.Series, unit_handling: str | None) -> tuple[pd.Series, bool]:
    numeric = pd.to_numeric(series, errors="coerce")
    if unit_handling != "auto_fraction_to_percent":
        return numeric, False

    valid = numeric.dropna()
    if valid.empty:
        return numeric, False

    # If all non-missing values fit 0..1, treat the raster as fractional.
    if valid.min() >= 0 and valid.max() <= 1.0:
        return numeric * 100.0, True
    return numeric, False


def add_variable_risks(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    qc: dict[str, Any] = {}

    for variable_name, variable_config in config["variables"].items():
        input_col = variable_config["input_column"]
        output_col = variable_config["output_column"]
        thresholds = variable_config["thresholds"]

        if input_col not in out.columns:
            raise KeyError(f"Missing input column for {variable_name}: {input_col}")

        numeric, converted_fraction = maybe_convert_fraction_to_percent(
            out[input_col], variable_config.get("unit_handling")
        )
        out[input_col] = numeric
        out[output_col] = numeric.apply(lambda value: classify_threshold(value, thresholds)).astype("Int64")

        valid = numeric.dropna()
        qc[variable_name] = {
            "input_column": input_col,
            "risk_column": output_col,
            "thresholds": thresholds,
            "converted_fraction_to_percent": converted_fraction,
            "missing": int(numeric.isna().sum()),
            "min": round(float(valid.min()), 3) if not valid.empty else None,
            "mean": round(float(valid.mean()), 3) if not valid.empty else None,
            "max": round(float(valid.max()), 3) if not valid.empty else None,
            "risk_counts": {
                str(level): int((out[output_col] == level).sum())
                for level in range(1, 6)
            },
        }

    return out, qc


def second_highest(values: list[int]) -> int | None:
    valid = sorted([int(value) for value in values if pd.notna(value)], reverse=True)
    if len(valid) < 3:
        return None
    return valid[1]


def confidence_for(valid_count: int) -> str:
    if valid_count < 3:
        return "low"
    if valid_count < 5:
        return "medium"
    return "high"


def reason_code(prefix: str, risk: int) -> str | None:
    if risk == 5:
        return f"{prefix}_very_high"
    if risk == 4:
        return f"{prefix}_high"
    return None


def add_combined_risk(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    risk_cols = [variable["output_column"] for variable in config["variables"].values()]
    reason_prefixes = {
        variable["output_column"]: variable["reason_prefix"]
        for variable in config["variables"].values()
    }

    labels = {int(level): label for level, label in config["risk_labels_lv"].items()}
    method = config["normalization_method"]
    legal = config["legal_placeholder"]

    combined_levels = []
    labels_lv = []
    reasons = []
    valid_counts = []
    confidences = []

    for _, row in out.iterrows():
        risks = [row[col] for col in risk_cols]
        valid_risks = [int(value) for value in risks if pd.notna(value)]
        valid_count = len(valid_risks)
        level = second_highest(valid_risks)

        row_reasons: list[str] = []
        if level is None:
            row_reasons.append("insufficient_valid_inputs")
        else:
            for col in risk_cols:
                value = row[col]
                if pd.isna(value):
                    continue
                code = reason_code(reason_prefixes[col], int(value))
                if code and int(value) >= int(level):
                    row_reasons.append(code)

        combined_levels.append(level)
        labels_lv.append(labels.get(int(level), None) if level is not None else None)
        reasons.append("|".join(row_reasons))
        valid_counts.append(valid_count)
        confidences.append(confidence_for(valid_count))

    out["valid_variable_count"] = valid_counts
    out["kiri_risk_level"] = pd.Series(combined_levels, dtype="Int64")
    out["kiri_risk_label_lv"] = labels_lv
    out["main_reasons"] = reasons
    out["normalization_method"] = method
    out["confidence"] = confidences
    out["legal_status"] = legal["legal_status"]
    out["hard_stop_active"] = bool(legal["hard_stop_active"])
    out["block_reason"] = legal["block_reason"]
    return out


def cell_geometries(df: pd.DataFrame, cell_size_m: float) -> gpd.GeoSeries:
    half = cell_size_m / 2.0
    geometries = [
        box(float(x) - half, float(y) - half, float(x) + half, float(y) + half)
        for x, y in zip(df["x"], df["y"])
    ]
    return gpd.GeoSeries(geometries)


def municipality_summary(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["municipality_code"].notna() & df["kiri_risk_level"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()

    def dominant_reasons(series: pd.Series) -> str:
        counts: dict[str, int] = {}
        for value in series.dropna():
            for reason in str(value).split("|"):
                reason = reason.strip()
                if reason:
                    counts[reason] = counts.get(reason, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return "|".join(reason for reason, _count in ordered[:5])

    def confidence_summary(series: pd.Series) -> str:
        counts = series.value_counts(dropna=True)
        if counts.empty:
            return "unknown"
        return "|".join(f"{idx}:{int(value)}" for idx, value in counts.items())

    grouped = valid.groupby(["municipality_code", "municipality_name"], dropna=False)
    summary = grouped.agg(
        grid_cell_count=("grid_id", "count"),
        valid_grid_cell_count=("kiri_risk_level", "count"),
        median_kiri_risk=("kiri_risk_level", "median"),
        p90_kiri_risk=("kiri_risk_level", lambda s: float(np.nanpercentile(s.astype(float), 90))),
        max_kiri_risk=("kiri_risk_level", "max"),
        percent_cells_risk_4_5=("kiri_risk_level", lambda s: float((s.astype(float) >= 4).mean() * 100)),
        dominant_reasons=("main_reasons", dominant_reasons),
        confidence_summary=("confidence", confidence_summary),
    ).reset_index()

    summary["median_kiri_risk"] = summary["median_kiri_risk"].round(2)
    summary["p90_kiri_risk"] = summary["p90_kiri_risk"].round(2)
    summary["percent_cells_risk_4_5"] = summary["percent_cells_risk_4_5"].round(2)
    return summary[
        [
            "municipality_name",
            "municipality_code",
            "grid_cell_count",
            "valid_grid_cell_count",
            "median_kiri_risk",
            "p90_kiri_risk",
            "max_kiri_risk",
            "percent_cells_risk_4_5",
            "dominant_reasons",
            "confidence_summary",
        ]
    ]


def main() -> None:
    config = load_config(DEFAULT_CONFIG)
    input_path = BASE_DIR / config["input"]["indicator_csv"]
    output_dir = BASE_DIR / config["output"]["directory"]
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        input_path,
        dtype={
            "grid_id": "string",
            "municipality_code": "string",
            "municipality_atvk": "string",
            "municipality_name": "string",
        },
    )

    normalized, qc = add_variable_risks(df, config)
    normalized = add_combined_risk(normalized, config)

    csv_path = output_dir / config["output"]["csv"]
    normalized.to_csv(csv_path, index=False, encoding="utf-8")

    crs_epsg = int(config["input"]["crs_epsg"])
    cell_size_m = float(config["input"]["cell_size_m"])
    gdf = gpd.GeoDataFrame(
        normalized,
        geometry=cell_geometries(normalized, cell_size_m),
        crs=f"EPSG:{crs_epsg}",
    )

    gpkg_path = output_dir / config["output"]["gpkg"]
    if gpkg_path.exists():
        gpkg_path.unlink()
    gdf.to_file(gpkg_path, layer="kiri_grid_2026_06_15", driver="GPKG")

    geojson_path = output_dir / config["output"]["geojson"]
    gdf.to_crs("EPSG:4326").to_file(geojson_path, driver="GeoJSON")

    summary = municipality_summary(normalized)
    summary_path = output_dir / config["output"]["municipality_summary_csv"]
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    metadata = {
        "target_date": config["target_date"],
        "normalization_method": config["normalization_method"],
        "input": str(input_path),
        "outputs": {
            "csv": str(csv_path),
            "geojson": str(geojson_path),
            "gpkg": str(gpkg_path),
            "municipality_summary_csv": str(summary_path),
        },
        "row_count": int(len(normalized)),
        "kiri_risk_counts": {
            str(level): int((normalized["kiri_risk_level"] == level).sum())
            for level in range(1, 6)
        },
        "confidence_counts": {
            key: int(value)
            for key, value in normalized["confidence"].value_counts(dropna=False).to_dict().items()
        },
        "data_quality": qc,
    }
    metadata_path = output_dir / config["output"]["metadata_json"]
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("KIRI-LV v0.1 provisional normalization complete")
    print("Rows:", len(normalized))
    print("Input:", input_path)
    print("CSV:", csv_path)
    print("GeoJSON:", geojson_path)
    print("GPKG:", gpkg_path)
    print("Municipality summary:", summary_path)
    print("Risk counts:", metadata["kiri_risk_counts"])
    print("Confidence counts:", metadata["confidence_counts"])
    print("Data quality:")
    print(json.dumps(qc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
