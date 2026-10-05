from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
STATIC_DIR = FRONTEND_DATA / "grid_static"
VALUES_DIR = FRONTEND_DATA / "grid_values"
HISTORY_DIR = FRONTEND_DATA / "indicator_history"


def main() -> None:
    static_count = len(list(STATIC_DIR.glob("*.geojson"))) if STATIC_DIR.exists() else 0
    date_count = len([path for path in VALUES_DIR.iterdir() if path.is_dir()]) if VALUES_DIR.exists() else 0
    history_index = HISTORY_DIR / "index.json"
    history = json.loads(history_index.read_text(encoding="utf-8")) if history_index.exists() else {}
    payload = {
        "status": "no-op",
        "message": (
            "Compact frontend data is now written directly by "
            "prepare_frontend_last_60_kiri_data.py. Static grid geometry is stored once, "
            "and daily grid values are stored separately."
        ),
        "static_grid_files": static_count,
        "daily_value_dates": date_count,
        "indicator_history_files": len(list(HISTORY_DIR.glob("*/*.json.gz"))) if HISTORY_DIR.exists() else 0,
        "indicator_history_date_count": history.get("date_count", 0),
        "indicator_history_date_end": history.get("date_end"),
        "static_dir": str(STATIC_DIR),
        "values_dir": str(VALUES_DIR),
        "history_dir": str(HISTORY_DIR),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
