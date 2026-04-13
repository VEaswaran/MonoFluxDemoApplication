"""
config/questions.py — Pre-defined triage question template
Each question has a key, prompt text, optional validator, and skip flag.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class TriageQuestion:
    key: str                              # maps to session answer dict
    prompt: str                           # message sent to user
    hint: str = ""                        # shown as sub-text hint
    skippable: bool = False               # user can type 'skip'
    validator: Optional[Callable] = None  # optional answer validator


def _validate_time_range(value: str) -> bool:
    """Accept formats like: 1h, 24h, 2d, or ISO datetime range."""
    import re
    return bool(re.match(r"^\d+[mhd]$", value.strip().lower())) or "to" in value or value.lower() == "skip"


# ── Question Template (order matters — collected step by step) ────────────────

TRIAGE_QUESTIONS: list[TriageQuestion] = [
    TriageQuestion(
        key="service_name",
        prompt="🛠️ **Step 1/6 — Service Name**\n\nWhich service or application is affected?\n*(e.g. `auth-service`, `payment-api`, `user-portal`)*",
        hint="Enter the exact service name as it appears in your logs.",
    ),
    TriageQuestion(
        key="environment",
        prompt="🌍 **Step 2/6 — Environment**\n\nWhich environment is this occurring in?\n*(Reply with: `prod`, `staging`, or `dev`)*",
        hint="Type the environment name.",
        validator=lambda v: v.strip().lower() in {"prod", "staging", "dev", "production", "development"},
    ),
    TriageQuestion(
        key="time_range",
        prompt="🕐 **Step 3/6 — Time Range**\n\nWhat time window should I search?\n*(e.g. `1h`, `6h`, `24h`, `2d` — or a range like `2024-01-10T08:00 to 2024-01-10T10:00`)*",
        hint="Use shorthand like `1h` for last 1 hour, `2d` for last 2 days.",
        validator=_validate_time_range,
    ),
    TriageQuestion(
        key="error_keyword",
        prompt="🔍 **Step 4/6 — Error Keyword**\n\nWhat error message, exception, or keyword should I search for?\n*(e.g. `NullPointerException`, `timeout`, `403 Forbidden`)*",
        hint="Paste the error text or a key term from the logs.",
    ),
    TriageQuestion(
        key="trace_id",
        prompt="🔗 **Step 5/6 — Trace ID**\n\nDo you have a specific Trace ID to narrow the search?\n*(Paste the trace ID, or type `skip` to search broadly)*",
        hint="Trace IDs help pinpoint exact request chains in distributed systems.",
        skippable=True,
    ),
    TriageQuestion(
        key="user_id",
        prompt="👤 **Step 6/6 — User / Team**\n\nIs this affecting a specific user ID or team?\n*(Paste user ID or team name, or type `skip` to search all users)*",
        hint="Leave blank to search across all users.",
        skippable=True,
    ),
]

TOTAL_STEPS = len(TRIAGE_QUESTIONS)
