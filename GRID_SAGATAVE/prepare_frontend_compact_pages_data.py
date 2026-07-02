from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
STATIC_DIR = FRONTEND_DATA / "grid_static"
VALUES_DIR = FRONTEND_DATA / "grid_values"


def main() -> None:
    static_count = len(list(STATIC_DIR.glob("*.geojson"))) if STATIC_DIR.exists() else 0
    date_count = len([path for path in VALUES_DIR.iterdir() if path.is_dir()]) if VALUES_DIR.exists() else 0
    payload = {
        "status": "no-op",
        "message": (
            "Compact frontend data is now written directly by "
            "prepare_frontend_last_60_kiri_data.py. Static grid geometry is stored once, "
            "and daily grid values are stored separately."
        ),
        "static_grid_files": static_count,
        "daily_value_dates": date_count,
        "static_dir": str(STATIC_DIR),
        "values_dir": str(VALUES_DIR),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
