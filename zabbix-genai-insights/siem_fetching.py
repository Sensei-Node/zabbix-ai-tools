"""
SIEM (Graylog) log fetching and enrichment module.

Searches Graylog for logs correlated with a Zabbix host and returns a
formatted, deduplicated, and summarized string ready to be injected into
the LLM prompt.
"""

import os
import json
import hashlib
import requests
from collections import Counter
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

GRAYLOG_URL = os.environ.get("GRAYLOG_URL")
GRAYLOG_TOKEN = os.environ.get("GRAYLOG_TOKEN")
GRAYLOG_SEARCH_MINUTES = int(os.environ.get("GRAYLOG_SEARCH_MINUTES", 30))
GRAYLOG_SEARCH_LIMIT = int(os.environ.get("GRAYLOG_SEARCH_LIMIT", 100))
GRAYLOG_VERIFY_SSL = os.environ.get("GRAYLOG_VERIFY_SSL", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_query(value: str) -> str:
    """Build a Graylog query string with noise-filtering exclusions."""
    v = value.replace('"', '\\"')
    exclusions = (
        "AND NOT application_name:kernel "
        "AND NOT application_name:sshd "
        "AND NOT application_name:CRON "
        "AND NOT application_name:systemd"
    )
    return f'(source:"{v}" OR message:"{v}") {exclusions}'


def format_timestamp(ts: str) -> str:
    """Normalize an ISO timestamp to a readable format."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def _message_fingerprint(msg: dict) -> str:
    """
    Create a fingerprint for deduplication.
    Two messages are considered duplicates when they share the same source,
    application_name, and message text.
    """
    key = f"{msg.get('source', '')}|{msg.get('application_name', '')}|{msg.get('message', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate_messages(messages: list[dict]) -> list[dict]:
    """
    Remove duplicate log entries, keeping the most recent occurrence.
    Returns a list of unique message wrappers.
    """
    seen: dict[str, dict] = {}
    for msg_wrapper in messages:
        msg = msg_wrapper.get("message", {})
        fp = _message_fingerprint(msg)
        # Keep the latest occurrence (messages are typically newest-first)
        if fp not in seen:
            seen[fp] = msg_wrapper
    return list(seen.values())


def summarize_logs(messages: list[dict]) -> str:
    """
    Create a statistical summary of log messages to give the LLM a
    high-level overview before the detailed entries.
    """
    apps: Counter = Counter()
    sources: Counter = Counter()
    for msg_wrapper in messages:
        msg = msg_wrapper.get("message", {})
        apps[msg.get("application_name", "unknown")] += 1
        sources[msg.get("source", "unknown")] += 1

    lines = ["### Log Summary"]
    lines.append(f"- **Total messages**: {len(messages)}")

    if apps:
        lines.append("- **By application**:")
        for app, count in apps.most_common(10):
            lines.append(f"  - `{app}`: {count}")

    if sources and len(sources) > 1:
        lines.append("- **By source**:")
        for src, count in sources.most_common(5):
            lines.append(f"  - `{src}`: {count}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_graylog(host_raw: str) -> str:
    """
    Search Graylog for logs related to a specific host.

    Returns a formatted string containing a statistical summary followed by
    deduplicated log entries, ready for LLM consumption.
    """
    if not GRAYLOG_URL or not GRAYLOG_TOKEN:
        return "Graylog integration not fully configured (missing URL or Token)."

    # Process host name: remove IP suffix if present (e.g. "myhost_10.0.0.1")
    hostname = host_raw.split("_")[0] if host_raw else "unknown"

    query = build_query(hostname)
    query_url = f"{GRAYLOG_URL.rstrip('/')}/api/search/universal/relative"

    params = {
        "query": query,
        "range": str(GRAYLOG_SEARCH_MINUTES * 60),
        "limit": str(GRAYLOG_SEARCH_LIMIT),
    }

    headers = {"Accept": "application/json", "X-Requested-By": "cli"}
    auth = HTTPBasicAuth(GRAYLOG_TOKEN, "token")

    try:
        response = requests.get(
            query_url,
            params=params,
            auth=auth,
            headers=headers,
            verify=GRAYLOG_VERIFY_SSL,
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()
        messages = data.get("messages", [])

        if not messages:
            return (
                f"No logs found in Graylog for host '{hostname}' "
                f"in the last {GRAYLOG_SEARCH_MINUTES} minutes."
            )

        # Deduplicate
        unique_messages = deduplicate_messages(messages)

        # Build output: summary + detailed entries
        output_parts: list[str] = []

        # Statistical summary
        output_parts.append(summarize_logs(unique_messages))

        # Detailed log entries
        output_parts.append(
            f"\n### Log Entries for `{hostname}` "
            f"(last {GRAYLOG_SEARCH_MINUTES}m, {len(unique_messages)} unique "
            f"of {len(messages)} total):"
        )

        for msg_wrapper in unique_messages:
            msg = msg_wrapper.get("message", {})
            timestamp = format_timestamp(msg.get("timestamp", "N/A"))
            source = msg.get("source", "N/A")
            app_name = msg.get("application_name", "N/A")
            message_text = msg.get("message", "N/A")

            output_parts.append(
                f"[{timestamp}] {source} | {app_name} | {message_text}"
            )

        if len(output_parts) <= 2:
            return (
                f"No relevant logs found in Graylog for host '{hostname}' "
                "(query-level filter applied)."
            )

        return "\n".join(output_parts)

    except Exception as exc:
        return f"Error fetching logs from Graylog for host {hostname}: {exc}"
