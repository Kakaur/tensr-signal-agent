"""
server.py — FastAPI backend for Tensr Signal Agent dashboard.

Run with:
    ./venv/bin/python -m uvicorn signal_pipeline_backend.server:app --reload --port 8000
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from signal_pipeline_backend import database

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON_CANDIDATE = PROJECT_DIR / "venv" / "bin" / "python"
PYTHON = str(PYTHON_CANDIDATE if PYTHON_CANDIDATE.exists() else Path(sys.executable))
OUTPUTS_DIR = PROJECT_DIR / "outputs"

app = FastAPI(title="Tensr Signal Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory pipeline state
# ---------------------------------------------------------------------------
_pipeline_state = {
    "running": False,
    "last_status": "idle",
    "last_run_at": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row | dict) -> dict:
    d = dict(row)
    d.pop("outreach_angle", None)
    if d.get("total_score") is None:
        d["total_score"] = 0
    if d.get("priority_tier") is None:
        d["priority_tier"] = "HOLD"
    return d


def _get_all_signals_from_db() -> list[dict]:
    """Return signals across all runs, newest first."""
    return [_row_to_dict(r) for r in database.get_all_signals()]


def _get_signals_from_latest_json() -> list[dict]:
    """Fallback: parse the most recently modified scored_report_*.json."""
    files = sorted(
        OUTPUTS_DIR.glob("scored_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return []

    with open(files[0]) as f:
        data = json.load(f)

    signals = data.get("signals", [])
    result = []
    for sig in signals:
        bd = sig.get("score_breakdown", {})

        def pts(key):
            block = bd.get(key)
            return block.get("points") if isinstance(block, dict) else None

        result.append(
            {
                "id": None,
                "run_id": None,
                "institution": sig.get("institution"),
                "country": sig.get("country"),
                "region": sig.get("region"),
                "signal_type": sig.get("signal_type"),
                "signal_date": sig.get("signal_date"),
                "domain": sig.get("domain"),
                "institution_tier": sig.get("institution_type", sig.get("institution_tier")),
                "seniority": sig.get("seniority"),
                "source_url": sig.get("source_url"),
                "summary": sig.get("summary"),
                "total_score": sig.get("total_score", 0),
                "priority_tier": sig.get("priority_tier", "HOLD"),
                "action_pts": pts("action_type"),
                "seniority_pts": pts("seniority"),
                "domain_pts": pts("domain_fit"),
                "accessibility_pts": pts("institution_accessibility"),
                "recency_pts": pts("recency"),
                "seniority_inferred": 0,
                "scored_at": data.get("timestamp"),
                "run_timestamp": data.get("timestamp"),
            }
        )

    return sorted(result, key=lambda x: (x.get("signal_date") or ""), reverse=True)


def _delete_batches_for_runs(runs: list[dict]) -> dict:
    scored_by_source: dict[str, list[Path]] = {}
    for scored_path in OUTPUTS_DIR.glob("scored_report_*.json"):
        try:
            with open(scored_path) as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        source = payload.get("source_report")
        if not source:
            continue
        scored_by_source.setdefault(source, []).append(scored_path)

    scout_deleted = 0
    scout_missing = 0
    scored_deleted = 0
    for run in runs:
        output_file = run.get("output_file")
        if not output_file:
            continue

        scout_path = OUTPUTS_DIR / output_file
        if scout_path.exists():
            scout_path.unlink()
            scout_deleted += 1
        else:
            scout_missing += 1

        for scored_path in scored_by_source.get(output_file, []):
            if scored_path.exists():
                scored_path.unlink()
                scored_deleted += 1

    return {
        "scout_reports_deleted": scout_deleted,
        "scout_reports_missing": scout_missing,
        "scored_reports_deleted": scored_deleted,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class DeleteBatchRequest(BaseModel):
    run_id: int


class RunPipelineRequest(BaseModel):
    pass


@app.get("/api/signals")
def get_signals():
    signals = _get_all_signals_from_db()
    if not signals:
        signals = _get_signals_from_latest_json()
    return {"signals": signals, "total": len(signals)}


@app.get("/api/summary")
def get_summary():
    return database.get_summary()


@app.get("/api/status")
def get_status():
    return _pipeline_state


@app.get("/api/batches")
def list_batches():
    return {"batches": database.get_batches()}


@app.post("/api/batches/delete")
def delete_batch(req: DeleteBatchRequest):
    if _pipeline_state["running"]:
        return {"error": "Cannot delete batches while pipeline is running"}

    batch = database.delete_batch(req.run_id)
    if not batch:
        return {"error": f"Batch {req.run_id} not found"}

    batch_deleted = _delete_batches_for_runs([batch])
    return {
        "run_id": req.run_id,
        **batch_deleted,
    }


@app.post("/api/batches/delete-all")
def delete_all_batches():
    if _pipeline_state["running"]:
        return {"error": "Cannot delete batches while pipeline is running"}

    runs = database.get_all_runs()
    run_ids = [run["id"] for run in runs]
    db_deleted = database.delete_runs_by_ids(run_ids)
    batch_deleted = _delete_batches_for_runs(runs)

    orphan_scout_deleted = 0
    for scout_path in OUTPUTS_DIR.glob("signal_report_*.json"):
        if scout_path.exists():
            scout_path.unlink()
            orphan_scout_deleted += 1

    orphan_scored_deleted = 0
    for scored_path in OUTPUTS_DIR.glob("scored_report_*.json"):
        if scored_path.exists():
            scored_path.unlink()
            orphan_scored_deleted += 1

    return {
        "runs_deleted": db_deleted["runs_deleted"],
        "signals_deleted": db_deleted["signals_deleted"],
        "orphan_scout_reports_deleted": orphan_scout_deleted,
        "orphan_scored_reports_deleted": orphan_scored_deleted,
        **batch_deleted,
    }


@app.post("/api/run-pipeline")
async def run_pipeline(_req: RunPipelineRequest | None = None):
    if _pipeline_state["running"]:
        return {"error": "Pipeline already running"}

    async def event_stream():
        _pipeline_state["running"] = True
        _pipeline_state["last_status"] = "running"

        try:
            cmd = [PYTHON, "-m", "signal_pipeline_backend.orchestrator"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(PROJECT_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async for line in proc.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                yield f"data: {json.dumps({'log': text})}\n\n"

            await proc.wait()
            if proc.returncode == 0:
                _pipeline_state["last_status"] = "done"
                yield (
                    "data: "
                    + json.dumps({"status": "done", "log": "Pipeline completed successfully."})
                    + "\n\n"
                )
            else:
                _pipeline_state["last_status"] = "error"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "status": "error",
                            "log": f"Pipeline failed (exit code {proc.returncode}).",
                        }
                    )
                    + "\n\n"
                )
        finally:
            _pipeline_state["running"] = False
            _pipeline_state["last_run_at"] = datetime.now().isoformat()
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
