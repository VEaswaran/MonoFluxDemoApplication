"""
services/elk_client.py
Builds Elasticsearch queries from session answers and fetches raw logs.
"""

import re
import json
import asyncio
import aiohttp
from typing import Optional
from config.settings import Settings


def _parse_time_range(raw: str) -> dict:
    """
    Converts user-supplied time range into Elasticsearch range filter.
    Supports:
      - Shorthand: 1h, 6h, 24h, 2d, 30m
      - ISO range: "2024-01-10T08:00 to 2024-01-10T10:00"
    """
    raw = raw.strip().lower()

    # ISO range: "YYYY-MM-DDTHH:MM to YYYY-MM-DDTHH:MM"
    if " to " in raw:
        parts = raw.split(" to ")
        return {"gte": parts[0].strip(), "lte": parts[1].strip()}

    # Shorthand: 1h / 2d / 30m
    if re.match(r"^\d+[mhd]$", raw):
        return {"gte": f"now-{raw}", "lte": "now"}

    # Default fallback — last 1 hour
    return {"gte": "now-1h", "lte": "now"}


def build_elk_query(answers: dict) -> dict:
    """Construct a bool query from triage answers."""
    must_clauses = []
    filter_clauses = []

    if answers.get("service_name"):
        must_clauses.append({"match": {"service.name": answers["service_name"]}})

    if answers.get("environment"):
        env = answers["environment"].lower()
        if env == "production":
            env = "prod"
        must_clauses.append({"term": {"environment": env}})

    if answers.get("error_keyword"):
        must_clauses.append({
            "multi_match": {
                "query": answers["error_keyword"],
                "fields": ["message", "error.message", "log.message", "exception"],
                "type": "best_fields",
            }
        })

    if answers.get("trace_id"):
        must_clauses.append({
            "term": {"trace.id": answers["trace_id"]}
        })

    if answers.get("user_id"):
        must_clauses.append({
            "bool": {
                "should": [
                    {"term": {"user.id": answers["user_id"]}},
                    {"term": {"team": answers["user_id"]}},
                ],
                "minimum_should_match": 1,
            }
        })

    # Time range filter
    time_range = _parse_time_range(answers.get("time_range", "1h"))
    filter_clauses.append({"range": {"@timestamp": time_range}})

    return {
        "query": {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}],
                "filter": filter_clauses,
            }
        },
        "size": 100,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": [
            "@timestamp", "message", "error.message", "exception",
            "service.name", "environment", "trace.id",
            "user.id", "team", "log.level", "host.name",
            "http.request.method", "http.response.status_code", "url.path",
        ],
    }


class ELKClient:
    def __init__(self, settings: Settings):
        self.host = settings.ELK_HOST.rstrip("/")
        self.index = settings.ELK_INDEX
        self.api_key = settings.ELK_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=settings.ELK_TIMEOUT)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"ApiKey {self.api_key}",
        }

    async def search(self, answers: dict) -> dict:
        """
        Execute ELK search and return structured result:
        {
          "total": int,
          "hits": [...],    # raw log entries
          "query": {...},   # the query used (for debugging)
          "error": str|None
        }
        """
        query = build_elk_query(answers)
        url = f"{self.host}/{self.index}/_search"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, headers=self._headers(), json=query) as resp:
                    body = await resp.json()

                    if resp.status != 200:
                        error_reason = body.get("error", {}).get("reason", f"HTTP {resp.status}")
                        return {"total": 0, "hits": [], "query": query, "error": error_reason}

                    hits = body.get("hits", {})
                    total = hits.get("total", {}).get("value", 0)
                    raw_hits = [h["_source"] for h in hits.get("hits", [])]

                    return {"total": total, "hits": raw_hits, "query": query, "error": None}

        except asyncio.TimeoutError:
            return {"total": 0, "hits": [], "query": query, "error": "ELK query timed out."}
        except Exception as e:
            return {"total": 0, "hits": [], "query": query, "error": str(e)}

    def format_for_model(self, elk_result: dict, answers: dict) -> str:
        """
        Serialize ELK results + triage context into a string
        suitable for passing to the refinement model.
        """
        context_lines = [
            "=== TRIAGE CONTEXT ===",
            f"Service     : {answers.get('service_name', 'N/A')}",
            f"Environment : {answers.get('environment', 'N/A')}",
            f"Time Range  : {answers.get('time_range', 'N/A')}",
            f"Error Search: {answers.get('error_keyword', 'N/A')}",
            f"Trace ID    : {answers.get('trace_id') or 'Not provided'}",
            f"User / Team : {answers.get('user_id') or 'Not provided'}",
            f"Total Logs  : {elk_result['total']}",
            "",
            "=== RAW LOG ENTRIES (most recent first) ===",
        ]

        for i, hit in enumerate(elk_result["hits"][:50], 1):
            context_lines.append(f"\n--- Log #{i} ---")
            context_lines.append(json.dumps(hit, indent=2, default=str))

        return "\n".join(context_lines)
