"""
briefing_agent.py — conversational agent for building pipeline profiles.
"""

from __future__ import annotations

import json
import os
from typing import Any

from crewai import LLM
from dotenv import load_dotenv

from signal_pipeline_backend.pipeline_profile import default_profile

load_dotenv()


BRIEFING_SYSTEM_PROMPT = """
You are Briefing Agent for a signal intelligence pipeline.
Your job is to have a concise conversation and gather:
1) what signals to look for (objective)
2) where (regions/countries)
3) when (time window)
4) how to rank (up to 5 weighted categories and thresholds)
5) constraints (inclusions/exclusions, output size)

Rules:
- Keep responses concise and practical.
- Ask only 1-3 targeted follow-up questions at a time.
- Propose ranking categories (max 5) and let the user override.
- Do NOT fabricate facts.
"""

PERSONA_SYSTEM_PROMPT = """
You are Persona Setup Agent for a signal intelligence dashboard.
Your job is to gather a concise persona profile for downstream briefing/pipeline use.

Collect:
1) persona type (company or individual)
2) name
3) expertise domains
4) industries/markets of interest
5) geography focus
6) goals and constraints

Rules:
- Keep replies concise and practical.
- Ask 1-3 focused follow-up questions at a time.
- If a detail is unknown, offer sensible default options.
"""


FINALIZE_PROMPT = """
Using the full conversation transcript, produce ONLY valid JSON for this schema:
{
  "profile_id": "profile_xxx",
  "version": 1,
  "created_at": "ISO datetime",
  "objective": "string",
  "regions": ["..."],
  "countries": ["..."],
  "time_window_days": 90,
  "domains": ["..."],
  "signal_types": ["..."],
  "inclusion_rules": ["..."],
  "exclusion_rules": ["..."],
  "target_output": {
    "min_signals": 20,
    "max_signals": 25,
    "dedupe_policy": "exclude_seen"
  },
  "ranking": {
    "categories": [
      {"key":"...", "label":"...", "weight":30, "description":"..."}
    ],
    "priority_thresholds": {"HOT":80, "WARM":60, "NURTURE":40}
  }
}

Hard constraints:
- ranking.categories length <= 5
- sum(weights) = 100
- HOT > WARM > NURTURE >= 0
- output must be JSON only, no markdown fences
"""


ADJUST_PROMPT = """
You are updating an existing pipeline profile from user adjustment instructions.
Return ONLY valid JSON profile, preserving unchanged fields unless explicitly adjusted.

Requirements:
- ranking categories max 5
- weights sum to 100
- HOT > WARM > NURTURE >= 0
- output JSON only, no markdown
"""

FINALIZE_PERSONA_PROMPT = """
Using the full conversation transcript, output ONLY valid JSON:
{
  "persona_id": "persona_xxx",
  "created_at": "ISO datetime",
  "persona_type": "company|person",
  "name": "string",
  "expertise": ["..."],
  "industries": ["..."],
  "markets": ["..."],
  "regions": ["..."],
  "goals": ["..."],
  "constraints": ["..."],
  "notes": "string"
}

Rules:
- Output must be JSON only, no markdown.
- Arrays may be empty, but include all keys.
"""


def _build_llm() -> LLM | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return LLM(model="gemini/gemini-2.0-flash", api_key=api_key, max_tokens=4096)


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "").strip()
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def initial_question() -> str:
    seed = default_profile()
    return (
        "What should this pipeline focus on? Please share:\n"
        "1) objective,\n"
        "2) regions/countries,\n"
        "3) time window,\n"
        "4) how you want scoring categories weighted (up to 5),\n"
        "5) exclusions.\n\n"
        f"Default target is {seed.target_output.get('min_signals', 20)}-"
        f"{seed.target_output.get('max_signals', 25)} net-new signals."
    )


def generate_reply(history: list[dict[str, str]]) -> str:
    llm = _build_llm()
    if llm is None:
        return (
            "I can proceed with defaults now, or you can provide objective, geography, "
            "time window, ranking categories (max 5), and exclusions."
        )

    prompt = (
        f"{BRIEFING_SYSTEM_PROMPT}\n\n"
        "Conversation so far:\n"
        f"{_messages_to_prompt(history)}\n\n"
        "Respond to the user and ask follow-up questions only if needed."
    )
    try:
        return str(llm.call(prompt)).strip()
    except Exception:
        return (
            "Please continue with objective, geography, time window, "
            "ranking weights, and exclusions."
        )


def persona_initial_question() -> str:
    return (
        "Let’s set up your persona. Please share:\n"
        "1) company or person,\n"
        "2) name,\n"
        "3) expertise,\n"
        "4) industries/markets,\n"
        "5) region focus,\n"
        "6) goals or constraints."
    )


def generate_persona_reply(history: list[dict[str, str]]) -> str:
    llm = _build_llm()
    if llm is None:
        return (
            "Please provide persona type (company/person), name, expertise, "
            "industries, region focus, and goals/constraints."
        )

    prompt = (
        f"{PERSONA_SYSTEM_PROMPT}\n\n"
        "Conversation so far:\n"
        f"{_messages_to_prompt(history)}\n\n"
        "Respond with concise follow-up questions as needed."
    )
    try:
        return str(llm.call(prompt)).strip()
    except Exception:
        return (
            "Please provide persona type, name, expertise, industries/markets, "
            "regions, and goals/constraints."
        )


def finalize_profile_json(history: list[dict[str, str]]) -> str:
    llm = _build_llm()
    if llm is None:
        fallback = default_profile().model_dump()
        return json.dumps(fallback, indent=2)

    prompt = (
        f"{BRIEFING_SYSTEM_PROMPT}\n\n"
        f"{FINALIZE_PROMPT}\n\n"
        "Conversation transcript:\n"
        f"{_messages_to_prompt(history)}"
    )
    try:
        return str(llm.call(prompt)).strip()
    except Exception:
        fallback = default_profile().model_dump()
        return json.dumps(fallback, indent=2)


def adjust_profile_json(current_profile: dict[str, Any], adjustment_text: str) -> str:
    llm = _build_llm()
    if llm is None:
        merged = dict(current_profile)
        return json.dumps(merged, indent=2)

    prompt = (
        f"{BRIEFING_SYSTEM_PROMPT}\n\n"
        f"{ADJUST_PROMPT}\n\n"
        "Current profile JSON:\n"
        f"{json.dumps(current_profile, indent=2)}\n\n"
        "User adjustment request:\n"
        f"{adjustment_text}\n\n"
        "Return the updated profile JSON."
    )
    try:
        return str(llm.call(prompt)).strip()
    except Exception:
        merged = dict(current_profile)
        return json.dumps(merged, indent=2)


def finalize_persona_json(history: list[dict[str, str]]) -> str:
    llm = _build_llm()
    if llm is None:
        fallback = {
            "persona_id": "persona_default",
            "created_at": "",
            "persona_type": "person",
            "name": "",
            "expertise": [],
            "industries": [],
            "markets": [],
            "regions": [],
            "goals": [],
            "constraints": [],
            "notes": "",
        }
        return json.dumps(fallback, indent=2)

    prompt = (
        f"{PERSONA_SYSTEM_PROMPT}\n\n"
        f"{FINALIZE_PERSONA_PROMPT}\n\n"
        "Conversation transcript:\n"
        f"{_messages_to_prompt(history)}"
    )
    try:
        return str(llm.call(prompt)).strip()
    except Exception:
        fallback = {
            "persona_id": "persona_default",
            "created_at": "",
            "persona_type": "person",
            "name": "",
            "expertise": [],
            "industries": [],
            "markets": [],
            "regions": [],
            "goals": [],
            "constraints": [],
            "notes": "",
        }
        return json.dumps(fallback, indent=2)


def default_assistant_message() -> dict[str, Any]:
    return {"role": "assistant", "content": initial_question()}


def default_persona_message() -> dict[str, Any]:
    return {"role": "assistant", "content": persona_initial_question()}
