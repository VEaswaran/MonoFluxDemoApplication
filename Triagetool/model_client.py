"""
services/model_client.py
Sends ELK data to your refinement model API and returns root cause analysis.
"""

import aiohttp
import asyncio
from config.settings import Settings


class ModelClient:
    """
    Adapter for your external refinement model.
    Adjust the request/response schema to match your model's API contract.
    """

    def __init__(self, settings: Settings):
        self.api_url = settings.MODEL_API_URL
        self.api_key = settings.MODEL_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=settings.MODEL_TIMEOUT)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def analyze(self, formatted_log_data: str, answers: dict) -> dict:
        """
        Send log data to your model and return root cause analysis.

        Expected model response format (adjust to your model's output):
        {
          "root_cause": "...",
          "confidence": 0.87,
          "contributing_factors": ["...", "..."],
          "affected_components": ["...", "..."],
          "recommended_actions": ["...", "..."],
          "severity": "critical|high|medium|low",
          "summary": "..."
        }

        Returns a normalized dict with the above keys.
        """
        payload = {
            "task": "root_cause_analysis",
            "context": {
                "service": answers.get("service_name"),
                "environment": answers.get("environment"),
                "time_range": answers.get("time_range"),
                "error_keyword": answers.get("error_keyword"),
                "trace_id": answers.get("trace_id"),
                "user_id": answers.get("user_id"),
            },
            "log_data": formatted_log_data,
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.api_url,
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    body = await resp.json()

                    if resp.status != 200:
                        return {
                            "error": f"Model API returned HTTP {resp.status}: {body}",
                            "raw": body,
                        }

                    return self._normalize(body)

        except asyncio.TimeoutError:
            return {"error": "Model API timed out. Try again or check model service health."}
        except Exception as e:
            return {"error": f"Model API error: {str(e)}"}

    def _normalize(self, raw: dict) -> dict:
        """Normalize model response to a consistent shape."""
        return {
            "root_cause": raw.get("root_cause") or raw.get("cause") or "Could not determine root cause.",
            "confidence": raw.get("confidence") or raw.get("score"),
            "contributing_factors": raw.get("contributing_factors") or raw.get("factors") or [],
            "affected_components": raw.get("affected_components") or raw.get("components") or [],
            "recommended_actions": raw.get("recommended_actions") or raw.get("actions") or [],
            "severity": raw.get("severity") or "unknown",
            "summary": raw.get("summary") or "",
            "error": None,
        }

    def format_rca_report(self, rca: dict, answers: dict) -> str:
        """
        Render the root cause analysis as a clean Teams-friendly markdown message.
        """
        if rca.get("error"):
            return f"❌ **Model Error**\n\n{rca['error']}"

        severity_emoji = {
            "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
        }.get(rca.get("severity", "").lower(), "⚪")

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🧠 **Root Cause Analysis Report**",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"**Service:** `{answers.get('service_name', 'N/A')}`  |  "
            f"**Env:** `{answers.get('environment', 'N/A')}`  |  "
            f"**Severity:** {severity_emoji} `{rca.get('severity', 'N/A').upper()}`",
        ]

        if rca.get("confidence") is not None:
            conf_pct = int(float(rca["confidence"]) * 100)
            lines.append(f"**Confidence:** {conf_pct}%")

        lines += ["", "---", "### 🔍 Root Cause", f"> {rca['root_cause']}"]

        if rca.get("summary"):
            lines += ["", "### 📋 Summary", rca["summary"]]

        if rca.get("contributing_factors"):
            lines += ["", "### ⚙️ Contributing Factors"]
            for f in rca["contributing_factors"]:
                lines.append(f"- {f}")

        if rca.get("affected_components"):
            lines += ["", "### 🗂️ Affected Components"]
            for c in rca["affected_components"]:
                lines.append(f"- `{c}`")

        if rca.get("recommended_actions"):
            lines += ["", "### ✅ Recommended Actions"]
            for i, action in enumerate(rca["recommended_actions"], 1):
                lines.append(f"{i}. {action}")

        lines += [
            "",
            "---",
            f"🔎 *Trace ID: `{answers.get('trace_id') or 'N/A'}`*  |  "
            f"*Time Range: `{answers.get('time_range', 'N/A')}`*",
            "",
            "💬 *Type `restart` to triage another issue.*",
        ]

        return "\n".join(lines)
