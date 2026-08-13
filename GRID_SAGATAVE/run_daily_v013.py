from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "DATA_LAST_60"
LOG_DIR = DATA_DIR / "logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the operational KIRI-LV v0.1.3 daily update and optionally commit/push the Pages payload."
    )
    parser.add_argument("--visible-days", type=int, default=60)
    parser.add_argument("--days", type=int, default=None, help="Backward-compatible alias for --visible-days.")
    parser.add_argument("--source-lookback-days", type=int, default=75)
    parser.add_argument("--retain-source-days", type=int, default=14)
    parser.add_argument("--rebuild-window", action="store_true", help="Rebuild the whole visible source/intermediate window.")
    parser.add_argument("--skip-source-update", action="store_true", help="Backward-compatible alias for --skip-source-download.")
    parser.add_argument("--skip-source-download", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument("--swi-raster-date-offset-days", type=int, default=None)
    parser.add_argument("--today", default=None, help="Override today's date as YYYY-MM-DD.")
    parser.add_argument("--commit-and-push", action="store_true")
    parser.add_argument("--push-branch", default="main")
    parser.add_argument("--keep-server-running", action="store_true")
    parser.add_argument("--serve-port", type=int, default=8000)
    parser.add_argument("--hsaf-project", default=None)
    parser.add_argument("--swi-project", default=None)
    parser.add_argument("--hsaf-root", default=None)
    parser.add_argument("--swi-daily-dir", default=None)
    return parser.parse_args()


def run_step(name: str, command: list[str], cwd: Path = BASE_DIR) -> None:
    print(f"\n== {name} ==")
    print(" ".join(shlex.quote(part) for part in command))
    subprocess.run(command, cwd=cwd, check=True)


def frontend_status() -> dict[str, object]:
    manifest_path = BASE_DIR / "frontend" / "data" / "calendar_manifest.json"
    archive_path = BASE_DIR / "frontend" / "data" / "archive_manifest.json"
    calendar = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = json.loads(archive_path.read_text(encoding="utf-8"))
    return {
        "default_date": calendar["default_date"],
        "date_count": calendar["date_count"],
        "window_start": calendar["dates"][0]["date"],
        "window_end": calendar["dates"][-1]["date"],
        "archive_dates": len(archive.get("dates", [])),
        "archive_start": archive.get("dates", [{}])[0].get("date"),
        "archive_end": archive.get("dates", [{}])[-1].get("date"),
    }


def git_commit_and_push(branch: str) -> None:
    run_step("Stage KIRI v0.1.3 operational update", ["git", "add", "-A"], PROJECT_DIR)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not status:
        print("\n== Commit KIRI v0.1.3 operational update ==")
        print("No git changes to commit.")
        return
    current = frontend_status()
    message = f"Update KIRI-LV v0.1.3 operational data to {current['default_date']}"
    run_step("Commit KIRI v0.1.3 operational update", ["git", "commit", "-m", message], PROJECT_DIR)
    run_step("Push KIRI v0.1.3 operational update", ["git", "push", "origin", f"HEAD:{branch}"], PROJECT_DIR)


def main() -> None:
    args = parse_args()
    visible_days = args.days if args.days is not None else args.visible_days
    started_at = datetime.now().isoformat(timespec="seconds")

    command = [
        sys.executable,
        "run_kiri_daily_clean.py",
        "--visible-days",
        str(visible_days),
        "--source-lookback-days",
        str(args.source_lookback_days),
        "--retain-source-days",
        str(args.retain_source_days),
    ]
    if args.rebuild_window:
        command.append("--rebuild-window")
    if args.skip_source_update or args.skip_source_download:
        command.append("--skip-source-download")
    if args.skip_cleanup:
        command.append("--skip-cleanup")
    if args.keep_server_running:
        command.append("--keep-server-running")
        command.extend(["--serve-port", str(args.serve_port)])
    if args.today:
        date.fromisoformat(args.today)
        command.extend(["--today", args.today])
    if args.swi_raster_date_offset_days is not None:
        command.extend(["--swi-raster-date-offset-days", str(args.swi_raster_date_offset_days)])
    for flag, value in [
        ("--hsaf-project", args.hsaf_project),
        ("--swi-project", args.swi_project),
        ("--hsaf-root", args.hsaf_root),
        ("--swi-daily-dir", args.swi_daily_dir),
    ]:
        if value:
            command.extend([flag, value])

    run_step("Run clean KIRI v0.1.3 daily refresh", command)
    if args.commit_and_push:
        git_commit_and_push(args.push_branch)

    status = {
        "version": "v0.1.3-operational",
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "commit_and_push": args.commit_and_push,
        "push_branch": args.push_branch,
        "frontend": frontend_status(),
    }
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = LOG_DIR / "daily_v013_last_run.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDONE v0.1.3 operational daily update")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
