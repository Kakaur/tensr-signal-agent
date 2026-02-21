"""
orchestrator.py — Single entrypoint for the signal scout → scorer pipeline.

Usage:
    python -m signal_pipeline_backend.orchestrator
    python -m signal_pipeline_backend.orchestrator --scout-only
    python -m signal_pipeline_backend.orchestrator --score-only outputs/signal_report_20250220_143000.json
"""

import argparse
import json
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

from signal_pipeline_backend import database

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
PYTHON_CANDIDATE = PROJECT_DIR / "venv" / "bin" / "python"
PYTHON = str(PYTHON_CANDIDATE if PYTHON_CANDIDATE.exists() else Path(sys.executable))
SCOUT_MODULE = "signal_pipeline_backend.signal_scout"
SCORER_MODULE = "signal_pipeline_backend.signal_scorer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def find_latest_file(pattern: str) -> Path | None:
    """Return the most recently modified file matching the glob pattern."""
    files = sorted(OUTPUTS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def run_subprocess(label: str, cmd: list[str]) -> bool:
    """Run a subprocess, stream output live, and return True on success."""
    print(f"\n{'=' * 60}")
    print(f"RUNNING: {label}")
    print(f"CMD: {' '.join(cmd)}")
    print("=" * 60)

    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )  # nosec B603

    # Print captured output
    if proc.stdout:
        print(proc.stdout)

    if proc.returncode != 0:
        print(f"\nERROR: {label} failed with exit code {proc.returncode}")
        return False

    print(f"\n{label} completed successfully.")
    return True


def print_scored_summary(scored_path: Path) -> None:
    """Parse scored report JSON and print tier counts."""
    try:
        with open(scored_path) as f:
            data = json.load(f)
        print(f"  HOT:     {data.get('hot_count', 0)}")
        print(f"  WARM:    {data.get('warm_count', 0)}")
        print(f"  NURTURE: {data.get('nurture_count', 0)}")
        print(f"  HOLD:    {data.get('hold_count', 0)}")
        print(f"  TOTAL:   {data.get('total_signals', 0)}")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  WARNING: Could not parse scored report: {e}")


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
def run_scout(profile_path: Path | None = None) -> Path | None:
    """Run scout module and return the output file path, or None on failure."""
    # Snapshot existing files before scout runs
    existing = set(OUTPUTS_DIR.glob("signal_report_*.json")) if OUTPUTS_DIR.exists() else set()

    cmd = [PYTHON, "-m", SCOUT_MODULE]
    if profile_path:
        cmd.extend(["--profile", str(profile_path)])

    ok = run_subprocess("Signal Scout", cmd)
    if not ok:
        return None

    # Find the new file created by the scout
    current = set(OUTPUTS_DIR.glob("signal_report_*.json"))
    new_files = current - existing

    if new_files:
        # Pick the most recently modified among new files
        return max(new_files, key=lambda p: p.stat().st_mtime)

    # Fallback: most recent file overall
    return find_latest_file("signal_report_*.json")


def run_scorer(scout_output: Path, profile_path: Path | None = None) -> Path | None:
    """Run scorer module on the given scout output, return scored file path."""
    existing = set(OUTPUTS_DIR.glob("scored_report_*.json")) if OUTPUTS_DIR.exists() else set()

    cmd = [PYTHON, "-m", SCORER_MODULE, str(scout_output)]
    if profile_path:
        cmd.extend(["--profile", str(profile_path)])
    ok = run_subprocess("Signal Scorer", cmd)
    if not ok:
        return None

    current = set(OUTPUTS_DIR.glob("scored_report_*.json"))
    new_files = current - existing

    if new_files:
        return max(new_files, key=lambda p: p.stat().st_mtime)

    return find_latest_file("scored_report_*.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orchestrate the signal scout → scorer pipeline.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--scout-only",
        action="store_true",
        help="Run scout only; skip scoring.",
    )
    group.add_argument(
        "--score-only",
        type=str,
        metavar="FILEPATH",
        help="Skip scouting; run scorer on the provided scout output file.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Optional pipeline profile JSON file to guide scout/scorer.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    start_time = time.time()

    scout_output: Path | None = None
    scored_output: Path | None = None
    profile_path: Path | None = Path(args.profile) if args.profile else None
    profile_json: str | None = None

    if profile_path:
        if not profile_path.exists():
            print(f"ERROR: Profile file not found: {profile_path}")
            sys.exit(1)
        with open(profile_path) as f:
            profile_json = f.read()

    # ---- Score-only mode ----
    if args.score_only:
        scout_output = Path(args.score_only)
        if not scout_output.exists():
            print(f"ERROR: File not found: {scout_output}")
            sys.exit(1)
        print(f"Score-only mode — using: {scout_output}")
        scored_output = run_scorer(scout_output, profile_path=profile_path)
        if scored_output is None:
            sys.exit(1)
        print(f"\nDB: writing scored run → {scored_output.name}")
        database.write_scored_run(scored_output)

    # ---- Scout-only mode ----
    elif args.scout_only:
        scout_output = run_scout(profile_path=profile_path)
        if scout_output is None:
            sys.exit(1)
        print(f"\nDB: writing scout run → {scout_output.name}")
        database.write_scout_run(
            scout_output,
            profile_file=str(profile_path) if profile_path else None,
            profile_json=profile_json,
        )

    # ---- Full pipeline ----
    else:
        scout_output = run_scout(profile_path=profile_path)
        if scout_output is None:
            print("\nAborting — scout failed, skipping scorer.")
            sys.exit(1)
        print(f"\nDB: writing scout run → {scout_output.name}")
        database.write_scout_run(
            scout_output,
            profile_file=str(profile_path) if profile_path else None,
            profile_json=profile_json,
        )

        scored_output = run_scorer(scout_output, profile_path=profile_path)
        if scored_output is None:
            sys.exit(1)
        print(f"\nDB: writing scored run → {scored_output.name}")
        database.write_scored_run(scored_output)

    # ---- Summary ----
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Scout output:  {scout_output}")

    if scored_output:
        print(f"  Scored output: {scored_output}")
        print("-" * 60)
        print_scored_summary(scored_output)
    elif args.scout_only:
        print("  Scorer:        skipped (--scout-only)")

    print("-" * 60)
    print(f"  Total runtime: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
