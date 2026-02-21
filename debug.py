"""
debug.py — Query tensr.db and print a formatted diagnostic report to stdout.

Usage:
    python debug.py
"""

import sys
from pathlib import Path

# Ensure project root is on the path so 'database' imports cleanly
sys.path.insert(0, str(Path(__file__).parent))

import database


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _trunc(s: str | None, width: int) -> str:
    """Truncate and left-pad a string to exactly `width` chars."""
    text = (s or "—")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def _fmt_int(v) -> str:
    return str(int(v)) if v is not None else "—"


def _fmt_float(v) -> str:
    return f"{float(v):.0f}" if v is not None else "—"


def _tier_color(tier: str | None) -> str:
    """Return ANSI-coloured tier label (degrades gracefully if not a tty)."""
    if not sys.stdout.isatty():
        return (tier or "—").ljust(7)
    colours = {
        "HOT": "\033[91m",     # bright red
        "WARM": "\033[93m",    # yellow
        "NURTURE": "\033[96m", # cyan
        "HOLD": "\033[90m",    # dark grey
    }
    reset = "\033[0m"
    t = (tier or "—").upper()
    colour = colours.get(t, "")
    return f"{colour}{t.ljust(7)}{reset}"


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def print_header(summary: dict) -> None:
    ts = summary.get("timestamp") or "unknown"
    total = summary.get("total", 0)
    hot = summary.get("HOT", 0)
    warm = summary.get("WARM", 0)
    nurture = summary.get("NURTURE", 0)
    hold = summary.get("HOLD", 0)

    print("=" * 100)
    print("  TENSR SIGNAL AGENT — DEBUG REPORT")
    print("=" * 100)
    print(f"  Run timestamp : {ts}")
    print(f"  Total signals : {total}")
    print(f"  HOT           : {hot}")
    print(f"  WARM          : {warm}")
    print(f"  NURTURE       : {nurture}")
    print(f"  HOLD          : {hold}")
    print("=" * 100)


def print_signal_table(signals: list) -> None:
    # Column widths
    W_INST  = 30
    W_TIER  = 10  # institution_tier
    W_SCORE =  6
    W_PRI   =  9  # priority_tier
    W_ACT   =  4
    W_SEN   =  4
    W_DOM   =  4
    W_REC   =  4
    W_DATE  = 12
    W_FLAGS =  5

    header = (
        f"{'INSTITUTION':<{W_INST}} "
        f"{'TIER':<{W_TIER}} "
        f"{'SCORE':>{W_SCORE}} "
        f"{'PRIORITY':<{W_PRI}} "
        f"{'ACT':>{W_ACT}} "
        f"{'SEN':>{W_SEN}} "
        f"{'DOM':>{W_DOM}} "
        f"{'REC':>{W_REC}} "
        f"{'SIGNAL DATE':<{W_DATE}} "
        f"FLAGS"
    )
    separator = "-" * len(header)

    print()
    print("  SIGNAL TABLE (sorted by score descending)")
    print()
    print("  " + header)
    print("  " + separator)

    for row in signals:
        inst         = _trunc(row["institution"], W_INST)
        tier         = _trunc(row["institution_tier"], W_TIER)
        score        = _fmt_float(row["total_score"]).rjust(W_SCORE)
        priority     = _trunc(row["priority_tier"], W_PRI)
        action_pts   = _fmt_int(row["action_pts"]).rjust(W_ACT)
        seniority_pts = _fmt_int(row["seniority_pts"]).rjust(W_SEN)
        domain_pts   = _fmt_int(row["domain_pts"]).rjust(W_DOM)
        recency_pts  = _fmt_int(row["recency_pts"]).rjust(W_REC)
        signal_date  = _trunc(row["signal_date"], W_DATE)

        # Flags
        flags = []
        if row["seniority_inferred"]:
            flags.append("*")      # seniority was inferred
        if row["recency_pts"] == 0:
            flags.append("?")      # undated / zero recency
        flag_str = " ".join(flags) if flags else ""

        line = (
            f"{inst} "
            f"{tier} "
            f"{score} "
            f"{priority} "
            f"{action_pts} "
            f"{seniority_pts} "
            f"{domain_pts} "
            f"{recency_pts} "
            f"{signal_date} "
            f"{flag_str}"
        )
        print("  " + line)

    print("  " + separator)
    print()
    print("  Flags:  * = seniority_inferred    ? = recency_pts == 0 (undated signal)")
    print()


def print_score_distribution(signals: list) -> None:
    """Print a count of signals per 10-point bucket (0–10, 10–20, …, 90–100)."""
    buckets = {i: 0 for i in range(0, 100, 10)}  # 0,10,20,...,90

    for row in signals:
        score = row["total_score"]
        if score is None:
            continue
        score = float(score)
        # Clamp to [0, 100]
        score = max(0.0, min(100.0, score))
        bucket = int(score // 10) * 10
        if bucket == 100:
            bucket = 90  # 100 falls into the 90-100 bucket
        buckets[bucket] += 1

    print("  SCORE DISTRIBUTION")
    print()
    max_count = max(buckets.values()) if any(buckets.values()) else 1
    bar_max = 30  # max bar width

    for low, count in sorted(buckets.items()):
        high = low + 10
        label = f"  {low:>3}–{high:<3}"
        bar_len = int((count / max_count) * bar_max) if max_count else 0
        bar = "█" * bar_len
        print(f"{label}  {bar:<{bar_max}}  {count}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    summary = database.get_summary()

    if summary["run_id"] is None:
        print("No runs found in tensr.db. Run the pipeline first.")
        return

    signals = database.get_latest_run()

    print_header(summary)
    print_signal_table(signals)
    print("=" * 100)
    print_score_distribution(signals)
    print("=" * 100)


if __name__ == "__main__":
    main()
