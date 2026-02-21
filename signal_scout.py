import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from crewai import LLM, Agent, Crew, Task
from dotenv import load_dotenv
from tavily import TavilyClient

import database
from pipeline_profile import load_profile

load_dotenv()

# ---------------------------------------------------------------------------
# Paths — all relative to project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
CONFIG_DIR   = PROJECT_ROOT / "config"
OUTPUTS_DIR  = PROJECT_ROOT / "outputs"

# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------
llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=os.environ["GEMINI_API_KEY"],
)

# ---------------------------------------------------------------------------
# Tavily client (direct API — no agent tool wrapper)
# ---------------------------------------------------------------------------
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# ---------------------------------------------------------------------------
# Search queries — geographically diverse, covering all signal types
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # ── Eastern Europe — Industrial Automation & Digital Assets ──────────────
    "Poland industrial automation AI 2025",
    "Poland nearshore logistics digital transformation 2025",
    "Polish bank digital assets EU AI Act compliance 2025",
    "Romania industrial AI transformation 2025",
    "Romania nearshore logistics technology 2025",
    "Czech Republic industrial automation digital 2025",
    "Czech bank AI transformation 2025",
    "Eastern Europe Industrial 5.0 adoption 2025",
    "Eastern Europe Digital Product Passport DPP 2025",
    "Eastern Europe EU AI Act compliance fintech 2025",
    "Eastern Europe labor cost AI offset 2025",
    "Poland fintech Series A digital assets 2025",
    "Romania fintech AI partnership 2025",
    "Czech fintech digital transformation 2025",
    "Eastern Europe regional bank AI pilot 2025",
    "Eastern Europe sovereign cloud initiative 2025",
    # ── Middle East — Non-Oil Diversification & Giga-Projects ────────────────
    "Saudi Arabia non-oil GDP AI strategy 2025",
    "Saudi Arabia giga-project digital transformation 2025",
    "Saudi Arabia National AI Strategy alignment 2025",
    "UAE in-country value ICV digital assets 2025",
    "UAE smart city orchestration AI 2025",
    "UAE sovereign cloud initiative 2025",
    "Qatar non-oil diversification technology 2025",
    "Kuwait digital transformation AI 2025",
    "Saudi Arabia family conglomerate digital assets 2025",
    "UAE regional champion AI transformation 2025",
    "Middle East sovereign wealth fund digital assets 2025",
    "Saudi fintech digital asset tokenization 2025",
    "UAE bank digital assets pilot 2025",
    "Qatar bank AI transformation 2025",
    "Kuwait bank digital assets 2025",
    "Abu Dhabi sovereign cloud digital assets 2025",
    "Middle East Industrial 5.0 smart manufacturing 2025",
    "Middle East Digital Product Passport DPP supply chain 2025",
    # ── EE + ME — Cross-region signals ───────────────────────────────────────
    "Eastern Europe Middle East fintech AI Series A 2025",
    "regional bank Eastern Europe digital transformation hire 2025",
    "family conglomerate Middle East AI consulting 2025",
    "industrial company Poland Romania digitalization 2025",
    "Gulf Cooperation Council GCC fintech AI pilot 2025",
]

DOMAIN_QUERY_HINTS = {
    "ai_transformation": "enterprise AI transformation",
    "ai_implementation": "AI implementation rollout",
    "agentic_automation": "agentic automation AI agents operations",
    "industrial_automation": "industrial automation Industry 5.0",
    "digital_product_passport": "digital product passport DPP supply chain",
    "sovereign_cloud": "sovereign cloud data infrastructure",
    "tokenized_rwa": "tokenized real world assets institutional pilot",
    "smart_city": "smart city orchestration AI",
    "ai_compliance_risk": "EU AI Act compliance AI governance",
}

COUNTRY_TO_REGION = {
    "saudi arabia": "Middle East",
    "uae": "Middle East",
    "united arab emirates": "Middle East",
    "qatar": "Middle East",
    "kuwait": "Middle East",
    "oman": "Middle East",
    "bahrain": "Middle East",
    "poland": "Eastern Europe",
    "romania": "Eastern Europe",
    "czech republic": "Eastern Europe",
    "czechia": "Eastern Europe",
    "hungary": "Eastern Europe",
    "slovakia": "Eastern Europe",
    "bulgaria": "Eastern Europe",
    "croatia": "Eastern Europe",
    "serbia": "Eastern Europe",
    "slovenia": "Eastern Europe",
}

COUNTRY_KEYWORDS = {
    "saudi arabia": ("saudi arabia", "saudi"),
    "uae": ("uae", "united arab emirates", "abu dhabi", "dubai"),
    "qatar": ("qatar", "doha"),
    "kuwait": ("kuwait",),
    "oman": ("oman",),
    "bahrain": ("bahrain",),
    "poland": ("poland", "polish"),
    "romania": ("romania", "romanian"),
    "czech republic": ("czech republic", "czech", "czechia"),
    "hungary": ("hungary", "hungarian"),
    "slovakia": ("slovakia", "slovak"),
    "bulgaria": ("bulgaria", "bulgarian"),
    "croatia": ("croatia", "croatian"),
    "serbia": ("serbia", "serbian"),
    "slovenia": ("slovenia", "slovenian"),
}

NON_COMPANY_TOKENS = (
    "region",
    "country",
    "ministry",
    "government",
    "agency",
    "department",
    "authority",
    "municipality",
    "city council",
    "county council",
    "national bank",
    "central bank",
    "public sector",
    "state",
    "federal",
    "parliament",
    "university",
    "school",
    "hospital",
    "ngo",
    "foundation",
    "association",
    "organization",
    "organisation",
)

GENERIC_INSTITUTION_NOUNS = {
    "enterprise",
    "enterprises",
    "business",
    "businesses",
    "company",
    "companies",
    "customer",
    "customers",
    "client",
    "clients",
    "executive",
    "executives",
    "employee",
    "employees",
    "retailer",
    "retailers",
    "manufacturer",
    "manufacturers",
    "institution",
    "institutions",
    "sector",
    "industry",
    "industries",
    "market",
    "markets",
    "organization",
    "organizations",
    "organisation",
    "organisations",
}

INSTITUTION_FILLER_WORDS = {
    "the",
    "and",
    "of",
    "in",
    "for",
    "to",
    "from",
    "across",
    "global",
    "regional",
    "national",
    "international",
    "local",
    "middle",
    "east",
    "eastern",
    "europe",
    "africa",
    "gcc",
    "emea",
    "uk",
    "uae",
}

COMPANY_HINT_TOKENS = {
    "inc",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "plc",
    "group",
    "sa",
    "ag",
    "nv",
    "spa",
    "gmbh",
    "srl",
    "oyj",
    "asa",
    "ab",
    "holding",
    "holdings",
    "technologies",
    "technology",
    "systems",
    "solutions",
    "bank",
}


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def run_searches(queries: list[str]) -> list[dict]:
    """Run all search queries via Tavily API and return deduplicated results."""
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        print(f"  Searching: {query}")
        try:
            response = tavily_client.search(query=query, max_results=8)
            for result in response.get("results", []):
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(
                        {
                            "query": query,
                            "title": result.get("title", ""),
                            "url": url,
                            "content": result.get("content", ""),
                        }
                    )
        except Exception as e:
            print(f"  WARNING: Search failed for '{query}': {e}")

    return all_results


# ---------------------------------------------------------------------------
# Agent factory — built from config/agents.yaml
# ---------------------------------------------------------------------------

def build_scout_agent() -> Agent:
    cfg = _load_yaml("agents.yaml")["signal_scout"]
    return Agent(
        role=cfg["role"],
        goal=cfg["goal"],
        backstory=cfg["backstory"],
        tools=[],  # No tools — works with provided data only
        llm=llm,
        verbose=True,
    )


# ---------------------------------------------------------------------------
# Task factory — built from config/tasks.yaml
# ---------------------------------------------------------------------------

def build_scout_task(
    agent: Agent, search_results: list[dict], profile_context: str = ""
) -> Task:
    """Build the scout task with pre-fetched search results injected."""
    cfg = _load_yaml("tasks.yaml")["scout_task"]

    search_results_json = json.dumps(search_results, indent=2)

    description = cfg["description"].format_map(
        {
            "n_results": len(search_results),
            "search_results_json": search_results_json,
        }
    )
    if profile_context:
        description += (
            "\n\nACTIVE PIPELINE PROFILE (use this as hard guidance):\n"
            f"{profile_context}\n"
        )

    return Task(
        description=description,
        expected_output=cfg["expected_output"],
        agent=agent,
    )


# ---------------------------------------------------------------------------
# Post-processing: validate URLs against actual search results
# ---------------------------------------------------------------------------

def validate_signals(
    signals: list[dict], search_results: list[dict]
) -> list[dict]:
    """Remove any signal whose source_url is not in the search results."""
    valid_urls = {r["url"] for r in search_results}
    validated = []
    dropped = 0

    for sig in signals:
        url = sig.get("source_url", "")
        if url in valid_urls:
            validated.append(sig)
        else:
            dropped += 1
            print(
                f"  DROPPED (invalid URL): {sig.get('institution', '?')} — {url}"
            )

    if dropped:
        print(f"  Dropped {dropped} signal(s) with unverified URLs")

    return validated


_TIER1_INSTITUTIONS = {
    # Global banks (G-SIBs)
    "goldman sachs", "jp morgan", "jpmorgan", "citigroup", "citi",
    "bank of america", "wells fargo", "hsbc", "barclays", "bnp paribas",
    "deutsche bank", "credit suisse", "ubs", "societe generale",
    "morgan stanley", "blackrock", "fidelity", "vanguard",
    # Big Tech (MAGMA)
    "microsoft", "apple", "google", "alphabet", "meta", "amazon", "aws",
    # Top-10 Global Consultancies
    "mckinsey", "boston consulting group", "bcg", "bain", "deloitte",
    "pwc", "pricewaterhousecoopers", "kpmg", "ernst & young", "ey",
    "accenture",
}

_LARGE_ENTERPRISE_EXCLUSIONS = {
    # Large global tech/platform vendors outside ICP
    "adobe",
    "lenovo",
    "oracle",
    "sap",
    "ibm",
    "cisco",
    "salesforce",
    "servicenow",
    "workday",
    "intel",
    "amd",
    "nvidia",
    "dell",
    "hp",
    "hewlett packard",
    "hpe",
    "vmware",
    "palantir",
    "snowflake",
    "databricks",
}

_CRYPTO_PRIMARY_KEYWORDS = {
    "cryptocurrency", "crypto exchange", "nft marketplace", "web3 protocol",
    "defi protocol", "bitcoin miner", "crypto wallet provider",
    "token launchpad", "crypto trading platform",
}

_AI_NATIVE_INSTITUTION_KEYWORDS = {
    "openai",
    "anthropic",
    "cohere",
    "mistral ai",
    "hugging face",
    "stability ai",
    "midjourney",
    "perplexity",
    "character.ai",
    "xai",
    "deepmind",
}

_AI_NATIVE_SELF_PATTERNS = (
    "is an ai startup",
    "is a ai startup",
    "is an artificial intelligence startup",
    "is an ai company",
    "is a generative ai company",
    "is an llm company",
    "builds ai models",
    "develops ai models",
    "develops foundation models",
    "builds foundation models",
    "llm provider",
    "model provider",
    "model lab",
    "ai lab",
    "ai platform provider",
    "ai software vendor",
    "offers ai software",
    "sells ai software",
    "ai-native company",
)

_AI_PRIORITY_DOMAINS = {
    "ai_transformation",
    "ai_implementation",
    "agentic_automation",
    "ai_compliance_risk",
}

_AI_DOMAIN_SYNONYMS = {
    "ai implementation": "ai_implementation",
    "ai_implementation": "ai_implementation",
    "enterprise_ai_implementation": "ai_implementation",
    "agentic automation": "agentic_automation",
    "agentic_automation": "agentic_automation",
    "ai_agents": "agentic_automation",
    "automation_agents": "agentic_automation",
    "ai transformation": "ai_transformation",
    "ai_transformation": "ai_transformation",
    "ai_compliance_risk": "ai_compliance_risk",
}

_AI_HINT_KEYWORDS = (
    "agentic",
    "ai agent",
    "llm",
    "copilot",
    "genai",
    "generative ai",
    "enterprise ai",
    "ai transformation",
    "ai rollout",
    "ai implementation",
    "workflow automation",
    "intelligent automation",
)


def filter_tier1(signals: list[dict]) -> list[dict]:
    """Remove Tier-1 institutions and large global enterprises outside ICP."""
    kept = []
    for sig in signals:
        institution = sig.get("institution", "")
        institution_lower = institution.lower()
        tier = sig.get("institution_tier", "").lower()

        blocked_name = any(name in institution_lower for name in _TIER1_INSTITUTIONS)
        blocked_large = any(name in institution_lower for name in _LARGE_ENTERPRISE_EXCLUSIONS)
        if tier == "tier1" or blocked_name or blocked_large:
            print(
                f"  FILTERED {institution} — Tier 1 / global giant exclusion"
            )
        else:
            kept.append(sig)
    return kept


def filter_crypto(signals: list[dict]) -> list[dict]:
    """Remove companies whose primary business is Crypto, NFTs, or Web3.

    Note: "Digital Assets" in the context of this agent refers to
    Tokenized Real World Assets (RWA), Sovereign Data Assets, and
    Industrial IP — NOT cryptocurrencies or speculative tokens.
    """
    kept = []
    for sig in signals:
        institution = sig.get("institution", "?")
        summary_lower = sig.get("summary", "").lower()
        domain = sig.get("domain", "").lower()

        is_crypto_primary = (
            domain == "crypto"
            or any(kw in summary_lower for kw in _CRYPTO_PRIMARY_KEYWORDS)
        )

        if is_crypto_primary:
            print(f"  FILTERED {institution} — Primary crypto/NFT/Web3 business exclusion")
        else:
            kept.append(sig)
    return kept


def filter_ai_native_companies(signals: list[dict]) -> list[dict]:
    """Remove AI-native companies that primarily build/sell AI products."""
    kept = []
    for sig in signals:
        institution = str(sig.get("institution", "")).strip()
        summary = str(sig.get("summary", "")).strip()
        institution_lower = institution.lower()
        summary_lower = summary.lower()

        known_ai_native = any(
            name in institution_lower for name in _AI_NATIVE_INSTITUTION_KEYWORDS
        )

        # Bias toward institution-local context to avoid dropping buyers that
        # merely mention AI vendors in the summary text.
        local_window = summary_lower
        if institution_lower and institution_lower in summary_lower:
            start = summary_lower.find(institution_lower)
            local_window = summary_lower[start:start + 240]

        self_described_ai_vendor = any(
            pattern in local_window for pattern in _AI_NATIVE_SELF_PATTERNS
        )

        if known_ai_native or self_described_ai_vendor:
            print(f"  FILTERED {institution or '?'} — AI-native company exclusion")
            continue

        kept.append(sig)

    return kept


def filter_old_signals(signals: list[dict], cutoff_days: int = 90) -> list[dict]:
    """Remove any signal whose signal_date is older than cutoff_days from today."""
    cutoff = datetime.now() - timedelta(days=cutoff_days)
    kept = []
    for sig in signals:
        date_str = sig.get("signal_date", "")
        institution = sig.get("institution", "?")
        parsed = None

        # Try YYYY-MM-DD first, then YYYY-MM
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except (ValueError, TypeError):
                continue

        if parsed is None:
            # Cannot parse date — keep the signal to avoid false drops
            kept.append(sig)
        elif parsed < cutoff:
            print(f"  FILTERED {institution} — signal_date {date_str} is older than {cutoff_days} days")
        else:
            kept.append(sig)

    return kept


def apply_dedupe_policy(
    signals: list[dict], dedupe_policy: str, min_count: int
) -> list[dict]:
    """Apply dedupe policy while keeping enough candidates for target output.

    Policies:
    - exclude_seen: strict new-only
    - allow_seen: keep both new and seen
    - prefer_new: keep new first, backfill seen if below min_count
    """
    existing_fps = database.get_existing_fingerprints()
    unseen: list[dict] = []
    seen: list[dict] = []
    batch_fps: set[str] = set()
    dropped_batch = 0

    for sig in signals:
        fp = database.signal_fingerprint(sig)
        if fp in batch_fps:
            dropped_batch += 1
            continue
        batch_fps.add(fp)
        if fp in existing_fps:
            seen.append(sig)
        else:
            unseen.append(sig)

    policy = (dedupe_policy or "prefer_new").strip().lower()
    if policy == "exclude_seen":
        selected = list(unseen)
        # Honor min_count over strictness to prevent near-empty runs.
        if len(selected) < min_count:
            selected.extend(seen[: max(0, min_count - len(selected))])
            print(
                f"  DEDUPE FALLBACK: strict exclude_seen relaxed to meet "
                f"minimum target {min_count}"
            )
    elif policy == "allow_seen":
        selected = unseen + seen
    else:
        # prefer_new
        selected = list(unseen)
        if len(selected) < min_count:
            selected.extend(seen[: max(0, min_count - len(selected))])

    print(
        f"  DEDUPE POLICY '{policy}': unseen={len(unseen)} seen={len(seen)} "
        f"dropped_batch={dropped_batch} selected={len(selected)}"
    )
    return selected


def enforce_output_window(
    signals: list[dict], min_count: int = 20, max_count: int = 25
) -> list[dict]:
    """Clamp output to max_count and warn if unable to meet min_count."""
    ordered = sorted(
        signals,
        key=lambda s: (
            s.get("signal_date", ""),
            s.get("run_timestamp", ""),
        ),
        reverse=True,
    )
    trimmed = ordered[:max_count]
    if len(trimmed) < min_count:
        print(
            f"  WARNING: only {len(trimmed)} new unique signals found "
            f"(target {min_count}-{max_count})"
        )
    else:
        print(f"  OUTPUT WINDOW: returning {len(trimmed)} new unique signals")
    return trimmed


def resolve_profile_targets(profile_dict: dict | None) -> tuple[int, int, int, str]:
    """Return (min_count, max_count, recency_days, dedupe_policy)."""
    if not profile_dict:
        return 20, 25, 90, "prefer_new"

    target = profile_dict.get("target_output") or {}
    min_count = int(target.get("min_signals", 20))
    max_count = int(target.get("max_signals", 25))
    if max_count < min_count:
        max_count = min_count

    recency_days = int(profile_dict.get("time_window_days", 90))
    recency_days = max(1, recency_days)
    dedupe_policy = str(target.get("dedupe_policy", "prefer_new"))
    return min_count, max_count, recency_days, dedupe_policy


def _detect_country(text: str) -> str:
    lower = (text or "").lower()
    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return country.title() if country != "uae" else "UAE"
    return ""


def _detect_region(text: str) -> str:
    lower = (text or "").lower()
    if "middle east" in lower or "gcc" in lower or "gulf" in lower:
        return "Middle East"
    if "eastern europe" in lower:
        return "Eastern Europe"
    return ""


def enrich_geo_fields(signals: list[dict], search_results: list[dict]) -> list[dict]:
    """Ensure each signal has both country and region values."""
    url_ctx: dict[str, str] = {}
    for item in search_results:
        url = item.get("url", "")
        if not url:
            continue
        url_ctx[url] = " ".join(
            [
                str(item.get("query", "")),
                str(item.get("title", "")),
                str(item.get("content", "")),
            ]
        )

    for sig in signals:
        country = (sig.get("country") or "").strip()
        region = (sig.get("region") or "").strip()
        context_text = " ".join(
            [
                str(sig.get("institution", "")),
                str(sig.get("summary", "")),
                url_ctx.get(sig.get("source_url", ""), ""),
            ]
        )

        if not country:
            country = _detect_country(context_text)
        if not region:
            region = _detect_region(context_text)
        if not region and country:
            region = COUNTRY_TO_REGION.get(country.lower(), "")

        # Keep explicit values for downstream consumers even when inference is weak.
        sig["country"] = country or "Unspecified"
        sig["region"] = region or "Unspecified"
    return signals


def filter_non_company_institutions(signals: list[dict]) -> list[dict]:
    """Keep only company-like institutions and drop regions/countries/organizations."""
    country_names = set(COUNTRY_KEYWORDS.keys())
    region_names = {v.lower() for v in COUNTRY_TO_REGION.values()}
    dropped = 0
    kept: list[dict] = []

    for sig in signals:
        institution = str(sig.get("institution", "")).strip()
        low = institution.lower()
        if not institution:
            dropped += 1
            continue

        if low in country_names or low in region_names:
            dropped += 1
            print(f"  FILTERED {institution} — institution is a geography label")
            continue

        if any(token in low for token in NON_COMPANY_TOKENS):
            dropped += 1
            print(f"  FILTERED {institution} — non-company institution type")
            continue

        kept.append(sig)

    print(f"  COMPANY FILTER: kept {len(kept)}/{len(signals)} (dropped {dropped})")
    return kept


def filter_generic_institution_labels(signals: list[dict]) -> list[dict]:
    """Drop generic group labels and keep only concrete company names."""
    kept: list[dict] = []
    dropped = 0

    for sig in signals:
        institution = str(sig.get("institution", "")).strip()
        low = institution.lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", low) if t]
        alpha_tokens = [t for t in tokens if any(ch.isalpha() for ch in t)]

        if not alpha_tokens:
            dropped += 1
            print(f"  FILTERED {institution or '?'} — empty or invalid institution label")
            continue

        contains_company_hint = any(t in COMPANY_HINT_TOKENS for t in alpha_tokens)
        contains_generic_noun = any(t in GENERIC_INSTITUTION_NOUNS for t in alpha_tokens)
        reduced = [
            t
            for t in alpha_tokens
            if t not in GENERIC_INSTITUTION_NOUNS and t not in INSTITUTION_FILLER_WORDS
        ]

        # If the label is only geography/filler/generic nouns, it is not a company.
        if not reduced:
            dropped += 1
            print(f"  FILTERED {institution} — generic institution label, not a company name")
            continue

        # Short generic labels like "UK Businesses" or "European Enterprises".
        if contains_generic_noun and not contains_company_hint and len(reduced) <= 2:
            dropped += 1
            print(f"  FILTERED {institution} — generic group label, not a specific company")
            continue

        kept.append(sig)

    print(
        f"  COMPANY-NAME FILTER: kept {len(kept)}/{len(signals)} (dropped {dropped})"
    )
    return kept


def build_queries_from_profile(profile_dict: dict | None) -> list[str]:
    if not profile_dict:
        return SEARCH_QUERIES

    regions = profile_dict.get("regions") or ["Eastern Europe", "Middle East"]
    countries = profile_dict.get("countries") or []
    domains = profile_dict.get("domains") or ["ai_transformation"]
    objective = profile_dict.get("objective", "digital transformation buying signals")
    time_window_days = int(profile_dict.get("time_window_days", 90))
    year = datetime.now().year

    geos = countries if countries else regions
    queries: list[str] = []
    for geo in geos[:10]:
        for domain in domains[:8]:
            hint = DOMAIN_QUERY_HINTS.get(domain, domain.replace("_", " "))
            queries.append(f"{geo} {hint} {objective} {year}")
            queries.append(f"{geo} {hint} institutional adoption last {time_window_days} days")

    deduped: list[str] = []
    seen = set()
    for q in queries:
        norm = q.lower().strip()
        if norm not in seen:
            seen.add(norm)
            deduped.append(q)

    return deduped[:50] if deduped else SEARCH_QUERIES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run signal scout searches and extraction.")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Optional pipeline profile JSON file.",
    )
    return parser.parse_args()


def parse_signals_from_agent_text(result_text: str) -> list[dict]:
    """Parse scout agent output and return list of signal objects."""
    text = str(result_text).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = parsed.get("signals", parsed.get("results", []))
    return parsed if isinstance(parsed, list) else []


def _normalize_domain(domain: str) -> str:
    normalized = (domain or "").strip().lower().replace("-", "_")
    normalized = normalized.replace("/", "_").replace("  ", " ")
    return _AI_DOMAIN_SYNONYMS.get(normalized, normalized)


def rebalance_ai_focus(
    signals: list[dict], target_ratio: float = 0.5
) -> list[dict]:
    """Ensure at least target_ratio of signals are AI-focused domains.

    Strategy:
    1) Normalize known AI domain aliases.
    2) Promote non-AI domains to ai_implementation when summary clearly
       indicates implementation/automation work.
    """
    if not signals:
        return signals

    for sig in signals:
        sig["domain"] = _normalize_domain(sig.get("domain", ""))

    ai_count = sum(1 for s in signals if s.get("domain") in _AI_PRIORITY_DOMAINS)
    target_count = max(1, int(round(len(signals) * target_ratio)))
    if ai_count >= target_count:
        print(
            f"  AI MIX: {ai_count}/{len(signals)} already AI-focused "
            f"(target >= {target_count})"
        )
        return signals

    promoted = 0
    for sig in signals:
        if ai_count >= target_count:
            break
        if sig.get("domain") in _AI_PRIORITY_DOMAINS:
            continue

        text = (
            f"{sig.get('summary', '')} "
            f"{sig.get('regional_keyword_match', '')} "
            f"{sig.get('signal_type', '')}"
        ).lower()
        if any(kw in text for kw in _AI_HINT_KEYWORDS):
            sig["domain"] = "ai_implementation"
            ai_count += 1
            promoted += 1

    print(
        f"  AI MIX: {ai_count}/{len(signals)} AI-focused "
        f"(promoted {promoted}, target >= {target_count})"
    )
    return signals


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    profile = None
    profile_json_str = ""
    if args.profile:
        try:
            loaded_profile = load_profile(args.profile)
            profile = loaded_profile.model_dump()
            profile_json_str = json.dumps(profile, indent=2)
            print(f"Loaded profile: {args.profile}")
        except Exception as exc:
            print(f"WARNING: failed to load profile '{args.profile}': {exc}")

    active_queries = build_queries_from_profile(profile)
    min_count, max_count, recency_days, dedupe_policy = resolve_profile_targets(profile)

    # 1. Run all searches programmatically
    print("=" * 60)
    print("PHASE 1: Running Tavily searches")
    print("=" * 60)
    all_search_results = run_searches(active_queries)
    print(f"\nCollected {len(all_search_results)} unique search results\n")

    # 2. Run the analyst agent with pre-fetched results
    print("=" * 60)
    print("PHASE 2: Analysing search results with CrewAI agent")
    print("=" * 60)
    agent = build_scout_agent()
    task = build_scout_task(agent, all_search_results, profile_context=profile_json_str)
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    result = crew.kickoff()

    # 3. Parse agent output
    result_text = str(result).strip()
    try:
        parsed_signals = parse_signals_from_agent_text(result_text)
    except Exception:
        print("\nWARNING: Could not parse agent output as JSON.")
        print("Saving raw output for debugging.\n")
        parsed_signals = []

    # Retry if model under-produces relative to configured minimum
    if len(parsed_signals) < min_count:
        for retry_idx in range(1, 3):
            print(
                f"\nWARNING: Scout returned {len(parsed_signals)} signals "
                f"(target min {min_count}). Retry {retry_idx}/2..."
            )
            retry_task = Task(
                description=(
                    task.description
                    + "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                    + f"You previously returned {len(parsed_signals)} signals.\n"
                    + f"Re-scan ALL search results and return at least {min_count} "
                    + "valid signal objects if possible.\n"
                    + "Do not stop early."
                ),
                expected_output=task.expected_output,
                agent=agent,
            )
            retry_crew = Crew(agents=[agent], tasks=[retry_task], verbose=True)
            retry_result = retry_crew.kickoff()
            retry_text = str(retry_result).strip()
            try:
                retry_parsed = parse_signals_from_agent_text(retry_text)
            except Exception:
                retry_parsed = []
            if len(retry_parsed) > len(parsed_signals):
                parsed_signals = retry_parsed
                result_text = retry_text
            if len(parsed_signals) >= min_count:
                break

    # 4. Validate URLs against actual search results
    print("\n" + "=" * 60)
    print("PHASE 3: Validating URLs")
    print("=" * 60)
    agent_count = len(parsed_signals)
    validated_signals = validate_signals(parsed_signals, all_search_results)

    print(
        f"\n  Agent found {agent_count} signals, "
        f"{len(validated_signals)} have verified URLs"
    )

    # 5. Filter Tier 1 institutions, Big Tech, and Top Consultancies
    print("\n" + "=" * 60)
    print("PHASE 4: Filtering Tier 1 / Big Tech / Top Consultancy institutions")
    print("=" * 60)
    pre_tier1_count = len(validated_signals)
    validated_signals = filter_tier1(validated_signals)
    print(
        f"  Kept {len(validated_signals)}/{pre_tier1_count} signals "
        f"after Tier 1 filter"
    )

    # 5a. Filter primary crypto / NFT / Web3 companies
    print("\n" + "=" * 60)
    print("PHASE 4b: Filtering primary Crypto/NFT/Web3 companies")
    print("=" * 60)
    pre_crypto_count = len(validated_signals)
    validated_signals = filter_crypto(validated_signals)
    print(
        f"  Kept {len(validated_signals)}/{pre_crypto_count} signals "
        f"after crypto/NFT/Web3 filter"
    )

    # 5b. Filter AI-native model/platform vendors
    print("\n" + "=" * 60)
    print("PHASE 4c: Filtering AI-native companies")
    print("=" * 60)
    pre_ai_native_count = len(validated_signals)
    validated_signals = filter_ai_native_companies(validated_signals)
    print(
        f"  Kept {len(validated_signals)}/{pre_ai_native_count} signals "
        f"after AI-native company filter"
    )

    # 5. Filter signals older than configured time window
    print("\n" + "=" * 60)
    print(f"PHASE 5: Filtering signals older than {recency_days} days")
    print("=" * 60)
    pre_recency_count = len(validated_signals)
    validated_signals = filter_old_signals(validated_signals, cutoff_days=recency_days)
    print(
        f"  Kept {len(validated_signals)}/{pre_recency_count} signals "
        f"after recency filter"
    )

    # 6. Apply dedupe policy
    print("\n" + "=" * 60)
    print("PHASE 6: Applying dedupe policy")
    print("=" * 60)
    validated_signals = apply_dedupe_policy(
        validated_signals, dedupe_policy=dedupe_policy, min_count=min_count
    )

    # 7. Normalize and rebalance domains so ~50% are AI-focused signals
    print("\n" + "=" * 60)
    print("PHASE 7: Rebalancing AI-focused domains")
    print("=" * 60)
    validated_signals = rebalance_ai_focus(validated_signals, target_ratio=0.5)

    # 8. Enrich country/region fields for each signal
    print("\n" + "=" * 60)
    print("PHASE 8: Enriching country and region fields")
    print("=" * 60)
    validated_signals = enrich_geo_fields(validated_signals, all_search_results)

    # 9. Keep only company institutions
    print("\n" + "=" * 60)
    print("PHASE 9: Filtering non-company institutions")
    print("=" * 60)
    validated_signals = filter_non_company_institutions(validated_signals)

    # 10. Remove generic institution labels (must be concrete company names)
    print("\n" + "=" * 60)
    print("PHASE 10: Filtering generic institution labels")
    print("=" * 60)
    validated_signals = filter_generic_institution_labels(validated_signals)

    # 11. Enforce target output count window (20-25)
    print("\n" + "=" * 60)
    print("PHASE 11: Enforcing output size window")
    print("=" * 60)
    validated_signals = enforce_output_window(
        validated_signals, min_count=min_count, max_count=max_count
    )

    # 12. Save report
    OUTPUTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUTS_DIR / f"signal_report_{timestamp}.json"

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "search_queries_used": active_queries,
        "total_search_results": len(all_search_results),
        "agent_signals_returned": agent_count,
        "validated_signals_count": len(validated_signals),
        "signals": validated_signals,
    }
    if profile:
        report_data["profile"] = profile

    # Include raw output for debugging if parsing failed
    if not parsed_signals:
        report_data["raw_output"] = str(result)

    with open(output_file, "w") as f:
        json.dump(report_data, f, indent=2)

    # 12. Print summary
    print("\n" + "=" * 60)
    print("SIGNAL SCOUT REPORT")
    print("=" * 60)
    print(f"  Queries run:       {len(active_queries)}")
    print(f"  Search results:    {len(all_search_results)}")
    print(f"  Agent signals:     {agent_count}")
    print(f"  Validated signals: {len(validated_signals)}")
    print("-" * 60)
    for i, sig in enumerate(validated_signals, 1):
        name = sig.get("institution", "Unknown")
        region = sig.get("region", "?")
        stype = sig.get("signal_type", "?")
        url = sig.get("source_url", "?")
        print(f"  {i}. [{region}] {name} — {stype}")
        print(f"     {url}")
    print("=" * 60)
    print(f"\nReport saved to {output_file}")
