from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import date
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


@dataclass(frozen=True)
class Window:
    name: str
    start: date
    end: date


WINDOWS = [
    Window("P30", date(2026, 5, 17), date(2026, 6, 15)),
    Window("P90", date(2026, 3, 18), date(2026, 6, 15)),
    Window("P730", date(2024, 6, 16), date(2026, 6, 15)),
]

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "precip_outputs"
RAW_DIR = OUT_DIR / "raw"
OBS_DIR = OUT_DIR / "obs"


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
    df = df[df[["YEAR", "MONTH"]].apply(lambda row: (int(row["YEAR"]), int(row["MONTH"])) in valid_months, axis=1)]
    return df


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


def sum_window(df: pd.DataFrame, window: Window) -> pd.DataFrame:
    df = normalize_val_columns(df)
    records = []
    for _, row in df.iterrows():
        year = int(row["YEAR"])
        month = int(row["MONTH"])
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            if not (window.start <= current_date <= window.end):
                continue
            col = f"VAL{day:02d}"
            if col not in df.columns:
                continue
            value = row[col]
            if pd.isna(value):
                continue
            records.append(
                {
                    "gh_id": row["EG_GH_ID"],
                    "date": current_date.isoformat(),
                    "value_mm": float(value),
                }
            )

    daily = pd.DataFrame(records)
    if daily.empty:
        return pd.DataFrame(columns=["gh_id", "value_mm", "period", "window_start", "window_end", "n_days"])

    station_sum = daily.groupby("gh_id", as_index=False).agg(value_mm=("value_mm", "sum"), n_days=("date", "nunique"))
    station_sum["value_mm"] = station_sum["value_mm"].round(3)
    station_sum["period"] = window.name
    station_sum["window_start"] = window.start.isoformat()
    station_sum["window_end"] = window.end.isoformat()
    return station_sum[["gh_id", "value_mm", "period", "window_start", "window_end", "n_days"]]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OBS_DIR.mkdir(parents=True, exist_ok=True)

    min_start = min(window.start for window in WINDOWS)
    max_end = max(window.end for window in WINDOWS)
    raw = download_rdata(min_start, max_end)
    raw_path = RAW_DIR / f"clidata_rdata_{min_start.isoformat()}_{max_end.isoformat()}_{ELEMENT}.csv"
    raw.to_csv(raw_path, index=False, encoding="utf-8")

    all_sums = []
    for window in WINDOWS:
        obs = sum_window(raw, window)
        out_path = OBS_DIR / f"obs_{window.name}_precip_{window.start.isoformat()}_{window.end.isoformat()}.csv"
        obs.to_csv(out_path, index=False, encoding="utf-8")
        all_sums.append(obs)
        print(f"{window.name}: {len(obs)} stations -> {out_path}")

    combined = pd.concat(all_sums, ignore_index=True)
    combined_path = OBS_DIR / "obs_precip_windows_long.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8")

    wide = combined.pivot(index="gh_id", columns="period", values="value_mm").reset_index()
    wide_path = OBS_DIR / "obs_precip_windows_wide.csv"
    wide.to_csv(wide_path, index=False, encoding="utf-8")

    print("Raw CLIDATA rows:", len(raw))
    print("Raw saved:", raw_path)
    print("Combined saved:", combined_path)
    print("Wide saved:", wide_path)


if __name__ == "__main__":
    main()
