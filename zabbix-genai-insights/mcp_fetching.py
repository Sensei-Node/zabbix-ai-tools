"""
Zabbix MCP Server enrichment module.

Queries the Zabbix MCP Server (running in SSE transport mode) to fetch live
host details, active problems, and recent events for a given host.  The
enriched context is injected into the LLM prompt alongside SIEM logs and
historical insights.

Protocol
--------
The MCP Server uses the **MCP SSE transport** (JSON-RPC 2.0 over SSE):

1. Client opens a GET request to the ``/sse`` endpoint.  The server sends
   an ``endpoint`` event whose ``data`` field contains the URL for POSTing
   JSON-RPC messages (e.g. ``/messages?sessionId=<uuid>``).
2. Client sends ``initialize`` → receives ``initialized`` response.
3. Client sends ``tools/call`` requests via POST to the messages endpoint.
4. Responses arrive as SSE ``message`` events on the open connection.

This module implements a lightweight, synchronous MCP SSE client using only
``requests`` (already a project dependency) — no extra SDK required.

This module is optional — controlled by the ``MCP_ENABLED`` env var.
When disabled, all public functions return empty strings gracefully.
"""

import os
import json
import logging
import threading
import queue
import uuid
import requests
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

MCP_ENABLED = os.environ.get("MCP_ENABLED", "false").lower() == "true"
ZABBIX_MCP_URL = os.environ.get("ZABBIX_MCP_URL", "http://zabbix-mcp:8000/sse")
MCP_TIMEOUT = int(os.environ.get("MCP_TIMEOUT", "15"))


# ---------------------------------------------------------------------------
# Lightweight synchronous MCP SSE client
# ---------------------------------------------------------------------------

class _MCPClient:
    """
    Minimal synchronous MCP client that speaks JSON-RPC 2.0 over SSE.

    Lifecycle for a single batch of tool calls:
        1. connect()        — opens the SSE stream, discovers the messages
                              endpoint, sends ``initialize``.
        2. call_tool(...)   — sends ``tools/call`` and waits for the response.
        3. close()          — tears down the SSE stream.

    Designed to be used via the ``_with_mcp_session`` context helper.
    """

    def __init__(self, sse_url: str, timeout: int = 15):
        self._sse_url = sse_url
        self._timeout = timeout
        self._messages_url: Optional[str] = None
        self._responses: queue.Queue = queue.Queue()
        self._sse_response: Optional[requests.Response] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._session = requests.Session()

    # -- connection ---------------------------------------------------------

    def connect(self) -> bool:
        """Open the SSE stream, discover the messages endpoint, initialize."""
        try:
            self._sse_response = self._session.get(
                self._sse_url,
                stream=True,
                timeout=self._timeout,
                headers={"Accept": "text/event-stream"},
            )
            self._sse_response.raise_for_status()
        except Exception as exc:
            logger.warning("MCP SSE connect failed (%s): %s", self._sse_url, exc)
            return False

        # Start background reader
        self._reader_thread = threading.Thread(
            target=self._read_sse_stream, daemon=True
        )
        self._reader_thread.start()

        # Wait for the ``endpoint`` event (server sends it immediately)
        try:
            evt = self._responses.get(timeout=self._timeout)
        except queue.Empty:
            logger.warning("MCP SSE: no endpoint event received")
            self.close()
            return False

        if evt.get("_sse_event") == "endpoint":
            # The data is a relative or absolute URL for POSTing messages
            endpoint_path = evt.get("_sse_data", "")
            self._messages_url = self._resolve_messages_url(endpoint_path)
        else:
            logger.warning("MCP SSE: first event was not 'endpoint': %s", evt)
            self.close()
            return False

        # Send ``initialize``
        init_resp = self._jsonrpc_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "zabbix-genai-insights", "version": "1.0.0"},
        })

        if init_resp is None:
            logger.warning("MCP SSE: initialize handshake failed")
            self.close()
            return False

        # Send ``notifications/initialized``
        self._jsonrpc_notify("notifications/initialized", {})

        return True

    def close(self):
        """Tear down the SSE connection."""
        self._stop_event.set()
        if self._sse_response:
            try:
                self._sse_response.close()
            except Exception:
                pass
        self._session.close()

    # -- tool calls ---------------------------------------------------------

    def call_tool(self, tool_name: str, arguments: dict) -> Optional[Any]:
        """
        Call a tool on the MCP server and return the parsed result.

        Returns the parsed JSON content on success, or None on failure.
        """
        resp = self._jsonrpc_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if resp is None:
            return None

        # Extract text content from the MCP tool result
        result = resp.get("result", resp)
        if isinstance(result, dict) and "content" in result:
            for item in result["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except (json.JSONDecodeError, TypeError):
                        return item["text"]
        return result

    # -- internals ----------------------------------------------------------

    def _resolve_messages_url(self, endpoint_path: str) -> str:
        """Resolve the messages endpoint relative to the SSE URL."""
        if endpoint_path.startswith("http://") or endpoint_path.startswith("https://"):
            return endpoint_path
        # Build absolute URL from the SSE base
        from urllib.parse import urljoin
        # Base is everything up to and including the host:port
        base = self._sse_url.rsplit("/", 1)[0] + "/"
        return urljoin(base, endpoint_path.lstrip("/"))

    def _jsonrpc_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request and wait for the matching response."""
        if not self._messages_url:
            return None

        req_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        try:
            http_resp = self._session.post(
                self._messages_url,
                json=payload,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
            http_resp.raise_for_status()
        except Exception as exc:
            logger.warning("MCP POST %s failed: %s", method, exc)
            return None

        # Wait for the JSON-RPC response on the SSE stream
        deadline = self._timeout
        while deadline > 0:
            try:
                evt = self._responses.get(timeout=min(deadline, 2))
                if isinstance(evt, dict) and evt.get("id") == req_id:
                    if "error" in evt:
                        logger.warning(
                            "MCP JSON-RPC error for %s: %s", method, evt["error"]
                        )
                        return None
                    return evt
                # Not our response — put it back? No, just discard or log.
            except queue.Empty:
                deadline -= 2
                continue

        logger.warning("MCP SSE: timeout waiting for response to %s", method)
        return None

    def _jsonrpc_notify(self, method: str, params: dict):
        """Send a JSON-RPC notification (no response expected)."""
        if not self._messages_url:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        try:
            self._session.post(
                self._messages_url,
                json=payload,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
        except Exception as exc:
            logger.debug("MCP notify %s failed (non-critical): %s", method, exc)

    def _read_sse_stream(self):
        """Background thread: parse SSE events from the streaming response."""
        event_type = ""
        data_lines: list[str] = []

        try:
            for raw_line in self._sse_response.iter_lines(decode_unicode=True):
                if self._stop_event.is_set():
                    break
                if raw_line is None:
                    continue

                line = raw_line

                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
                elif line == "":
                    # End of event
                    if data_lines:
                        data_str = "\n".join(data_lines)
                        self._dispatch_event(event_type, data_str)
                    event_type = ""
                    data_lines = []
        except Exception as exc:
            if not self._stop_event.is_set():
                logger.debug("MCP SSE reader stopped: %s", exc)

    def _dispatch_event(self, event_type: str, data: str):
        """Route a parsed SSE event to the response queue."""
        if event_type == "endpoint":
            self._responses.put({"_sse_event": "endpoint", "_sse_data": data})
        elif event_type == "message" or event_type == "":
            try:
                parsed = json.loads(data)
                self._responses.put(parsed)
            except json.JSONDecodeError:
                logger.debug("MCP SSE: non-JSON message data: %s", data[:200])


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def _with_mcp_session(tool_calls: list[tuple[str, dict]]) -> list[Optional[Any]]:
    """
    Open a single MCP session, execute a batch of tool calls, and close.

    Parameters
    ----------
    tool_calls : list of (tool_name, arguments) tuples

    Returns
    -------
    list of results (None for failed calls), same order as input.
    """
    if not MCP_ENABLED:
        return [None] * len(tool_calls)

    client = _MCPClient(sse_url=ZABBIX_MCP_URL, timeout=MCP_TIMEOUT)
    results: list[Optional[Any]] = []

    try:
        if not client.connect():
            return [None] * len(tool_calls)

        for tool_name, arguments in tool_calls:
            results.append(client.call_tool(tool_name, arguments))
    except Exception as exc:
        logger.warning("MCP session error: %s", exc)
        # Pad remaining results with None
        while len(results) < len(tool_calls):
            results.append(None)
    finally:
        client.close()

    return results


# ---------------------------------------------------------------------------
# Public enrichment functions
# ---------------------------------------------------------------------------

def fetch_host_context(hostname: str, host_data: Optional[Any] = None) -> str:
    """
    Format host details from Zabbix MCP data.

    If ``host_data`` is provided (pre-fetched), uses it directly.
    Otherwise returns empty string (caller should batch via
    ``enrich_from_mcp``).
    """
    hosts = host_data
    if not hosts:
        return ""

    lines = ["## Zabbix Host Details (via MCP)"]
    for host in hosts[:3]:
        lines.append(f"- **Host ID**: {host.get('hostid', 'N/A')}")
        lines.append(f"- **Technical Name**: {host.get('host', 'N/A')}")
        lines.append(f"- **Visible Name**: {host.get('name', 'N/A')}")
        status = "Enabled" if str(host.get('status')) == '0' else "Disabled"
        lines.append(f"- **Status**: {status}")
        avail = host.get("available", "")
        if avail:
            avail_map = {"0": "Unknown", "1": "Available", "2": "Unavailable"}
            lines.append(f"- **Availability**: {avail_map.get(str(avail), avail)}")
        if host.get("description"):
            lines.append(f"- **Description**: {host['description']}")
        lines.append("")

    return "\n".join(lines)


def format_problems(hostname: str, problems: Optional[Any]) -> str:
    """Format active problems data into a markdown section."""
    if not problems:
        return ""

    severity_map = {
        "0": "Not classified",
        "1": "Information",
        "2": "Warning",
        "3": "Average",
        "4": "High",
        "5": "Disaster",
    }

    lines = [f"## Active Problems for `{hostname}` (via MCP)"]
    lines.append(f"Found **{len(problems)}** active problem(s):\n")

    for p in problems:
        sev = severity_map.get(str(p.get("severity", "0")), "Unknown")
        name = p.get("name", "N/A")
        eventid = p.get("eventid", "N/A")
        lines.append(f"- **[{sev}]** {name} (Event ID: {eventid})")

    return "\n".join(lines)


def format_events(hostname: str, events: Optional[Any]) -> str:
    """Format recent events data into a markdown section."""
    if not events:
        return ""

    lines = [f"## Recent Events for `{hostname}` (via MCP)"]
    for ev in events:
        eventid = ev.get("eventid", "N/A")
        name = ev.get("name", "N/A")
        clock = ev.get("clock", "")
        value = ev.get("value", "")
        status_str = "PROBLEM" if str(value) == "1" else "OK"
        lines.append(f"- Event {eventid}: {name} [{status_str}] (clock: {clock})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Aggregated enrichment (single MCP session for all queries)
# ---------------------------------------------------------------------------

def enrich_from_mcp(hostname: str) -> str:
    """
    Fetch all available MCP enrichment data for a host and return a
    combined markdown string ready for prompt injection.

    Opens a **single** MCP SSE session and executes all tool calls within
    it, minimizing connection overhead.

    Returns an empty string when MCP is disabled, no data is available,
    or any error occurs — MCP enrichment must never block insight generation.
    """
    if not MCP_ENABLED or not hostname:
        return ""

    try:
        return _enrich_from_mcp_inner(hostname)
    except Exception as exc:
        logger.warning("MCP enrichment failed (non-fatal): %s", exc)
        return ""


def _enrich_from_mcp_inner(hostname: str) -> str:
    """Internal implementation of MCP enrichment — may raise on unexpected errors."""

    # --- Step 1: Resolve host ID ---
    host_result = _with_mcp_session([
        ("host_get", {
            "search": {"host": hostname},
            "output": "extend",
            "limit": 5,
        }),
    ])

    hosts = host_result[0]
    if not hosts or not isinstance(hosts, list) or len(hosts) == 0:
        return ""

    hostid = hosts[0].get("hostid")

    # --- Step 2: Fetch problems + events in a single session ---
    tool_calls: list[tuple[str, dict]] = []

    if hostid:
        tool_calls.append(("problem_get", {
            "hostids": [hostid],
            "output": "extend",
            "recent": True,
            "limit": 10,
        }))
        tool_calls.append(("event_get", {
            "hostids": [hostid],
            "output": "extend",
            "limit": 10,
        }))

    detail_results = _with_mcp_session(tool_calls) if tool_calls else []

    # --- Step 3: Format sections ---
    sections: list[str] = []

    host_ctx = fetch_host_context(hostname, hosts)
    if host_ctx:
        sections.append(host_ctx)

    if len(detail_results) > 0:
        problems_ctx = format_problems(hostname, detail_results[0])
        if problems_ctx:
            sections.append(problems_ctx)

    if len(detail_results) > 1:
        events_ctx = format_events(hostname, detail_results[1])
        if events_ctx:
            sections.append(events_ctx)

    return "\n\n".join(sections) if sections else ""
