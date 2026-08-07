from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
MESLI_DIR = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "DATA_LAST_60"
FRONTEND_DATA = BASE_DIR / "frontend" / "data"
CALENDAR_MANIFEST = FRONTEND_DATA / "calendar_manifest.json"
DATE_DATA_DIR = FRONTEND_DATA / "dates"
VALUES_DIR = FRONTEND_DATA / "grid_values"
INDICATOR_DIR = DATA_DIR / "indicator_grids"
LOG_DIR = DATA_DIR / "logs"

DEFAULT_HSAF_PROJECT = MESLI_DIR / "FTP_TRYING"
DEFAULT_SWI_PROJECT = MESLI_DIR / "COPERNICUS_SWI"
DEFAULT_HSAF_ROOT = DEFAULT_HSAF_PROJECT / "data" / "h28_latvia_nc"
DEFAULT_SWI_DAILY_DIR = DEFAULT_SWI_PROJECT / "data" / "grid_tiffs" / "daily_swi"

HSAF_DATE_RE = re.compile(r"_(20\d{6})\d{4,6}_")
INDICATOR_RE = re.compile(r"grid_indicators_P30_P90_P730_HSAF_SWI_(20\d{2}-\d{2}-\d{2})\.csv$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-command KIRI-LV clean daily refresh: sources, indicators, frontend JSON, and raw cleanup."
    )
    parser.add_argument("--visible-days", type=int, default=60)
    parser.add_argument("--source-lookback-days", type=int, default=75)
    parser.add_argument("--skip-source-download", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument("--rebuild-window", action="store_true", help="Rebuild the whole visible window from sources.")
    parser.add_argument("--retain-source-days", type=int, default=14)
    parser.add_argument("--swi-raster-date-offset-days", type=int, default=None)
    parser.add_argument("--keep-server-running", action="store_true")
    parser.add_argument("--serve-port", type=int, default=8000)
    parser.add_argument("--hsaf-project", default=str(DEFAULT_HSAF_PROJECT))
    parser.add_argument("--swi-project", default=str(DEFAULT_SWI_PROJECT))
    parser.add_argument("--hsaf-root", default=str(DEFAULT_HSAF_ROOT))
    parser.add_argument("--swi-daily-dir", default=str(DEFAULT_SWI_DAILY_DIR))
    parser.add_argument("--today", default=None, help="Override today's date as YYYY-MM-DD for repeatable local runs.")
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def run_step(name: str, command: list[str], cwd: Path, log_lines: list[str]) -> None:
    rendered = " ".join(shlex.quote(part) for part in command)
    print(f"\n== {name} ==")
    print(rendered)
    log_lines.append(f"\n== {name} ==\n{rendered}\n")
    started = time.time()
    subprocess.run(command, cwd=cwd, check=True)
    log_lines.append(f"OK {name} in {time.time() - started:.1f}s\n")


def csv_has_rows(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _line in handle) > 1


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def indicator_dates() -> set[str]:
    out: set[str] = set()
    if not INDICATOR_DIR.exists():
        return out
    for path in INDICATOR_DIR.glob("grid_indicators_P30_P90_P730_HSAF_SWI_*.csv"):
        match = INDICATOR_RE.match(path.name)
        if match:
            out.add(match.group(1))
    return out


def frontend_payload_complete(date_text: str) -> bool:
    if not (DATE_DATA_DIR / date_text / "overview.geojson").exists():
        return False
    if not (DATE_DATA_DIR / date_text / "manifest.json").exists():
        return False
    values_dir = VALUES_DIR / date_text
    return values_dir.exists() and len(list(values_dir.glob("*.json"))) >= 40


def calendar_default_date() -> date | None:
    if not CALENDAR_MANIFEST.exists():
        return None
    try:
        manifest = read_json(CALENDAR_MANIFEST)
        return date.fromisoformat(manifest["default_date"])
    except Exception:
        return None


def hsaf_dates(root: Path) -> set[str]:
    out: set[str] = set()
    if not root.exists():
        return out
    for path in root.rglob("*.nc"):
        match = HSAF_DATE_RE.search(path.name)
        if match:
            raw = match.group(1)
            out.add(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
            continue
        parts = path.parts
        for index in range(len(parts) - 2):
            y, m, d = parts[index : index + 3]
            if re.fullmatch(r"20\d{2}", y) and re.fullmatch(r"[01]\d", m) and re.fullmatch(r"[0-3]\d", d):
                out.add(f"{y}-{m}-{d}")
                break
    return out


def swi_dates(root: Path) -> set[str]:
    out: set[str] = set()
    if not root.exists():
        return out
    for path in root.glob("*.tif"):
        match = re.search(r"_(20\d{6})\.tif$", path.name)
        if match:
            raw = match.group(1)
            out.add(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
    return out


def latest_window(dates: set[str], visible_days: int) -> list[str]:
    ordered = sorted(dates)
    return ordered[-visible_days:]


def is_suffix(subset: list[str], ordered: list[str]) -> bool:
    if not subset:
        return True
    return ordered[-len(subset) :] == subset


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def clear_generated_swi_daily(swi_daily_dir: Path) -> int:
    if not swi_daily_dir.exists():
        return 0
    removed = 0
    for path in swi_daily_dir.glob("lv_1x1_swi*.tif"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def cleanup_source_raw(
    hsaf_root: Path,
    swi_project: Path,
    processed_dates: set[str],
    retain_after: date,
) -> dict[str, int]:
    removed = {"hsaf_nc": 0, "hsaf_png": 0, "swi_raw": 0, "swi_extracted": 0}
    removable_dates = {
        value
        for value in processed_dates
        if date.fromisoformat(value) < retain_after
    }
    if hsaf_root.exists():
        date_tokens = {value.replace("-", "") for value in removable_dates}
        for suffix, key in [("*.nc", "hsaf_nc"), ("*.png", "hsaf_png")]:
            for path in hsaf_root.rglob(suffix):
                if any(token in path.name for token in date_tokens):
                    path.unlink(missing_ok=True)
                    removed[key] += 1

    raw_dir = swi_project / "data" / "raw"
    if raw_dir.exists():
        for path in raw_dir.glob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed["swi_raw"] += 1

    extracted_dir = swi_project / "data" / "extracted"
    if extracted_dir.exists():
        for path in extracted_dir.iterdir():
            remove_tree(path) if path.is_dir() else path.unlink(missing_ok=True)
            removed["swi_extracted"] += 1

    return removed


def start_local_server(port: int) -> dict[str, object]:
    current_port = port
    while True:
        probe = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -LocalPort {current_port} -ErrorAction SilentlyContinue"],
            capture_output=True,
            text=True,
        )
        if not probe.stdout.strip():
            break
        current_port += 1

    log_path = Path(os.getenv("TEMP", str(DATA_DIR))) / f"kiri-local-{current_port}.log"
    process = subprocess.Popen(
        ["python", "-m", "http.server", str(current_port)],
        cwd=BASE_DIR / "frontend",
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    time.sleep(2)
    return {"url": f"http://localhost:{current_port}", "pid": process.pid, "log": str(log_path)}


def main() -> None:
    args = parse_args()
    run_date = date.fromisoformat(args.today) if args.today else date.today()
    hsaf_project = Path(args.hsaf_project)
    swi_project = Path(args.swi_project)
    hsaf_root = Path(args.hsaf_root)
    swi_daily_dir = Path(args.swi_daily_dir)

    load_env_file(BASE_DIR / ".env")
    load_env_file(hsaf_project / ".env")
    load_env_file(swi_project / ".env")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    source_start = run_date - timedelta(days=args.source_lookback_days - 1)
    if not args.skip_source_download:
        local_hsaf_dates = sorted(hsaf_dates(hsaf_root))
        hsaf_start = source_start if args.rebuild_window else (
            date.fromisoformat(local_hsaf_dates[-1]) + timedelta(days=1) if local_hsaf_dates else source_start
        )
        if hsaf_start <= run_date:
            run_step(
                "Download latest H-SAF Latvia tiles",
                [
                    "python",
                    "h28_downloader.py",
                    "--start",
                    hsaf_start.isoformat(),
                    "--end",
                    run_date.isoformat(),
                    "--download",
                ],
                hsaf_project,
                log_lines,
            )
        else:
            print("\n== Download latest H-SAF Latvia tiles ==")
            print("Local H-SAF source is already current for this run date.")

        local_swi_dates = sorted(swi_dates(swi_daily_dir))
        swi_start = source_start if args.rebuild_window else (
            date.fromisoformat(local_swi_dates[-1]) + timedelta(days=1) if local_swi_dates else source_start
        )
        if swi_start <= run_date:
            run_step(
                "Download latest Copernicus SWI",
                [
                    "python",
                    "copernicus_swi_flow.py",
                    "--start-date",
                    swi_start.isoformat(),
                    "--end-date",
                    run_date.isoformat(),
                    "--limit",
                    str(args.source_lookback_days),
                    "--download-count",
                    str(args.source_lookback_days),
                ],
                swi_project,
                log_lines,
            )
        else:
            print("\n== Download latest Copernicus SWI ==")
            print("Local SWI daily grids are already current for this run date.")
        if csv_has_rows(swi_project / "data" / "catalog" / "products.csv"):
            if args.rebuild_window:
                removed_swi_daily = clear_generated_swi_daily(swi_daily_dir)
                print(f"Cleared generated SWI daily grids before rebuild: {removed_swi_daily}")
            swi_grid_command = ["python", "make_lv_grid_swi_tiffs.py"]
            if args.swi_raster_date_offset_days is not None:
                swi_grid_command.extend(["--raster-date-offset-days", str(args.swi_raster_date_offset_days)])
            run_step(
                "Build Latvia SWI daily grid TIFFs",
                swi_grid_command,
                swi_project,
                log_lines,
            )
        else:
            print("\n== Build Latvia SWI daily grid TIFFs ==")
            print("No new SWI products found; keeping existing daily SWI grid TIFFs.")

    available_hsaf_dates = hsaf_dates(hsaf_root)
    target_window = latest_window(available_hsaf_dates | indicator_dates(), args.visible_days)
    if not target_window:
        raise RuntimeError(f"No source or indicator dates found. Checked H-SAF root: {hsaf_root}")

    missing_indicator_dates = [value for value in target_window if value not in indicator_dates()]
    missing_frontend_dates = [value for value in target_window if not frontend_payload_complete(value)]
    rebuild_source_dates = target_window if args.rebuild_window else missing_indicator_dates
    if rebuild_source_dates and not is_suffix(rebuild_source_dates, target_window):
        rebuild_source_count = args.visible_days
    else:
        rebuild_source_count = max(1, len(rebuild_source_dates))

    print("\n== Refresh plan ==")
    print(f"Target window: {target_window[0]} .. {target_window[-1]} ({len(target_window)})")
    print(f"Missing indicator dates: {len(missing_indicator_dates)}")
    print(f"Missing frontend JSON dates: {len(missing_frontend_dates)}")
    print(f"Source rebuild count: {rebuild_source_count}")

    if missing_indicator_dates:
        run_step(
            "CLIDATA precipitation windows",
            ["python", "prepare_last_60_precip_obs.py", "--days", str(rebuild_source_count)],
            BASE_DIR,
            log_lines,
        )
        run_step(
            "P30/P90/P730 interpolation",
            ["Rscript", "run_last_60_precip_interpolation.R", str(rebuild_source_count)],
            BASE_DIR,
            log_lines,
        )
        run_step(
            "H-SAF/SWI grid sampling",
            [
                "python",
                "build_last_60_indicator_grids.py",
                "--days",
                str(rebuild_source_count),
                "--hsaf-root",
                str(hsaf_root),
                "--swi-dir",
                str(swi_daily_dir),
            ],
            BASE_DIR,
            log_lines,
        )

    run_step(
        "Frontend JSON window and archive",
        ["python", "prepare_frontend_last_60_kiri_data.py", "--visible-days", str(args.visible_days), "--materialize-archive-payloads"],
        BASE_DIR,
        log_lines,
    )
    run_step("Frontend compact check", ["python", "prepare_frontend_compact_pages_data.py"], BASE_DIR, log_lines)

    cleanup_report = {}
    if not args.skip_cleanup:
        retain_after = date.fromisoformat(target_window[-1]) - timedelta(days=args.retain_source_days - 1)
        cleanup_report = cleanup_source_raw(hsaf_root, swi_project, set(target_window), retain_after)
        print("\n== Source raw cleanup ==")
        print(json.dumps(cleanup_report, ensure_ascii=False, indent=2))

    server = start_local_server(args.serve_port) if args.keep_server_running else None
    latest_calendar = read_json(CALENDAR_MANIFEST)
    status = {
        "version": "v0.1.3-clean",
        "started_for_date": run_date.isoformat(),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "target_window_start": latest_calendar["dates"][0]["date"],
        "target_window_end": latest_calendar["dates"][-1]["date"],
        "default_date": latest_calendar["default_date"],
        "date_count": latest_calendar["date_count"],
        "missing_indicator_dates_before_run": missing_indicator_dates,
        "missing_frontend_dates_before_run": missing_frontend_dates,
        "cleanup": cleanup_report,
        "server": server,
    }
    status_path = LOG_DIR / "daily_clean_last_run.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / f"daily_clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log").write_text(
        "\n".join(log_lines), encoding="utf-8"
    )
    print("\nDONE clean daily refresh")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
