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


def clamp_risk(value: int | float, lower: int = 1, upper: int = 5) -> int:
    return max(lower, min(upper, int(round(float(value)))))


def confidence_for(row: pd.Series) -> str:
    hsaf = row.get("hsaf_ssm_risk")
    swi = row.get("swi_risk")
    p30 = row.get("p30_risk")
    p90 = row.get("p90_risk")
    hsaf_age = row.get("hsaf_age_days", 0)
    hsaf_is_stale = bool(row.get("hsaf_is_stale", False)) and pd.notna(hsaf_age) and int(hsaf_age) > 0
    active_valid_count = sum(pd.notna(value) for value in [hsaf, swi, p30, p90])

    if pd.isna(hsaf) or active_valid_count < 3:
        return "low"
    if pd.notna(swi) and pd.notna(p30) and pd.notna(p90):
        return "medium" if hsaf_is_stale else "high"
    if pd.notna(p30) and pd.notna(p90):
        return "low" if hsaf_is_stale else "medium"
    return "low"


def pipe_join(values: list[str]) -> str:
    return "|".join(value for value in values if value)


def add_combined_risk(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    labels = {int(level): label for level, label in config["risk_labels_lv"].items()}
    method = config["normalization_method"]
    legal = config["legal_placeholder"]

    active_risks = []
    p730_contexts = []
    p730_modifiers = []
    final_levels = []
    labels_lv = []
    active_reasons = []
    context_reasons = []
    data_warnings = []
    confidences = []
    map_visible_values = []
    active_indicator_counts = []

    for _, row in out.iterrows():
        hsaf = row.get("hsaf_ssm_risk")
        swi = row.get("swi_risk")
        p30 = row.get("p30_risk")
        p90 = row.get("p90_risk")
        p730 = row.get("p730_risk")
        active_valid_count = sum(pd.notna(value) for value in [hsaf, swi, p30, p90])
        confidence = confidence_for(row)

        row_active_reasons: list[str] = []
        row_context_reasons: list[str] = []
        row_warnings: list[str] = []

        if pd.isna(hsaf):
            active_risk = None
            final_level = None
            p730_modifier = 0
            map_visible = False
            label = "Nav H-SAF augsnes mitruma datu"
            row_warnings.append("Nav H-SAF augsnes mitruma datu; šūna netiek attēlota")
        else:
            hsaf_i = int(hsaf)
            p30_i = int(p30) if pd.notna(p30) else 1
            p90_i = int(p90) if pd.notna(p90) else 1

            if pd.notna(swi):
                swi_i = int(swi)
                score = (0.40 * hsaf_i) + (0.25 * swi_i) + (0.25 * p30_i) + (0.10 * p90_i)
            else:
                swi_i = None
                score = (0.50 * hsaf_i) + (0.35 * p30_i) + (0.15 * p90_i)
                row_warnings.append("SWI nav pieejams, uzticamība samazināta")

            hsaf_age = row.get("hsaf_age_days", 0)
            if pd.notna(hsaf_age) and int(hsaf_age) > 0:
                row_warnings.append(f"H-SAF dati {int(hsaf_age)} dienas veci; uzticamība samazināta")

            active_risk = clamp_risk(score)

            if hsaf_i <= 2 and p30_i <= 3:
                active_risk = min(active_risk, 2)
            if hsaf_i <= 2 and p30_i >= 4:
                active_risk = min(active_risk, 3)
            if hsaf_i >= 4 and p30_i >= 3:
                active_risk = max(active_risk, 4)
            if hsaf_i >= 4 and swi_i is not None and swi_i >= 4:
                active_risk = max(active_risk, 4)
            if hsaf_i >= 5 and p30_i >= 4:
                active_risk = 5
            if hsaf_i >= 5 and swi_i is not None and swi_i >= 4:
                active_risk = 5

            if pd.notna(p730) and int(p730) >= 4 and active_risk >= 3:
                p730_modifier = 1
            else:
                p730_modifier = 0

            final_level = active_risk
            if p730_modifier and active_risk > 2:
                final_level = min(active_risk + 1, 4)
            if hsaf_i <= 2 and (swi_i is None or swi_i <= 2):
                final_level = min(final_level, 3)

            map_visible = True
            label = labels.get(int(final_level))

            if hsaf_i >= 3:
                row_active_reasons.append("H-SAF virsmas mitrums paaugstināts")
            if swi_i is not None and swi_i >= 3:
                row_active_reasons.append("Copernicus SWI rāda paaugstinātu profila mitrumu")
            if p30_i >= 3:
                row_active_reasons.append("P30 nokrišņi paaugstināti")
            if p90_i >= 4:
                row_active_reasons.append("P90 nokrišņu uzkrājums augsts")

        if pd.notna(p730) and int(p730) >= 4:
            p730_context = "high_long_term_precipitation_background"
            row_context_reasons.extend(
                [
                    "Ilgtermiņa nokrišņu fons paaugstināts",
                    "P730 izmantots tikai kā konteksta modifikators",
                ]
            )
        else:
            p730_context = "normal"

        if active_valid_count < 3:
            row_warnings.append("Nepilnīgs indikatoru komplekts")

        active_risks.append(active_risk)
        p730_contexts.append(p730_context)
        p730_modifiers.append(p730_modifier)
        final_levels.append(final_level)
        labels_lv.append(label)
        active_reasons.append(pipe_join(row_active_reasons))
        context_reasons.append(pipe_join(row_context_reasons))
        data_warnings.append(pipe_join(row_warnings))
        confidences.append(confidence)
        map_visible_values.append(map_visible)
        active_indicator_counts.append(active_valid_count)

    out["active_indicator_count"] = active_indicator_counts
    out["valid_variable_count"] = active_indicator_counts
    out["active_risk"] = pd.Series(active_risks, dtype="Int64")
    out["p730_context"] = p730_contexts
    out["p730_modifier"] = pd.Series(p730_modifiers, dtype="Int64")
    out["final_risk_level"] = pd.Series(final_levels, dtype="Int64")
    out["final_risk_label_lv"] = labels_lv
    out["active_reasons"] = active_reasons
    out["context_reasons"] = context_reasons
    out["data_warnings"] = data_warnings
    out["map_visible"] = map_visible_values
    out["hsaf_ssm"] = out["HSAF_SSM_pct"] if "HSAF_SSM_pct" in out.columns else np.nan
    out["swi"] = out["SWI010_pct"] if "SWI010_pct" in out.columns else np.nan
    out["kiri_risk_level"] = out["final_risk_level"]
    out["kiri_risk_label_lv"] = out["final_risk_label_lv"]
    out["main_reasons"] = out["active_reasons"]
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
    visible_mask = (
        df["map_visible"].astype(bool)
        if "map_visible" in df.columns
        else pd.Series(True, index=df.index)
    )
    valid = df[
        df["municipality_code"].notna()
        & df["kiri_risk_level"].notna()
        & visible_mask
    ].copy()
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
        dominant_reasons=("active_reasons", dominant_reasons),
        dominant_context_reasons=("context_reasons", dominant_reasons),
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
            "dominant_context_reasons",
            "confidence_summary",
        ]
    ]


def validation_summary(df: pd.DataFrame) -> dict[str, Any]:
    visible_mask = (
        df["map_visible"].astype(bool)
        if "map_visible" in df.columns
        else pd.Series(True, index=df.index)
    )
    visible = df[visible_mask].copy()
    hidden = df[~visible_mask].copy()

    def split_counts(series: pd.Series) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in series.dropna():
            for part in str(value).split("|"):
                part = part.strip()
                if part:
                    counts[part] = counts.get(part, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10])

    return {
        "total_visible_cells": int(len(visible)),
        "hidden_no_hsaf_cells": int(len(hidden)),
        "risk_distribution": {
            str(level): int((visible["final_risk_level"] == level).sum())
            for level in range(1, 6)
        },
        "confidence_distribution": {
            str(key): int(value)
            for key, value in visible["confidence"].value_counts(dropna=False).to_dict().items()
        },
        "top_active_reasons": split_counts(visible["active_reasons"]),
        "top_context_reasons": split_counts(visible["context_reasons"]),
    }


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
        "validation_summary": validation_summary(normalized),
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
