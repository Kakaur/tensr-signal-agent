"""
database.py — SQLite persistence layer for tensr-signal-agent.

DB location: <project_root>/data/<DB_NAME>
DB_NAME is read from the .env file (default: tensr.db).

Tables:
  scout_runs  — one row per pipeline run
  signals     — one row per signal, FK to scout_runs
"""

import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Path resolution — always relative to project root, machine-independent
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
DB_NAME      = os.getenv("DB_NAME", "tensr.db")
DB_PATH      = DATA_DIR / DB_NAME


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL_SCOUT_RUNS = """
CREATE TABLE IF NOT EXISTS scout_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    queries_used  INTEGER NOT NULL DEFAULT 0,
    results_found INTEGER NOT NULL DEFAULT 0,
    output_file   TEXT NOT NULL,
    profile_file  TEXT,
    profile_json  TEXT
);
"""

DDL_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES scout_runs(id),

    -- Scout fields (populated by write_scout_run)
    institution         TEXT,
    country             TEXT,
    region              TEXT,
    signal_type         TEXT,
    signal_date         TEXT,
    domain              TEXT,
    institution_tier    TEXT,
    seniority           TEXT,
    source_url          TEXT,
    summary             TEXT,

    -- Score fields (populated by write_scored_run)
    total_score         REAL,
    priority_tier       TEXT,
    action_pts          INTEGER,
    seniority_pts       INTEGER,
    domain_pts          INTEGER,
    accessibility_pts   INTEGER,
    recency_pts         INTEGER,
    seniority_inferred  INTEGER DEFAULT 0,  -- boolean: 1=true, 0=false
    outreach_angle      TEXT,
    scored_at           TEXT
);
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they do not already exist."""
    with _connect() as conn:
        conn.execute(DDL_SCOUT_RUNS)
        conn.execute(DDL_SIGNALS)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(scout_runs)").fetchall()
        }
        if "profile_file" not in columns:
            conn.execute("ALTER TABLE scout_runs ADD COLUMN profile_file TEXT")
        if "profile_json" not in columns:
            conn.execute("ALTER TABLE scout_runs ADD COLUMN profile_json TEXT")
        signal_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(signals)").fetchall()
        }
        if "country" not in signal_columns:
            conn.execute("ALTER TABLE signals ADD COLUMN country TEXT")
        conn.execute(
            "UPDATE signals SET country = 'Unspecified' WHERE country IS NULL OR TRIM(country) = ''"
        )
        conn.execute(
            "UPDATE signals SET region = 'Unspecified' WHERE region IS NULL OR TRIM(region) = ''"
        )
        conn.commit()


# ---------------------------------------------------------------------------
# De-duplication helpers
# ---------------------------------------------------------------------------

def signal_fingerprint(sig: dict) -> str:
    """Stable key for de-duplicating signals across runs."""
    institution = (sig.get("institution") or "").strip().lower()
    signal_type = (sig.get("signal_type") or "").strip().lower()
    signal_date = (sig.get("signal_date") or "").strip().lower()
    source_url = (sig.get("source_url") or "").strip().lower()

    if source_url:
        return f"url::{source_url}"
    return f"triple::{institution}|{signal_type}|{signal_date}"


def get_existing_fingerprints() -> set[str]:
    """Return de-duplication keys for all signals already in DB."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT institution, signal_type, signal_date, source_url
            FROM signals
            """
        ).fetchall()
    return {signal_fingerprint(dict(r)) for r in rows}


# ---------------------------------------------------------------------------
# Write scout run (unscored)
# ---------------------------------------------------------------------------

def write_scout_run(
    scout_json_path: str | Path,
    profile_file: str | None = None,
    profile_json: str | None = None,
) -> int:
    """
    Parse a signal_report_*.json file and insert:
      - One row into scout_runs
      - One row per signal into signals (score fields left NULL)

    Returns the new scout_runs.id.
    """
    path = Path(scout_json_path)
    with open(path) as f:
        data = json.load(f)

    timestamp     = data.get("timestamp", "")
    queries_used  = len(data.get("search_queries_used", []))
    results_found = data.get("validated_signals_count", len(data.get("signals", [])))
    signals       = data.get("signals", [])

    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scout_runs (
                timestamp, queries_used, results_found, output_file, profile_file, profile_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (timestamp, queries_used, results_found, path.name, profile_file, profile_json),
        )
        run_id = cur.lastrowid

        for sig in signals:
            conn.execute(
                """
                INSERT INTO signals (
                    run_id, institution, country, region, signal_type, signal_date,
                    domain, institution_tier, seniority, source_url, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sig.get("institution"),
                    sig.get("country") or "Unspecified",
                    sig.get("region") or "Unspecified",
                    sig.get("signal_type"),
                    sig.get("signal_date"),
                    sig.get("domain"),
                    sig.get("institution_tier"),
                    sig.get("seniority"),
                    sig.get("source_url"),
                    sig.get("summary"),
                ),
            )

        conn.commit()

    return run_id


# ---------------------------------------------------------------------------
# Write scored run (update score fields on existing rows, or insert if missing)
# ---------------------------------------------------------------------------

def _extract_score_fields(sig: dict) -> dict:
    """Pull score breakdown fields from a scored signal dict."""
    breakdown = sig.get("score_breakdown", {})

    def pts(key: str) -> int | None:
        block = breakdown.get(key)
        if isinstance(block, dict):
            return block.get("points")
        return None

    seniority_block = breakdown.get("seniority", {})
    seniority_inferred = int(
        bool(seniority_block.get("seniority_inferred", False))
        if isinstance(seniority_block, dict) else False
    )

    return {
        "total_score":      sig.get("total_score"),
        "priority_tier":    sig.get("priority_tier"),
        "action_pts":       pts("action_type"),
        "seniority_pts":    pts("seniority"),
        "domain_pts":       pts("domain_fit"),
        "accessibility_pts": pts("institution_accessibility"),
        "recency_pts":      pts("recency"),
        "seniority_inferred": seniority_inferred,
    }


def write_scored_run(scored_json_path: str | Path) -> None:
    """
    Parse a scored_report_*.json and update signal rows with score fields.

    Matching strategy: join on run_id (via source_report filename) +
    institution + signal_type. If no matching row exists, insert a new one.
    """
    path = Path(scored_json_path)
    with open(path) as f:
        data = json.load(f)

    signals       = data.get("signals", [])
    source_report = data.get("source_report", "")
    scored_at     = data.get("timestamp", "")

    init_db()
    with _connect() as conn:
        # Find the run_id that corresponds to the source scout report
        row = conn.execute(
            "SELECT id FROM scout_runs WHERE output_file = ?",
            (source_report,),
        ).fetchone()

        if row:
            run_id = row["id"]
        else:
            # No matching scout run — create a placeholder entry
            cur = conn.execute(
                """
                INSERT INTO scout_runs (timestamp, queries_used, results_found, output_file)
                VALUES (?, 0, ?, ?)
                """,
                (scored_at, len(signals), source_report),
            )
            run_id = cur.lastrowid

        for sig in signals:
            institution  = sig.get("institution")
            signal_type  = sig.get("signal_type")
            score_fields = _extract_score_fields(sig)

            existing = conn.execute(
                """
                SELECT id FROM signals
                WHERE run_id = ? AND institution = ? AND signal_type = ?
                  AND COALESCE(signal_date, '') = COALESCE(?, '')
                  AND COALESCE(source_url, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (run_id, institution, signal_type, sig.get("signal_date"), sig.get("source_url")),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE signals SET
                        total_score        = ?,
                        priority_tier      = ?,
                        action_pts         = ?,
                        seniority_pts      = ?,
                        domain_pts         = ?,
                        accessibility_pts  = ?,
                        recency_pts        = ?,
                        seniority_inferred = ?,
                        scored_at          = ?
                    WHERE id = ?
                    """,
                    (
                        score_fields["total_score"],
                        score_fields["priority_tier"],
                        score_fields["action_pts"],
                        score_fields["seniority_pts"],
                        score_fields["domain_pts"],
                        score_fields["accessibility_pts"],
                        score_fields["recency_pts"],
                        score_fields["seniority_inferred"],
                        scored_at,
                        existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO signals (
                        run_id, institution, country, region, signal_type, signal_date,
                        domain, institution_tier, seniority, source_url, summary,
                        total_score, priority_tier, action_pts, seniority_pts,
                        domain_pts, accessibility_pts, recency_pts,
                        seniority_inferred, scored_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        institution,
                        sig.get("country") or "Unspecified",
                        sig.get("region") or "Unspecified",
                        signal_type,
                        sig.get("signal_date"),
                        sig.get("domain"),
                        sig.get("institution_tier") or sig.get("institution_type"),
                        sig.get("seniority"),
                        sig.get("source_url"),
                        sig.get("summary"),
                        score_fields["total_score"],
                        score_fields["priority_tier"],
                        score_fields["action_pts"],
                        score_fields["seniority_pts"],
                        score_fields["domain_pts"],
                        score_fields["accessibility_pts"],
                        score_fields["recency_pts"],
                        score_fields["seniority_inferred"],
                        scored_at,
                    ),
                )

        conn.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_runs_by_profile_files(profile_files: list[str]) -> list[dict]:
    """Return scout runs linked to any of the provided profile paths."""
    init_db()
    unique_files = [p for p in dict.fromkeys(profile_files) if p]
    if not unique_files:
        return []

    with _connect() as conn:
        conn.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS tmp_profile_files (
                profile_file TEXT PRIMARY KEY
            )
            """
        )
        conn.execute("DELETE FROM tmp_profile_files")
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_profile_files (profile_file) VALUES (?)",
            [(path,) for path in unique_files],
        )
        rows = conn.execute(
            """
            SELECT sr.id, sr.output_file, sr.profile_file
            FROM scout_runs sr
            JOIN tmp_profile_files tpf ON tpf.profile_file = sr.profile_file
            ORDER BY id DESC
            """,
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_runs() -> list[dict]:
    """Return all scout run ids/output files."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, output_file, profile_file
            FROM scout_runs
            ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def delete_runs_by_ids(run_ids: list[int]) -> dict:
    """Delete runs and their signals for the provided run ids."""
    init_db()
    unique_ids = [rid for rid in dict.fromkeys(run_ids) if rid is not None]
    if not unique_ids:
        return {"signals_deleted": 0, "runs_deleted": 0}

    with _connect() as conn:
        conn.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS tmp_run_ids (
                id INTEGER PRIMARY KEY
            )
            """
        )
        conn.execute("DELETE FROM tmp_run_ids")
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_run_ids (id) VALUES (?)",
            [(rid,) for rid in unique_ids],
        )
        signals_deleted = conn.execute(
            "DELETE FROM signals WHERE run_id IN (SELECT id FROM tmp_run_ids)",
        ).rowcount
        runs_deleted = conn.execute(
            "DELETE FROM scout_runs WHERE id IN (SELECT id FROM tmp_run_ids)",
        ).rowcount
        conn.commit()

    return {
        "signals_deleted": signals_deleted if signals_deleted > 0 else 0,
        "runs_deleted": runs_deleted if runs_deleted > 0 else 0,
    }


def get_batches() -> list[dict]:
    """Return scout run batches with signal counts."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                sr.id,
                sr.timestamp,
                sr.output_file,
                sr.profile_file,
                COUNT(s.id) AS signal_count,
                COALESCE(MAX(NULLIF(s.institution, '')), '') AS company_name
            FROM scout_runs sr
            LEFT JOIN signals s ON s.run_id = sr.id
            GROUP BY sr.id, sr.timestamp, sr.output_file, sr.profile_file
            ORDER BY sr.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def delete_batch(run_id: int) -> dict | None:
    """Delete one scout run batch and linked signals."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, output_file, profile_file, timestamp FROM scout_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None

        conn.execute("DELETE FROM signals WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM scout_runs WHERE id = ?", (run_id,))
        conn.commit()
    return dict(row)


def get_latest_run() -> list[sqlite3.Row]:
    """Return all signals from the most recent scout_runs entry."""
    init_db()
    with _connect() as conn:
        run = conn.execute(
            "SELECT id FROM scout_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not run:
            return []
        return conn.execute(
            "SELECT * FROM signals WHERE run_id = ? ORDER BY total_score DESC NULLS LAST",
            (run["id"],),
        ).fetchall()


def get_summary() -> dict:
    """
    Return HOT/WARM/NURTURE/HOLD counts for the most recent scored run,
    plus total signal count and the run timestamp.
    """
    init_db()
    with _connect() as conn:
        run = conn.execute(
            "SELECT id, timestamp FROM scout_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not run:
            return {
                "run_id": None, "timestamp": None,
                "HOT": 0, "WARM": 0, "NURTURE": 0, "HOLD": 0, "total": 0,
            }

        rows = conn.execute(
            "SELECT priority_tier FROM signals WHERE run_id = ?",
            (run["id"],),
        ).fetchall()

        counts = {"HOT": 0, "WARM": 0, "NURTURE": 0, "HOLD": 0}
        for row in rows:
            tier = (row["priority_tier"] or "HOLD").upper()
            if tier in counts:
                counts[tier] += 1
            else:
                counts["HOLD"] += 1

        return {
            "run_id":    run["id"],
            "timestamp": run["timestamp"],
            **counts,
            "total": len(rows),
        }


def update_run_profile(run_id: int, profile_file: str | None, profile_json: str | None) -> None:
    """Attach briefing profile metadata to an existing scout run."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE scout_runs
            SET profile_file = ?, profile_json = ?
            WHERE id = ?
            """,
            (profile_file, profile_json, run_id),
        )
        conn.commit()


def get_latest_run_profile() -> dict:
    """Return profile metadata from the most recent scout run."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, timestamp, profile_file, profile_json
            FROM scout_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return {
                "run_id": None,
                "timestamp": None,
                "profile_file": None,
                "profile_json": None,
            }

        return {
            "run_id": row["id"],
            "timestamp": row["timestamp"],
            "profile_file": row["profile_file"],
            "profile_json": row["profile_json"],
        }
