from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
DEFAULT_VALUES_DIR = FRONTEND_DATA / "grid_values"
DEFAULT_HISTORY_DIR = FRONTEND_DATA / "indicator_history"
HISTORY_VERSION = 1

INDICATORS = {
    "hsaf": {"field": "HSAF_SSM_pct", "fallback": "hsaf_ssm", "unit": "%", "thresholds": [25, 40, 55, 70], "age_field": "hsaf_age_days"},
    "swi": {"field": "SWI010_pct", "fallback": "swi", "unit": "%", "thresholds": [30, 45, 60, 75]},
    "p30": {"field": "P30_mm", "unit": "mm", "thresholds": [20, 40, 70, 100]},
    "p90": {"field": "P90_mm", "unit": "mm", "thresholds": [80, 140, 220, 320]},
    "p730": {"field": "P730_mm", "unit": "mm", "thresholds": [900, 1100, 1300, 1500]},
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_bytes(data)
    temp_path.replace(path)


def available_dates(values_dir: Path) -> list[str]:
    return sorted(path.name for path in values_dir.iterdir() if path.is_dir())


def municipality_codes(values_dir: Path, dates: list[str]) -> list[str]:
    if not dates:
        return []
    for date_text in reversed(dates):
        codes = sorted(path.stem for path in (values_dir / date_text).glob("*.json"))
        if codes:
            return codes
    return []


def compact_age(value: object) -> int | None:
    if value is None:
        return None
    return int(float(value))


def load_existing_histories(
    history_dir: Path,
    municipality_code: str,
    dates: list[str],
    force_rebuild: bool,
) -> tuple[int, dict[str, dict]]:
    if force_rebuild:
        return 0, {key: {} for key in INDICATORS}

    payloads = {}
    prefixes = []
    for key in INDICATORS:
        path = history_dir / key / f"{municipality_code}.json"
        if not path.exists():
            return 0, {name: {} for name in INDICATORS}
        payload = read_json(path)
        existing_dates = payload.get("dates", [])
        if payload.get("version") != HISTORY_VERSION or existing_dates != dates[: len(existing_dates)]:
            return 0, {name: {} for name in INDICATORS}
        prefixes.append(len(existing_dates))
        payloads[key] = payload.get("series", {})

    if len(set(prefixes)) != 1:
        return 0, {key: {} for key in INDICATORS}
    return prefixes[0], payloads


def update_municipality_history(
    values_dir: Path,
    history_dir: Path,
    municipality_code: str,
    dates: list[str],
    force_rebuild: bool = False,
) -> tuple[int, int]:
    start_index, histories = load_existing_histories(history_dir, municipality_code, dates, force_rebuild)

    for date_index, date_text in enumerate(dates[start_index:], start=start_index):
        for series_by_cell in histories.values():
            for cell_series in series_by_cell.values():
                cell_series["v"].append(None)
                if "a" in cell_series:
                    cell_series["a"].append(None)

        values_path = values_dir / date_text / f"{municipality_code}.json"
        if not values_path.exists():
            continue

        payload = read_json(values_path)
        field_index = {field: index for index, field in enumerate(payload["fields"])}
        grid_index = field_index["grid_id"]

        for row in payload["rows"]:
            grid_id = str(row[grid_index])
            for key, config in INDICATORS.items():
                series_by_cell = histories[key]
                if grid_id not in series_by_cell:
                    cell_series = {"v": [None] * (date_index + 1)}
                    if config.get("age_field"):
                        cell_series["a"] = [None] * (date_index + 1)
                    series_by_cell[grid_id] = cell_series
                cell_series = series_by_cell[grid_id]
                value_index = field_index.get(config["field"], field_index.get(config.get("fallback", "")))
                cell_series["v"][date_index] = row[value_index] if value_index is not None else None
                age_field = config.get("age_field")
                if age_field:
                    age_index = field_index.get(age_field)
                    cell_series["a"][date_index] = compact_age(row[age_index]) if age_index is not None else None

    for key, config in INDICATORS.items():
        output = {
            "version": HISTORY_VERSION,
            "indicator": key,
            "municipality_code": municipality_code,
            "dates": dates,
            "unit": config["unit"],
            "thresholds": config["thresholds"],
            "series": histories[key],
        }
        write_json(history_dir / key / f"{municipality_code}.json", output)

    cell_count = max((len(series) for series in histories.values()), default=0)
    return cell_count, len(dates) - start_index


def build_indicator_histories(
    values_dir: Path = DEFAULT_VALUES_DIR,
    history_dir: Path = DEFAULT_HISTORY_DIR,
    force_rebuild: bool = False,
) -> dict[str, int]:
    dates = available_dates(values_dir)
    codes = municipality_codes(values_dir, dates)
    history_dir.mkdir(parents=True, exist_ok=True)

    cell_count = 0
    updated_date_count = 0
    for position, code in enumerate(codes, start=1):
        cells, updated_dates = update_municipality_history(
            values_dir,
            history_dir,
            code,
            dates,
            force_rebuild=force_rebuild,
        )
        cell_count += cells
        updated_date_count += updated_dates
        print(f"Indicator history {position}/{len(codes)}: {code} ({cells} cells, {updated_dates} new dates)", flush=True)

    expected_files = {f"{code}.json" for code in codes}
    for key in INDICATORS:
        metric_dir = history_dir / key
        for path in metric_dir.glob("*.json"):
            if path.name not in expected_files:
                path.unlink()

    stats = {
        "indicator_count": len(INDICATORS),
        "municipality_count": len(codes),
        "date_count": len(dates),
        "date_start": dates[0] if dates else None,
        "date_end": dates[-1] if dates else None,
        "cell_count": cell_count,
        "updated_date_count": updated_date_count,
    }
    write_json(
        history_dir / "index.json",
        {
            "version": HISTORY_VERSION,
            **stats,
            "indicators": {
                key: {
                    "unit": config["unit"],
                    "thresholds": config["thresholds"],
                    "file_count": len(codes),
                    "path": f"{key}/<municipality_code>.json",
                }
                for key, config in INDICATORS.items()
            },
        },
    )
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact chart histories for KIRI-LV indicators.")
    parser.add_argument("--rebuild", action="store_true", help="Ignore existing histories and rebuild all dates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_indicator_histories(force_rebuild=args.rebuild)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
