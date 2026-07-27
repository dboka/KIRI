from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "DATA_LAST_60"
LOG_DIR = DATA_DIR / "logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the clean KIRI-LV v0.1.3 daily update.")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--skip-source-update", action="store_true")
    parser.add_argument("--use-existing-clidata-raw", action="store_true")
    parser.add_argument("--commit-and-push", action="store_true")
    parser.add_argument("--push-branch", default="main")
    return parser.parse_args()


def run_step(name: str, command: list[str], cwd: Path = BASE_DIR) -> None:
    print(f"\n== {name} ==")
    print(" ".join(shlex.quote(part) for part in command))
    subprocess.run(command, cwd=cwd, check=True)


def run_optional_env_command(name: str, env_name: str) -> None:
    command = os.getenv(env_name)
    if not command:
        print(f"\n== {name} ==")
        print(f"{env_name} is not set; using existing local source archive.")
        return
    if os.name == "nt":
        run_step(name, ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], PROJECT_DIR)
    else:
        run_step(name, ["bash", "-lc", command], PROJECT_DIR)


def git_commit_and_push(branch: str) -> None:
    run_step("Stage frontend update", ["git", "add", "-A"])
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not status:
        print("\n== Commit frontend update ==")
        print("No git changes to commit.")
        return
    run_step("Commit frontend update", ["git", "commit", "-m", "Update KIRI-LV v0.1.3 daily data"], PROJECT_DIR)
    run_step("Push frontend update", ["git", "push", "origin", f"HEAD:{branch}"], PROJECT_DIR)


def main() -> None:
    args = parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")

    if not args.skip_source_update:
        run_optional_env_command("Update H-SAF source", "KIRI_HSAF_UPDATE_COMMAND")
        run_optional_env_command("Update SWI source", "KIRI_SWI_UPDATE_COMMAND")

    clidata_command = [
        "python",
        "prepare_last_60_precip_obs.py",
        "--days",
        str(args.days),
    ]
    if args.use_existing_clidata_raw:
        clidata_command.append("--use-existing-raw")
    run_step("CLIDATA precipitation windows", clidata_command)
    run_step("P30/P90/P730 interpolation", ["Rscript", "run_last_60_precip_interpolation.R", str(args.days)])
    run_step("H-SAF/SWI grid sampling", ["python", "build_last_60_indicator_grids.py", "--days", str(args.days)])
    run_step("Frontend latest window and archive", ["python", "prepare_frontend_last_60_kiri_data.py", "--visible-days", str(args.days)])
    run_step("Frontend compact check", ["python", "prepare_frontend_compact_pages_data.py"])
    if args.commit_and_push:
        git_commit_and_push(args.push_branch)

    status = {
        "version": "v0.1.3",
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "days": args.days,
        "commit_and_push": args.commit_and_push,
        "push_branch": args.push_branch,
        "frontend": str(BASE_DIR / "frontend"),
    }
    out = LOG_DIR / "daily_v013_last_run.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE v0.1.3 daily update: {out}")


if __name__ == "__main__":
    main()
