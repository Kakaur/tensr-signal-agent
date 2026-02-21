"""
server.py — FastAPI backend for Tensr Signal Agent dashboard.

Run with:
    ./venv/bin/python -m uvicorn signal_pipeline_backend.server:app --reload --port 8000
"""

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from signal_pipeline_backend import briefing_agent, database
from signal_pipeline_backend.pipeline_profile import (
    PROFILES_DIR,
    default_profile,
    save_profile,
    validate_profile_dict,
    validate_profile_text,
)

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
_briefing_sessions: dict[str, list[dict[str, str]]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d.pop("outreach_angle", None)
    if d.get("total_score") is None:
        d["total_score"] = 0
    if d.get("priority_tier") is None:
        d["priority_tier"] = "HOLD"
    return d


def _get_all_signals_from_db() -> list[dict]:
    """Return signals from the most recent run only."""
    database.init_db()
    conn = database._connect()
    try:
        latest_run = conn.execute(
            "SELECT id FROM scout_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not latest_run:
            return []

        rows = conn.execute(
            """
            SELECT s.*, sr.timestamp as run_timestamp
            FROM signals s
            JOIN scout_runs sr ON s.run_id = sr.id
            WHERE s.run_id = ?
            ORDER BY s.total_score DESC, s.signal_date DESC
            """
            ,
            (latest_run["id"],)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


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

        result.append({
            "id": None,
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
        })
    return sorted(result, key=lambda x: (x.get("signal_date") or ""), reverse=True)


def _candidate_profile_paths(profile_path: str) -> list[str]:
    candidates = {profile_path, str(Path(profile_path))}
    try:
        candidates.add(str(Path(profile_path).resolve()))
    except OSError:
        pass
    return [path for path in candidates if path]


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

class RunPipelineRequest(BaseModel):
    profile_path: str | None = None
    profile_paths: list[str] = Field(default_factory=list)
    run_all_profiles: bool = False


class DeletePipelineRequest(BaseModel):
    profile_path: str


class BriefingStartRequest(BaseModel):
    initial_message: str | None = None


class BriefingMessageRequest(BaseModel):
    session_id: str
    message: str


class BriefingFinalizeRequest(BaseModel):
    session_id: str


class DeleteBatchRequest(BaseModel):
    run_id: int


class AdjustSettingsRequest(BaseModel):
    adjustment_text: str
    base_profile: dict | None = None


class SaveSettingsRequest(BaseModel):
    profile: dict


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


@app.get("/api/briefing/default-profile")
def get_default_profile():
    return default_profile().model_dump()


@app.get("/api/pipeline/current-settings")
def get_current_pipeline_settings():
    latest = database.get_latest_run_profile()
    profile_json = latest.get("profile_json")
    if profile_json:
        try:
            parsed = json.loads(profile_json)
            return {
                "source": "latest_run_profile",
                "profile": parsed,
                "profile_file": latest.get("profile_file"),
                "run_id": latest.get("run_id"),
                "timestamp": latest.get("timestamp"),
            }
        except json.JSONDecodeError:
            pass

    return {
        "source": "default_profile",
        "profile": default_profile().model_dump(),
        "profile_file": None,
        "run_id": latest.get("run_id"),
        "timestamp": latest.get("timestamp"),
    }


@app.get("/api/pipeline/profiles")
def list_pipeline_profiles():
    """List saved pipeline profiles from the central profiles directory."""
    if not PROFILES_DIR.exists():
        return {"profiles": []}

    files = sorted(
        PROFILES_DIR.glob("pipeline_profile_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    profiles = []
    for path in files:
        try:
            with open(path) as f:
                profile = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        objective = " ".join((profile.get("objective") or "").split())
        short_description = " ".join(objective.split()[:10]) if objective else ""
        created_at = profile.get("created_at")
        if not created_at:
            created_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

        created_day = created_at.split("T")[0] if "T" in created_at else created_at
        target = profile.get("target_output", {})
        profiles.append(
            {
                "profile_path": str(path),
                "file_name": path.name,
                "profile_id": profile.get("profile_id"),
                "created_at": created_at,
                "created_day": created_day,
                "objective": objective,
                "short_description": short_description,
                "regions": profile.get("regions", []),
                "domains": profile.get("domains", []),
                "min_signals": target.get("min_signals", 20),
                "max_signals": target.get("max_signals", 25),
                "profile": profile,
            }
        )

    return {"profiles": profiles}


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


@app.post("/api/pipeline/adjust-settings")
def adjust_pipeline_settings(req: AdjustSettingsRequest):
    base_profile = req.base_profile
    if not base_profile:
        current = get_current_pipeline_settings()
        base_profile = current.get("profile") or default_profile().model_dump()

    if not req.adjustment_text.strip():
        return {"error": "adjustment_text is required"}

    adjusted_text = briefing_agent.adjust_profile_json(base_profile, req.adjustment_text)
    try:
        adjusted_profile = validate_profile_text(adjusted_text)
    except Exception as exc:
        return {"error": f"Adjusted profile validation failed: {exc}", "raw": adjusted_text}

    path = save_profile(adjusted_profile)
    return {
        "profile_path": str(path),
        "profile": adjusted_profile.model_dump(),
    }


@app.post("/api/pipeline/save-settings")
def save_pipeline_settings(req: SaveSettingsRequest):
    try:
        validated = validate_profile_dict(req.profile)
    except Exception as exc:
        return {"error": f"Profile schema validation failed: {exc}"}

    path = save_profile(validated)
    return {
        "profile_path": str(path),
        "profile": validated.model_dump(),
    }


@app.post("/api/pipeline/delete")
def delete_pipeline(req: DeletePipelineRequest):
    if _pipeline_state["running"]:
        return {"error": "Cannot delete while pipeline is running"}

    profile_path = (req.profile_path or "").strip()
    if not profile_path:
        return {"error": "profile_path is required"}

    candidates = _candidate_profile_paths(profile_path)
    runs = database.get_runs_by_profile_files(candidates)
    run_ids = [run["id"] for run in runs]

    db_deleted = database.delete_runs_by_ids(run_ids)
    batch_deleted = _delete_batches_for_runs(runs)

    profile_deleted = False
    deleted_profile_path = None
    for candidate in candidates:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            candidate_path.unlink()
            profile_deleted = True
            deleted_profile_path = str(candidate_path)
            break

    return {
        "deleted_profile_path": deleted_profile_path,
        "profile_deleted": profile_deleted,
        "runs_deleted": db_deleted["runs_deleted"],
        "signals_deleted": db_deleted["signals_deleted"],
        **batch_deleted,
    }


@app.post("/api/pipeline/delete-all")
def delete_all_pipelines():
    if _pipeline_state["running"]:
        return {"error": "Cannot delete while pipeline is running"}

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

    profiles_deleted = 0
    if PROFILES_DIR.exists():
        for profile_path in PROFILES_DIR.glob("pipeline_profile_*.json"):
            if profile_path.exists():
                profile_path.unlink()
                profiles_deleted += 1

    return {
        "profiles_deleted": profiles_deleted,
        "runs_deleted": db_deleted["runs_deleted"],
        "signals_deleted": db_deleted["signals_deleted"],
        "orphan_scout_reports_deleted": orphan_scout_deleted,
        "orphan_scored_reports_deleted": orphan_scored_deleted,
        **batch_deleted,
    }


@app.post("/api/briefing/start")
def briefing_start(req: BriefingStartRequest):
    session_id = f"brief_{uuid4().hex[:12]}"
    messages: list[dict[str, str]] = [briefing_agent.default_assistant_message()]

    if req.initial_message:
        messages.append({"role": "user", "content": req.initial_message})
        assistant_text = briefing_agent.generate_reply(messages)
        messages.append({"role": "assistant", "content": assistant_text})

    _briefing_sessions[session_id] = messages
    return {"session_id": session_id, "messages": messages}


@app.post("/api/briefing/message")
def briefing_message(req: BriefingMessageRequest):
    if req.session_id not in _briefing_sessions:
        return {"error": "Invalid briefing session"}

    messages = _briefing_sessions[req.session_id]
    messages.append({"role": "user", "content": req.message})
    assistant_text = briefing_agent.generate_reply(messages)
    messages.append({"role": "assistant", "content": assistant_text})
    _briefing_sessions[req.session_id] = messages
    return {"session_id": req.session_id, "messages": messages}


@app.post("/api/briefing/finalize")
def briefing_finalize(req: BriefingFinalizeRequest):
    if req.session_id not in _briefing_sessions:
        return {"error": "Invalid briefing session"}

    messages = _briefing_sessions[req.session_id]
    finalized_text = briefing_agent.finalize_profile_json(messages)
    try:
        profile = validate_profile_text(finalized_text)
    except Exception as exc:
        return {"error": f"Profile validation failed: {exc}", "raw": finalized_text}

    path = save_profile(profile)
    messages.append(
        {
            "role": "assistant",
            "content": (
                f"Briefing finalized. Profile saved to {path} and ready for pipeline run."
            ),
        }
    )
    _briefing_sessions[req.session_id] = messages
    return {
        "session_id": req.session_id,
        "profile_path": str(path),
        "profile": profile.model_dump(),
    }


@app.post("/api/run-pipeline")
async def run_pipeline(req: RunPipelineRequest | None = None):
    if _pipeline_state["running"]:
        return {"error": "Pipeline already running"}

    requested_paths: list[str] = []
    if req:
        if req.run_all_profiles:
            requested_paths = [
                str(path)
                for path in sorted(
                    PROFILES_DIR.glob("pipeline_profile_*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            ]
            if not requested_paths:
                return {"error": "No saved pipelines found for All pipelines run."}
        elif req.profile_paths:
            requested_paths = req.profile_paths
        elif req.profile_path:
            requested_paths = [req.profile_path]

    deduped_paths: list[str] = []
    seen = set()
    for raw_path in requested_paths:
        normalized = str(Path(raw_path))
        if normalized in seen:
            continue
        if not Path(normalized).exists():
            return {"error": f"Pipeline profile not found: {normalized}"}
        seen.add(normalized)
        deduped_paths.append(normalized)

    async def event_stream():
        _pipeline_state["running"] = True
        _pipeline_state["last_status"] = "running"
        run_targets = deduped_paths if deduped_paths else [None]
        total_runs = len(run_targets)
        failed_runs = 0

        try:
            if deduped_paths:
                yield f"data: {json.dumps({'log': f'Starting {total_runs} pipeline run(s).'})}\n\n"

            for idx, profile_path in enumerate(run_targets, start=1):
                cmd = [PYTHON, "-m", "signal_pipeline_backend.orchestrator"]
                if profile_path:
                    cmd.extend(["--profile", profile_path])
                    profile_name = Path(profile_path).name
                    yield (
                        f"data: {json.dumps({'log': f'[{idx}/{total_runs}] Running {profile_name}'})}\n\n"
                    )

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
                if proc.returncode != 0:
                    failed_runs += 1
                    if total_runs > 1:
                        label = Path(profile_path).name if profile_path else "default pipeline"
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "log": (
                                        f"[{idx}/{total_runs}] {label} failed "
                                        f"(exit code {proc.returncode})"
                                    )
                                }
                            )
                            + "\n\n"
                        )

            if failed_runs == 0:
                _pipeline_state["last_status"] = "done"
                success_msg = (
                    f"All {total_runs} pipeline runs completed successfully."
                    if total_runs > 1
                    else "Pipeline completed successfully."
                )
                yield f"data: {json.dumps({'status': 'done', 'log': success_msg})}\n\n"
            else:
                _pipeline_state["last_status"] = "error"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "status": "error",
                            "log": (
                                f"{failed_runs}/{total_runs} pipeline run(s) failed."
                                if total_runs > 1
                                else "Pipeline failed."
                            ),
                        }
                    )
                    + "\n\n"
                )
        finally:
            _pipeline_state["running"] = False
            _pipeline_state["last_run_at"] = datetime.now().isoformat()
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
