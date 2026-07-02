from __future__ import annotations

import argparse
import calendar
import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


ELEMENT = os.getenv("CLIDATA_ELEMENT")
ORACLE_INSTANTCLIENT = os.getenv("CLIDATA_ORACLE_INSTANTCLIENT")
ORACLE_DSN = os.getenv("CLIDATA_ORACLE_DSN")

LV_STATIONS = [
    "RIAI99PA",
    "RIAL99MS",
    "RIBA99PA",
    "RIDM99MS",
    "RIDO99MS",
    "RIGASLU",
    "RIGU99MS",
    "RIJE99PA",
    "RIKO99PA",
    "RILP99PA",
    "RIME99MS",
    "RIPA99PA",
    "RIPR99PA",
    "RIREZEKN",
    "RIRU99PA",
    "RISA99PA",
    "RISE99MS",
    "RISI99PA",
    "RIST99PA",
    "RIVE99PA",
    "RIZI99PA",
    "RIZO99MS",
    "KALNCIEM",
    "KULDIGA",
    "LIELPECI",
    "LUBANA",
    "PIEDRUJA",
    "RUCAVA",
    "SALACGRI",
    "SIGULDA",
    "SILI",
    "VICAKI",
    "RIDAGDA",
    "RIMADONA",
]

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
HSAF_ROOT = PROJECT_DIR.parent / "FTP_TRYING" / "data" / "h28_latvia_nc"
OUT_ROOT = PROJECT_DIR / "DATA_LAST_60"
DATE_DIR_RE = re.compile(r"\\(20\d{2})\\([01]\d)\\([0-3]\d)\\")


@dataclass(frozen=True)
class Window:
    target_date: date
    period: str
    days: int

    @property
    def start(self) -> date:
        return self.target_date - timedelta(days=self.days - 1)

    @property
    def end(self) -> date:
        return self.target_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download CLIDATA precipitation and build P30/P90/P730 station sums for last H-SAF dates."
    )
    parser.add_argument("--hsaf-root", default=str(HSAF_ROOT))
    parser.add_argument("--out-root", default=str(OUT_ROOT))
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD end date; defaults to latest H-SAF date.")
    parser.add_argument("--use-existing-raw", action="store_true", help="Reuse raw CLIDATA CSV if present.")
    return parser.parse_args()


def open_oracle():
    import oracledb

    user = os.getenv("CLIDATA_ORACLE_USER")
    password = os.getenv("CLIDATA_ORACLE_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "Set CLIDATA_ORACLE_USER and CLIDATA_ORACLE_PASSWORD before downloading CLIDATA data."
        )

    if ORACLE_INSTANTCLIENT:
        try:
            oracledb.init_oracle_client(lib_dir=ORACLE_INSTANTCLIENT)
        except Exception:
            pass
    return oracledb.connect(user=user, password=password, dsn=ORACLE_DSN)


def hsafe_dates(root: Path) -> list[date]:
    dates: set[date] = set()
    for path in root.rglob("*.nc"):
        match = DATE_DIR_RE.search(str(path))
        if match:
            dates.add(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
    if not dates:
        raise FileNotFoundError(f"No H-SAF netCDF dates found under {root}")
    return sorted(dates)


def target_dates(root: Path, days: int, end_date_text: str | None) -> list[date]:
    available = hsafe_dates(root)
    end = date.fromisoformat(end_date_text) if end_date_text else available[-1]
    selected = [value for value in available if value <= end][-days:]
    if len(selected) < days:
        raise ValueError(f"Only {len(selected)} H-SAF dates available up to {end}; requested {days}.")
    return selected


def month_iter(start: date, end: date) -> list[tuple[int, int]]:
    out = []
    year = start.year
    month = start.month
    while (year, month) <= (end.year, end.month):
        out.append((year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return out


def download_rdata(start: date, end: date) -> pd.DataFrame:
    months = month_iter(start, end)
    years = sorted({year for year, _month in months})
    year_placeholders = ",".join(f":year{i}" for i, _year in enumerate(years))
    station_placeholders = ",".join(f":station{i}" for i, _station in enumerate(LV_STATIONS))

    params = {f"year{i}": year for i, year in enumerate(years)}
    params.update({f"station{i}": station for i, station in enumerate(LV_STATIONS)})
    params["element"] = ELEMENT

    sql = f"""
        SELECT *
        FROM CLIDATA.RDATA
        WHERE EG_EL_ABBREVIATION = :element
          AND YEAR IN ({year_placeholders})
          AND EG_GH_ID IN ({station_placeholders})
    """

    with open_oracle() as conn:
        df = pd.read_sql(sql, conn, params=params)

    df["EG_GH_ID"] = df["EG_GH_ID"].astype(str).str.strip()
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["MONTH"] = pd.to_numeric(df["MONTH"], errors="coerce").astype("Int64")
    valid_months = set(months)
    return df[
        df[["YEAR", "MONTH"]].apply(lambda row: (int(row["YEAR"]), int(row["MONTH"])) in valid_months, axis=1)
    ].copy()


def normalize_val_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    val_cols = [col for col in out.columns if str(col).upper().startswith("VAL")]
    for col in val_cols:
        series = (
            out[col]
            .astype(str)
            .str.strip()
            .replace({"": None, "NA": None, "NaN": None, "None": None})
            .str.replace(",", ".", regex=False)
        )
        out[col] = pd.to_numeric(series, errors="coerce")
    return out


def raw_to_daily(raw: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    raw = normalize_val_columns(raw)
    records = []
    for _, row in raw.iterrows():
        year = int(row["YEAR"])
        month = int(row["MONTH"])
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            current = date(year, month, day)
            if not (start <= current <= end):
                continue
            col = f"VAL{day:02d}"
            if col not in raw.columns:
                continue
            value = row[col]
            if pd.isna(value):
                continue
            records.append({"gh_id": row["EG_GH_ID"], "date": current, "value_mm": float(value)})
    return pd.DataFrame(records)


def sum_window(daily: pd.DataFrame, window: Window) -> pd.DataFrame:
    subset = daily[(daily["date"] >= window.start) & (daily["date"] <= window.end)]
    if subset.empty:
        return pd.DataFrame(columns=["gh_id", "value_mm", "period", "target_date", "window_start", "window_end", "n_days"])
    out = subset.groupby("gh_id", as_index=False).agg(value_mm=("value_mm", "sum"), n_days=("date", "nunique"))
    out["value_mm"] = out["value_mm"].round(3)
    out["period"] = window.period
    out["target_date"] = window.target_date.isoformat()
    out["window_start"] = window.start.isoformat()
    out["window_end"] = window.end.isoformat()
    return out[["gh_id", "value_mm", "period", "target_date", "window_start", "window_end", "n_days"]]


def main() -> None:
    args = parse_args()
    hsaf_root = Path(args.hsaf_root)
    out_root = Path(args.out_root)
    raw_dir = out_root / "precip_obs" / "raw"
    obs_dir = out_root / "precip_obs" / "daily_windows"
    metadata_dir = out_root / "metadata"
    raw_dir.mkdir(parents=True, exist_ok=True)
    obs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    dates = target_dates(hsaf_root, args.days, args.end_date)
    windows = [Window(target, period, days) for target in dates for period, days in [("P30", 30), ("P90", 90), ("P730", 730)]]
    min_start = min(window.start for window in windows)
    max_end = max(window.end for window in windows)
    raw_path = raw_dir / f"clidata_rdata_{min_start.isoformat()}_{max_end.isoformat()}_{ELEMENT}.csv"

    if args.use_existing_raw and raw_path.exists():
        raw = pd.read_csv(raw_path, low_memory=False)
    else:
        raw = download_rdata(min_start, max_end)
        raw.to_csv(raw_path, index=False, encoding="utf-8")

    daily = raw_to_daily(raw, min_start, max_end)
    all_sums = []
    manifest_rows = []
    for window in windows:
        obs = sum_window(daily, window)
        date_dir = obs_dir / window.target_date.isoformat()
        date_dir.mkdir(parents=True, exist_ok=True)
        obs_file = date_dir / f"obs_{window.period}_precip_{window.start.isoformat()}_{window.end.isoformat()}.csv"
        obs.to_csv(obs_file, index=False, encoding="utf-8")
        all_sums.append(obs)
        manifest_rows.append(
            {
                "target_date": window.target_date.isoformat(),
                "period": window.period,
                "window_start": window.start.isoformat(),
                "window_end": window.end.isoformat(),
                "obs_file": str(obs_file),
                "station_count": int(len(obs)),
            }
        )

    combined = pd.concat(all_sums, ignore_index=True)
    combined_path = out_root / "precip_obs" / "obs_precip_windows_long.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8")

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = out_root / "precip_obs" / "precip_windows_manifest.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8")

    metadata = {
        "purpose": "KIRI-LV v0.1 last-60-day CLIDATA station precipitation windows before interpolation.",
        "target_dates": [value.isoformat() for value in dates],
        "date_count": len(dates),
        "windows": ["P30", "P90", "P730"],
        "raw_clidata": str(raw_path),
        "combined_obs": str(combined_path),
        "manifest": str(manifest_path),
    }
    metadata_path = metadata_dir / "precip_obs_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dates: {dates[0]} .. {dates[-1]} ({len(dates)})")
    print(f"Raw rows: {len(raw)}")
    print(f"Daily obs rows: {len(daily)}")
    print(f"Window rows: {len(combined)}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
