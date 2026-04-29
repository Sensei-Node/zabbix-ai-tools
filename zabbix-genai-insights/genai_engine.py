"""
Core analysis engine for Zabbix GenAI Insights.

Shared between the standalone CLI script (genai_alert.py) and the
Dockerized FastAPI service (docker/app.py).
"""

import os
import json
from collections import Counter
from datetime import datetime

import siem_fetching
from llm_provider import get_provider

# ---------------------------------------------------------------------------
# Default structured prompt — chain-of-thought for consistent, actionable output
# ---------------------------------------------------------------------------

DEFAULT_PROMPT = """You are a senior infrastructure and observability analyst.
You will receive a Zabbix alert event and, optionally, correlated SIEM logs.

Analyze the data following this structure:
1. **Summary**: One-line description of the incident.
2. **Root Cause Analysis**: What likely caused this alert based on the data.
3. **Severity Assessment**: Rate as Critical / High / Medium / Low with justification.
4. **Correlated Evidence**: If SIEM logs are present, highlight the most relevant entries.
5. **Recommended Actions**: Numbered list of concrete steps to resolve or mitigate.
6. **Prevention**: What can be done to prevent recurrence.

Be concise and technical. Prioritize actionable information."""


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

def build_structured_context(event_data: dict, siem_logs: str = "") -> str:
    """
    Build a well-organized context string from raw Zabbix event data and
    optional SIEM logs so the LLM receives structured input instead of a
    raw JSON blob.
    """
    sections: list[str] = []

    # Extract key Zabbix fields (case-insensitive fallback)
    key_fields = {
        "Host": event_data.get("HOST") or event_data.get("host"),
        "Trigger": event_data.get("TRIGGER_NAME") or event_data.get("trigger_name"),
        "Severity": event_data.get("TRIGGER_SEVERITY") or event_data.get("severity"),
        "Status": event_data.get("TRIGGER_STATUS") or event_data.get("status"),
        "Event ID": event_data.get("EVENT_ID") or event_data.get("event_id"),
        "Item Value": event_data.get("ITEM_VALUE") or event_data.get("item_value"),
        "Item Name": event_data.get("ITEM_NAME") or event_data.get("item_name"),
        "Event Time": event_data.get("EVENT_DATE") or event_data.get("event_date"),
        "Operational Data": event_data.get("EVENT_OPDATA") or event_data.get("opdata"),
    }

    sections.append("## Zabbix Alert Details")
    for label, value in key_fields.items():
        if value:
            sections.append(f"- **{label}**: {value}")

    # Full payload for additional context the model might need
    sections.append(
        f"\n## Full Event Payload\n```json\n"
        f"{json.dumps(event_data, indent=2, ensure_ascii=False)}\n```"
    )

    if siem_logs:
        sections.append(f"\n## Correlated SIEM Logs (Graylog)\n{siem_logs}")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_alert(
    event_data: dict,
    google_api_key: str = None,
    model_name: str = None,
    custom_prompt: str = None,
    graylog_enabled: bool = False,
) -> dict:
    """
    Core analysis entry-point shared between standalone script and Docker API.

    Parameters
    ----------
    event_data : dict
        The alert payload from Zabbix.
    google_api_key : str, optional
        Legacy parameter kept for backward compatibility.  The provider layer
        reads its own env vars; this is only used as a last-resort fallback
        for the Gemini provider.
    model_name : str, optional
        Legacy parameter — prefer ``LLM_MODEL`` env var.
    custom_prompt : str, optional
        If provided, replaces the default structured prompt.
    graylog_enabled : bool
        Whether to fetch SIEM enrichment logs from Graylog.

    Returns
    -------
    dict
        ``{"insight": str, "siem_logs": str, "model": str}`` on success, or
        ``{"error": str}`` on failure.
    """

    # --- Backward-compat: inject legacy key into env if not already set ---
    if google_api_key and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = google_api_key

    # --- Resolve LLM provider ---
    try:
        provider = get_provider()
    except Exception as exc:
        return {"error": f"LLM provider initialization failed: {exc}"}

    # --- 1. SIEM Enrichment ---
    siem_logs = ""
    if graylog_enabled:
        host_raw = event_data.get("HOST") or event_data.get("host")
        if host_raw:
            siem_logs = siem_fetching.search_graylog(host_raw)

    # --- 2. Build prompt ---
    selected_prompt = custom_prompt if custom_prompt else DEFAULT_PROMPT
    context = build_structured_context(event_data, siem_logs)
    prompt = f"{selected_prompt}\n\n{context}"

    # --- 3. Call LLM ---
    try:
        response_text = provider.generate(prompt)
        return {
            "insight": response_text,
            "siem_logs": siem_logs,
            "model": provider.name(),
        }
    except Exception as exc:
        return {"error": f"Error calling {provider.name()}: {exc}"}
