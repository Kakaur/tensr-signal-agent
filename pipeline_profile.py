"""
pipeline_profile.py — schema and persistence for briefing-generated profiles.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


PROJECT_ROOT = Path(__file__).parent
PROFILES_DIR = PROJECT_ROOT / "outputs" / "profiles"


class RankingCategory(BaseModel):
    key: str
    label: str
    weight: int = Field(ge=0, le=100)
    description: str = ""


class RankingConfig(BaseModel):
    categories: list[RankingCategory] = Field(default_factory=list, max_length=5)
    priority_thresholds: dict[str, int] = Field(
        default_factory=lambda: {"HOT": 80, "WARM": 60, "NURTURE": 40}
    )

    @field_validator("categories")
    @classmethod
    def ensure_unique_category_keys(cls, value: list[RankingCategory]) -> list[RankingCategory]:
        keys = [c.key for c in value]
        if len(keys) != len(set(keys)):
            raise ValueError("ranking category keys must be unique")
        return value

    @model_validator(mode="after")
    def validate_weights_and_thresholds(self) -> "RankingConfig":
        total_weight = sum(c.weight for c in self.categories)
        if total_weight != 100:
            raise ValueError("ranking category weights must sum to 100")

        hot = int(self.priority_thresholds.get("HOT", 80))
        warm = int(self.priority_thresholds.get("WARM", 60))
        nurture = int(self.priority_thresholds.get("NURTURE", 40))
        if not (hot > warm > nurture >= 0):
            raise ValueError("priority thresholds must satisfy HOT > WARM > NURTURE >= 0")
        return self


class PipelineProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: f"profile_{uuid4().hex[:12]}")
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    objective: str
    regions: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    time_window_days: int = Field(default=90, ge=1, le=3650)
    domains: list[str] = Field(default_factory=list)
    signal_types: list[str] = Field(default_factory=list)
    inclusion_rules: list[str] = Field(default_factory=list)
    exclusion_rules: list[str] = Field(default_factory=list)
    target_output: dict[str, Any] = Field(
        default_factory=lambda: {
            "min_signals": 20,
            "max_signals": 25,
            "dedupe_policy": "prefer_new",
        }
    )
    ranking: RankingConfig


def default_profile() -> PipelineProfile:
    return PipelineProfile(
        objective="Identify 20-25 net-new buying signals for AI transformation and digital modernization.",
        regions=["Eastern Europe", "Middle East"],
        countries=[],
        time_window_days=90,
        domains=[
            "ai_transformation",
            "ai_implementation",
            "agentic_automation",
            "industrial_automation",
            "sovereign_cloud",
        ],
        signal_types=["hire", "partnership", "launch", "pilot", "contract"],
        inclusion_rules=[
            "Target institutions that are buyers/adopters, not vendors.",
            "Prioritize strategic initiatives with implementation budget signals.",
        ],
        exclusion_rules=[
            "Exclude Tier-1 global banks, Big Tech, and top global consultancies.",
            "Exclude primary crypto/NFT/Web3 companies.",
        ],
        ranking=RankingConfig(
            categories=[
                RankingCategory(
                    key="action_strength",
                    label="Action Strength",
                    weight=30,
                    description="How concrete the institutional action is.",
                ),
                RankingCategory(
                    key="buyer_fit",
                    label="Buyer Fit",
                    weight=25,
                    description="How likely the institution is to buy consulting/services.",
                ),
                RankingCategory(
                    key="domain_fit",
                    label="Domain Fit",
                    weight=20,
                    description="Alignment with chosen use-case domains.",
                ),
                RankingCategory(
                    key="seniority",
                    label="Seniority",
                    weight=15,
                    description="Decision-maker level tied to the signal.",
                ),
                RankingCategory(
                    key="recency",
                    label="Recency",
                    weight=10,
                    description="How recent the signal is.",
                ),
            ],
            priority_thresholds={"HOT": 80, "WARM": 60, "NURTURE": 40},
        ),
    )


def validate_profile_dict(payload: dict) -> PipelineProfile:
    return PipelineProfile.model_validate(payload)


def validate_profile_text(profile_text: str) -> PipelineProfile:
    raw = profile_text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Profile JSON parsing failed: {exc}") from exc

    try:
        return validate_profile_dict(parsed)
    except ValidationError as exc:
        raise ValueError(f"Profile schema validation failed: {exc}") from exc


def save_profile(profile: PipelineProfile) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PROFILES_DIR / f"pipeline_profile_{timestamp}_{profile.profile_id}.json"
    with open(path, "w") as f:
        json.dump(profile.model_dump(), f, indent=2)
    return path


def load_profile(path: str | Path) -> PipelineProfile:
    p = Path(path)
    with open(p) as f:
        data = json.load(f)
    return validate_profile_dict(data)
