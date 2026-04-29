"""
Core analysis engine for Zabbix GenAI Insights.

Shared between the standalone CLI script (genai_alert.py) and the
Dockerized FastAPI service (docker/app.py).

Supports contextual memory: when running inside Docker (with db.py available),
the engine queries historical insights for the same host and recent global
alerts, injecting them into the prompt so the LLM can detect recurring
patterns, escalate severity, and correlate cross-host failures.
"""

import os
import json
from collections import Counter
from datetime import datetime

import siem_fetching
import mcp_fetching
from llm_provider import get_provider

# ---------------------------------------------------------------------------
# Default structured prompt — chain-of-thought for consistent, actionable output
# ---------------------------------------------------------------------------

DEFAULT_PROMPT = """You are a senior infrastructure and observability analyst.
You will receive a Zabbix alert event and, optionally, correlated SIEM logs
and historical context from previous alerts.

Analyze the data following this structure:
1. **Summary**: One-line description of the incident.
2. **Root Cause Analysis**: What likely caused this alert based on the data.
3. **Severity Assessment**: Rate as Critical / High / Medium / Low with justification.
   - If this host has had recent similar alerts, factor recurrence into the severity.
   - If multiple hosts are alerting simultaneously, consider systemic failure.
4. **Correlated Evidence**: If SIEM logs are present, highlight the most relevant entries.
5. **Historical Pattern**: If previous insights are provided, describe the pattern
   (recurring issue, escalation, new problem, etc.).
6. **Recommended Actions**: Numbered list of concrete steps to resolve or mitigate.
7. **Prevention**: What can be done to prevent recurrence.

Be concise and technical. Prioritize actionable information."""


# ---------------------------------------------------------------------------
# Memory / historical context
# ---------------------------------------------------------------------------

def _try_get_host_history(hostname: str) -> list[dict]:
    """
    Attempt to fetch recent insights for a host from the DB.
    Returns an empty list when running outside Docker (no db module).
    """
    try:
        import db
        return db.get_recent_insights_for_host(hostname, limit=5)
    except Exception:
        return []


def _try_get_global_history(minutes: int = 60) -> list[dict]:
    """
    Attempt to fetch recent global insights from the DB.
    Returns an empty list when running outside Docker (no db module).
    """
    try:
        import db
        return db.get_recent_insights_global(minutes=minutes, limit=10)
    except Exception:
        return []


def build_historical_context(
    hostname: str,
    current_event_id: str = None,
) -> str:
    """
    Build a historical context section for the prompt by querying the
    insights database.

    Includes:
    - Recent alerts for the same host (recurrence detection)
    - Recent alerts across all hosts (cross-host correlation)

    Returns an empty string when no history is available (e.g. standalone mode).
    """
    sections: list[str] = []

    # --- Host-specific history ---
    host_history = _try_get_host_history(hostname)
    # Exclude the current event from history (it may already be PENDING in DB)
    if current_event_id:
        host_history = [h for h in host_history if h["event_id"] != current_event_id]

    if host_history:
        sections.append("## Historical Alerts for This Host")
        sections.append(
            f"The following {len(host_history)} recent alert(s) were found "
            f"for host `{hostname}`:"
        )
        for entry in host_history:
            sections.append(
                f"- **[{entry['created_at']}]** Trigger: {entry['trigger']} | "
                f"Severity: {entry['severity']}\n"
                f"  Insight excerpt: {entry['insight_summary']}"
            )

    # --- Global recent alerts (cross-host correlation) ---
    global_history = _try_get_global_history(minutes=60)
    # Exclude current event and same-host entries (already shown above)
    if current_event_id:
        global_history = [g for g in global_history if g["event_id"] != current_event_id]
    other_hosts = [g for g in global_history if g["host"].split("_")[0] != hostname]

    if other_hosts:
        sections.append("\n## Recent Alerts on Other Hosts (last 60 min)")
        sections.append(
            "These concurrent alerts may indicate a systemic or network-level issue:"
        )
        for entry in other_hosts[:7]:
            sections.append(
                f"- **[{entry['created_at']}]** Host: `{entry['host']}` | "
                f"Trigger: {entry['trigger']} | Severity: {entry['severity']}"
            )

    return "\n".join(sections) if sections else ""


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

def build_structured_context(
    event_data: dict,
    siem_logs: str = "",
    historical_context: str = "",
    mcp_context: str = "",
) -> str:
    """
    Build a well-organized context string from raw Zabbix event data,
    optional SIEM logs, optional historical context, and optional MCP
    enrichment so the LLM receives structured input instead of a raw
    JSON blob.
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

    # MCP enrichment (live Zabbix data)
    if mcp_context:
        sections.append(f"\n{mcp_context}")

    # Historical context (memory)
    if historical_context:
        sections.append(f"\n{historical_context}")

    # SIEM logs
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
    mcp_enabled: bool = False,
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
    mcp_enabled : bool
        Whether to fetch live Zabbix context from the MCP Server.

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

    # --- Extract host info ---
    host_raw = event_data.get("HOST") or event_data.get("host") or ""
    hostname = host_raw.split("_")[0] if host_raw else "unknown"
    event_id = (
        event_data.get("EVENT_ID")
        or event_data.get("event_id")
        or event_data.get("id")
    )

    # --- 1. SIEM Enrichment ---
    siem_logs = ""
    if graylog_enabled and host_raw:
        siem_logs = siem_fetching.search_graylog(host_raw)

    # --- 2. MCP Enrichment (live Zabbix data) ---
    mcp_context = ""
    if mcp_enabled and hostname != "unknown":
        mcp_context = mcp_fetching.enrich_from_mcp(hostname)

    # --- 3. Historical context (memory) ---
    historical_context = build_historical_context(hostname, current_event_id=event_id)

    # --- 4. Build prompt ---
    selected_prompt = custom_prompt if custom_prompt else DEFAULT_PROMPT
    context = build_structured_context(
        event_data, siem_logs, historical_context, mcp_context
    )
    prompt = f"{selected_prompt}\n\n{context}"

    # --- 5. Call LLM ---
    try:
        response_text = provider.generate(prompt)
        return {
            "insight": response_text,
            "siem_logs": siem_logs,
            "model": provider.name(),
            "historical_context_used": bool(historical_context),
            "mcp_context_used": bool(mcp_context),
        }
    except Exception as exc:
        return {"error": f"Error calling {provider.name()}: {exc}"}
