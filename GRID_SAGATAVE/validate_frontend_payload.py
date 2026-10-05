from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


REQUIRED_INDICATORS = {"hsaf", "swi", "p30", "p90", "p730"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def validate(root: Path) -> dict[str, object]:
    calendar = read_json(root / "calendar_manifest.json")
    assert calendar["date_count"] == len(calendar["dates"]) == 60
    calendar_dates = [item["date"] for item in calendar["dates"]]
    assert calendar_dates == sorted(calendar_dates)
    assert calendar["default_date"] == calendar_dates[-1]
    assert len(list((root / "grid_static").glob("*.geojson"))) == 43

    archive = read_json(root / "archive_manifest.json")
    archive_dates = [item["date"] for item in archive["dates"]]
    assert archive["visible_date_count"] == 60
    assert archive_dates == sorted(archive_dates)
    assert archive_dates[-1] == calendar["default_date"]
    assert calendar_dates == archive_dates[-60:]

    for item in calendar["dates"]:
        manifest = read_json(root / item["manifest_file"])
        assert len(manifest) == item["municipality_count"] == 43, item["date"]
        for code, row in manifest.items():
            assert row["static_grid_file"] == f"grid_static/{code}.geojson"
            assert row["grid_values_file"] == f"grid_values/{item['date']}/{code}.json"
            assert (root / row["static_grid_file"]).exists()
            assert (root / row["grid_values_file"]).exists()

    history_root = root / "indicator_history"
    history_index = read_json(history_root / "index.json")
    assert set(history_index["indicators"]) == REQUIRED_INDICATORS
    assert history_index["municipality_count"] == 43
    assert history_index["date_end"] == calendar["default_date"]
    assert history_index["date_count"] == len(archive_dates)

    latest_manifest = read_json(root / calendar["dates"][-1]["manifest_file"])
    series_count = 0
    for indicator in sorted(REQUIRED_INDICATORS):
        files = list((history_root / indicator).glob("*.json.gz"))
        assert len(files) == 43, indicator
        for code in latest_manifest:
            payload = read_gzip_json(history_root / indicator / f"{code}.json.gz")
            assert payload["dates"] == archive_dates, (indicator, code)
            assert payload["series"], (indicator, code)
            for row in payload["series"].values():
                assert len(row["v"]) == len(archive_dates), (indicator, code)
                if indicator == "hsaf":
                    assert len(row["a"]) == len(archive_dates), code
            series_count += len(payload["series"])

    return {
        "calendar_start": calendar_dates[0],
        "calendar_end": calendar["default_date"],
        "calendar_days": len(calendar_dates),
        "archive_start": archive_dates[0],
        "archive_end": archive_dates[-1],
        "archive_days": len(archive_dates),
        "indicator_history_files": len(REQUIRED_INDICATORS) * 43,
        "indicator_series": series_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate KIRI-LV map and indicator chart payloads.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent / "frontend" / "data",
    )
    return parser.parse_args()


def main() -> None:
    result = validate(parse_args().root)
    print("KIRI-LV frontend validation passed")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
