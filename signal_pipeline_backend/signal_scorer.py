import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from crewai import LLM, Agent, Crew, Task
from dotenv import load_dotenv

from signal_pipeline_backend.pipeline_profile import load_profile, validate_profile_dict

load_dotenv()

# ---------------------------------------------------------------------------
# Paths — all relative to project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR   = PROJECT_ROOT / "config"
OUTPUTS_DIR  = PROJECT_ROOT / "outputs"

# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------
llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=os.environ["GEMINI_API_KEY"],
    max_tokens=8192,  # explicit ceiling — prevents silent truncation
)

# ---------------------------------------------------------------------------
# Locate the most recent signal report
# ---------------------------------------------------------------------------

def find_latest_report() -> Path:
    """Return the most recent signal_report_*.json file."""
    reports = sorted(OUTPUTS_DIR.glob("signal_report_*.json"))
    if not reports:
        raise FileNotFoundError(
            f"No signal_report_*.json files found in {OUTPUTS_DIR}"
        )
    return reports[-1]


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Programmatic scoring maps & functions (applied as post-processing overrides)
# ---------------------------------------------------------------------------
ACTION_TYPE_SCORES = {
    "launch": 30,
    "filing": 25,
    "pilot": 22,
    "hire": 20,
    "partnership": 15,
    "investment": 10,
    "conference": 10,
    "other": 5,
}

SENIORITY_SCORES = {
    "c-suite": 20,
    "md": 20,
    "c-suite / md": 20,
    "c-suite/md": 20,
    "vp": 15,
    "director": 15,
    "vp/director": 15,
    "vp / director": 15,
    "senior": 10,
    "manager": 10,
    "senior/manager": 10,
    "senior / manager": 10,
    "unknown": 5,
}

DOMAIN_FIT_SCORES = {
    "stablecoin": 25,
    "digital_assets": 22,
    "agentic_automation": 20,
    "ai_implementation": 16,
    "ai_compliance_risk": 18,
    "ai_transformation": 14,
    "other": 5,
}

INSTITUTION_SCORES = {
    "series a+ fintech": 15,
    "regional/community bank": 12,
    "regional / community bank": 12,
    "mid-tier bank": 8,
    "unknown": 5,
}

COMPONENT_MAX = {
    "action_type": 30,
    "seniority": 20,
    "domain_fit": 25,
    "institution_accessibility": 15,
    "recency": 10,
}

CATEGORY_COMPONENT_ALIASES = {
    "action_strength": "action_type",
    "action_type": "action_type",
    "buyer_fit": "institution_accessibility",
    "institution_accessibility": "institution_accessibility",
    "institution_fit": "institution_accessibility",
    "domain_fit": "domain_fit",
    "seniority": "seniority",
    "recency": "recency",
}


def parse_signal_date(date_str: str) -> datetime | None:
    """Parse signal_date in YYYY-MM-DD or YYYY-MM format."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def score_recency(signal_date_str: str, institution: str) -> dict:
    """Score recency and log debug info. Returns {"category", "points"}."""
    parsed = parse_signal_date(signal_date_str)
    today = datetime.now()

    if parsed is None:
        print(
            f"  RECENCY DEBUG: {institution} | date='{signal_date_str}' | "
            f"PARSE FAILED | points=0"
        )
        return {"category": "unknown", "points": 0}

    days_old = (today - parsed).days

    if days_old < 30:
        points = 10
        category = "<30 days"
    elif days_old <= 90:
        points = 7
        category = "30-90 days"
    elif days_old <= 180:
        points = 4
        category = "90-180 days"
    elif days_old <= 365:
        points = 2
        category = "180-365 days"
    else:
        points = 0
        category = ">365 days"

    print(
        f"  RECENCY DEBUG: {institution} | date={parsed.strftime('%Y-%m-%d')} | "
        f"days_old={days_old} | category={category} | points={points}"
    )
    return {"category": category, "points": points}


def apply_seniority_override(signal: dict, breakdown: dict) -> dict:
    """Override seniority for strategic partnerships and launches with Unknown seniority."""
    sig_type = signal.get("signal_type", "").lower()
    domain = signal.get("domain", "").lower()
    seniority = signal.get("seniority", "").lower()
    institution = signal.get("institution", "?")

    # Override 1: partnership + stablecoin/digital_assets + Unknown → 15pts
    if (
        sig_type == "partnership"
        and domain in ("stablecoin", "digital_assets")
        and seniority == "unknown"
    ):
        breakdown["seniority"] = {
            "category": "inferred (strategic partnership)",
            "points": 15,
            "seniority_inferred": True,
        }
        print(
            f"  SENIORITY OVERRIDE: {institution} — partnership + "
            f"{domain} + Unknown → inferred 15pts"
        )

    # Override 2: launch + stablecoin/digital_assets + Unknown → 12pts
    elif (
        sig_type == "launch"
        and domain in ("stablecoin", "digital_assets")
        and seniority == "unknown"
    ):
        breakdown["seniority"] = {
            "category": "inferred (strategic launch)",
            "points": 12,
            "seniority_inferred": True,
        }
        print(
            f"  SENIORITY OVERRIDE: {institution} — launch + "
            f"{domain} + Unknown → inferred 12pts"
        )

    return breakdown


def _profile_weighted_total(
    breakdown: dict, ranking_cfg: dict, institution: str
) -> tuple[int, dict]:
    """Compute weighted score from profile ranking categories."""
    categories = ranking_cfg.get("categories", [])
    weighted_breakdown: dict = {}
    weighted_total = 0.0

    for cat in categories:
        key = str(cat.get("key", "")).strip().lower()
        label = cat.get("label", key or "category")
        weight = int(cat.get("weight", 0))
        component = CATEGORY_COMPONENT_ALIASES.get(key)

        raw_points = 0
        max_points = 100
        if component and isinstance(breakdown.get(component), dict):
            raw_points = float(breakdown[component].get("points", 0))
            max_points = float(COMPONENT_MAX.get(component, 100))
        elif isinstance(breakdown.get(key), dict):
            raw_points = float(breakdown[key].get("points", 0))
            max_points = float(COMPONENT_MAX.get(key, 100))
        else:
            # Unknown custom category key: neutral score fallback.
            raw_points = 50
            max_points = 100

        normalized = 0.0 if max_points <= 0 else max(0.0, min(1.0, raw_points / max_points))
        contribution = normalized * weight
        weighted_total += contribution

        weighted_breakdown[key or label] = {
            "label": label,
            "weight": weight,
            "source_component": component or key,
            "raw_points": raw_points,
            "max_points": max_points,
            "normalized": round(normalized, 4),
            "weighted_points": round(contribution, 2),
        }

    total_rounded = int(round(weighted_total))
    print(f"  PROFILE SCORE: {institution} | weighted_total={total_rounded}")
    return total_rounded, weighted_breakdown


def _tier_from_thresholds(total: int, thresholds: dict) -> str:
    hot = int(thresholds.get("HOT", 80))
    warm = int(thresholds.get("WARM", 60))
    nurture = int(thresholds.get("NURTURE", 40))
    if total >= hot:
        return "HOT"
    if total >= warm:
        return "WARM"
    if total >= nurture:
        return "NURTURE"
    return "HOLD"


def rescore_signal(signal: dict, profile_config: dict | None = None) -> dict:
    """Apply programmatic scoring overrides to a single scored signal."""
    institution = signal.get("institution", signal.get("institution_name", "?"))
    breakdown = signal.get("score_breakdown", {})

    # Action type
    sig_type = signal.get("signal_type", "other").lower()
    action_pts = ACTION_TYPE_SCORES.get(sig_type, 5)
    breakdown["action_type"] = {"category": sig_type, "points": action_pts}

    # Seniority
    seniority_raw = signal.get("seniority", "unknown").lower()
    seniority_pts = SENIORITY_SCORES.get(seniority_raw, 5)
    breakdown["seniority"] = {"category": seniority_raw, "points": seniority_pts}

    # Seniority override for strategic partnerships
    breakdown = apply_seniority_override(signal, breakdown)

    # Domain fit
    domain_raw = signal.get("domain", "other").lower()
    domain_pts = DOMAIN_FIT_SCORES.get(domain_raw, 5)
    breakdown["domain_fit"] = {"category": domain_raw, "points": domain_pts}

    # Institution accessibility
    inst_type_raw = signal.get("institution_type", "unknown").lower()
    inst_pts = INSTITUTION_SCORES.get(inst_type_raw, 5)
    breakdown["institution_accessibility"] = {
        "category": inst_type_raw,
        "points": inst_pts,
    }

    # Recency (programmatic — replaces LLM guess)
    date_str = signal.get("signal_date", "")
    breakdown["recency"] = score_recency(date_str, institution)

    # Recompute total and tier using profile if available
    ranking_cfg = (profile_config or {}).get("ranking") if profile_config else None
    if ranking_cfg and ranking_cfg.get("categories"):
        total, weighted_breakdown = _profile_weighted_total(
            breakdown=breakdown, ranking_cfg=ranking_cfg, institution=institution
        )
        thresholds = ranking_cfg.get(
            "priority_thresholds", {"HOT": 80, "WARM": 60, "NURTURE": 40}
        )
        tier = _tier_from_thresholds(total, thresholds)
        signal["profile_weighted_breakdown"] = weighted_breakdown
        signal["profile_thresholds"] = thresholds
    else:
        total = int(sum(
            cat.get("points", 0)
            for cat in breakdown.values()
            if isinstance(cat, dict) and "points" in cat
        ))
        tier = "HOT" if total >= 80 else "WARM" if total >= 60 else "NURTURE" if total >= 40 else "HOLD"

    signal["score_breakdown"] = breakdown
    signal["total_score"] = total
    signal["priority_tier"] = tier
    signal.pop("outreach_angle", None)

    return signal


# ---------------------------------------------------------------------------
# Agent factory — built from config/agents.yaml
# ---------------------------------------------------------------------------

def build_scorer_agent() -> Agent:
    cfg = _load_yaml("agents.yaml")["signal_scorer"]
    return Agent(
        role=cfg["role"],
        goal=cfg["goal"],
        backstory=cfg["backstory"],
        llm=llm,
        verbose=True,
    )


# ---------------------------------------------------------------------------
# Task factory — built from config/tasks.yaml
# ---------------------------------------------------------------------------

def build_scorer_task(
    agent: Agent, signals_input: list[dict] | None, profile_context: str = ""
) -> Task:
    """Build the scoring task with scout signals injected.

    Args:
        agent:         The scorer Agent instance.
        signals_input: List of signal dicts, or None for raw-text fallback.
    """
    cfg = _load_yaml("tasks.yaml")["scorer_task"]

    if signals_input is not None:
        signals_json = json.dumps(signals_input, indent=2)
        description = cfg["description"].format_map(
            {
                "n_signals": len(signals_input),
                "signals_json": signals_json,
            }
        )
        if profile_context:
            description += (
                "\n\nACTIVE PIPELINE PROFILE (prioritize this ranking intent):\n"
                f"{profile_context}\n"
            )
    else:
        description = (
            "WARNING: Could not parse structured signals. Raw data is "
            "included below for best-effort scoring.\n\n"
        )

    return Task(
        description=description,
        expected_output=cfg["expected_output"],
        agent=agent,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = sys.argv[1:]
    profile_path = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile_path = args[idx + 1]
            del args[idx:idx + 2]

    # 1. Load scout report (from CLI arg or find latest)
    if args:
        report_path = Path(args[0])
        if not report_path.exists():
            print(f"ERROR: File not found: {report_path}")
            sys.exit(1)
    else:
        report_path = find_latest_report()
    print(f"Loading report: {report_path}")

    with open(report_path) as f:
        report_data = json.load(f)

    # Handle both old and new scout output formats
    if "signals" in report_data:
        signals_input = report_data["signals"]
    elif "raw_output" in report_data:
        raw_output = report_data["raw_output"]
        clean = raw_output.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        try:
            signals_input = json.loads(clean.strip())
            if isinstance(signals_input, dict):
                signals_input = signals_input.get(
                    "signals", signals_input.get("results", [])
                )
        except json.JSONDecodeError:
            signals_input = None
    else:
        raise ValueError(
            "Scout report has neither 'signals' nor 'raw_output' field"
        )

    print(
        f"Loaded {len(signals_input) if signals_input else '?'} signals "
        f"from scout report"
    )

    # 2. Score signals in batches to stay within LLM output token limits.
    #    Each signal scores to ~1,400 chars of JSON; Gemini Flash caps at
    #    8,192 tokens (~32,768 chars). Batch size of 10 keeps output well
    #    under that ceiling with headroom for the outer JSON envelope.
    BATCH_SIZE = 10
    all_scored_signals: list[dict] = []
    raw_outputs_on_error: list[str] = []

    if signals_input:
        batches = [
            signals_input[i : i + BATCH_SIZE]
            for i in range(0, len(signals_input), BATCH_SIZE)
        ]
    else:
        batches = [None]  # single pass with raw-text fallback

    profile_context = ""
    profile_config = None
    if profile_path:
        try:
            profile = load_profile(profile_path)
            profile_context = json.dumps(profile.model_dump(), indent=2)
            profile_config = profile.model_dump()
            print(f"Loaded profile: {profile_path}")
        except Exception as exc:
            print(f"WARNING: failed to load profile '{profile_path}': {exc}")
    elif isinstance(report_data.get("profile"), dict):
        try:
            validated_profile = validate_profile_dict(report_data["profile"])
            profile_config = validated_profile.model_dump()
            profile_context = json.dumps(profile_config, indent=2)
            print("Loaded profile from scout report payload.")
        except Exception as exc:
            print(f"WARNING: failed to load profile from scout report: {exc}")

    scorer_agent = build_scorer_agent()

    for batch_idx, batch in enumerate(batches, start=1):
        print(f"\n{'=' * 60}")
        print(
            f"BATCH {batch_idx}/{len(batches)}: scoring signals "
            f"{(batch_idx - 1) * BATCH_SIZE + 1}–"
            f"{min(batch_idx * BATCH_SIZE, len(signals_input) if signals_input else 0)}"
        )
        print("=" * 60)

        task = build_scorer_task(scorer_agent, batch, profile_context=profile_context)
        crew = Crew(agents=[scorer_agent], tasks=[task], verbose=True)
        result = crew.kickoff()

        # 3. Parse the scored JSON from the agent output
        result_text = str(result).strip()

        # Strip markdown code fences if the LLM added them
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
        if result_text.endswith("```"):
            result_text = result_text.rsplit("```", 1)[0]
        result_text = result_text.strip()

        try:
            scored_data = json.loads(result_text)
        except json.JSONDecodeError:
            print(f"WARNING: Batch {batch_idx} — could not parse agent output as JSON.")
            raw_outputs_on_error.append(result_text)
            scored_data = {"signals": []}

        batch_signals = scored_data.get("signals", [])

        # Guard: if JSON parsed but signals list is empty, preserve raw output
        if not batch_signals:
            print(
                f"WARNING: Batch {batch_idx} — JSON parsed successfully but "
                f"returned 0 signals. Raw output preserved for debugging."
            )
            raw_outputs_on_error.append(result_text)

        all_scored_signals.extend(batch_signals)
        print(f"  Batch {batch_idx} yielded {len(batch_signals)} scored signal(s).")

    signals = all_scored_signals

    # 4. Programmatic post-processing overrides
    print("\n" + "=" * 60)
    print("PHASE: Programmatic scoring overrides")
    print("=" * 60)
    signals = [rescore_signal(sig, profile_config=profile_config) for sig in signals]

    # Re-sort by score descending
    signals.sort(key=lambda s: s.get("total_score", 0), reverse=True)

    # 5. Compute tier counts
    tier_counts = {"HOT": 0, "WARM": 0, "NURTURE": 0, "HOLD": 0}
    for sig in signals:
        tier = sig.get("priority_tier", "HOLD").upper()
        if tier in tier_counts:
            tier_counts[tier] += 1
        else:
            tier_counts["HOLD"] += 1

    # 6. Save scored report
    OUTPUTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scored_file = OUTPUTS_DIR / f"scored_report_{timestamp}.json"

    output_payload = {
        "timestamp": datetime.now().isoformat(),
        "source_report": str(report_path.name),
        "hot_count": tier_counts["HOT"],
        "warm_count": tier_counts["WARM"],
        "nurture_count": tier_counts["NURTURE"],
        "hold_count": tier_counts["HOLD"],
        "total_signals": len(signals),
        "signals": signals,
    }

    # Preserve any raw LLM output that failed to parse or returned empty
    if raw_outputs_on_error:
        output_payload["parse_errors"] = len(raw_outputs_on_error)
        output_payload["raw_outputs_on_error"] = raw_outputs_on_error

    with open(scored_file, "w") as f:
        json.dump(output_payload, f, indent=2)

    # 7. Print terminal summary
    print("\n" + "=" * 60)
    print("SIGNAL SCORER SUMMARY")
    print("=" * 60)
    print(f"  HOT:     {tier_counts['HOT']}")
    print(f"  WARM:    {tier_counts['WARM']}")
    print(f"  NURTURE: {tier_counts['NURTURE']}")
    print(f"  HOLD:    {tier_counts['HOLD']}")
    print(f"  TOTAL:   {len(signals)}")
    print("-" * 60)
    print("TOP 5 SIGNALS:")
    print("-" * 60)
    for i, sig in enumerate(signals[:5], 1):
        score = sig.get("total_score", "?")
        name = sig.get("institution", sig.get("institution_name", "Unknown"))
        tier = sig.get("priority_tier", "?")
        print(f"  {i}. [{tier}] {name} — Score: {score}")
    print("=" * 60)
    print(f"\nScored report saved to {scored_file}")
