"""
Zabbix GenAI Alert API — FastAPI application.

Provides an asynchronous HTTP interface for submitting Zabbix alerts,
generating AI-powered insights, and browsing results via a web dashboard.
"""

from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
import os
import sys
import json
import html as html_mod
from datetime import datetime
from typing import Dict, Any

# Ensure parent directory is in path for shared module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genai_engine
import db

app = FastAPI(title="Zabbix GenAI Alert API")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GENAI_PROMPT = os.environ.get("GENAI_PROMPT")
GENAI_MODEL = os.environ.get("GENAI_MODEL", "gemini-pro")
GENAI_OUTPUT_TYPE = os.environ.get("GENAI_OUTPUT_TYPE", "BOTH").upper()
GENAI_MAX_OUTPUTS = int(os.environ.get("GENAI_MAX_OUTPUTS", 0))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")
LLM_MODEL = os.environ.get("LLM_MODEL") or GENAI_MODEL

# Graylog
GRAYLOG_ENABLED = os.environ.get("GRAYLOG_ENABLED", "false").lower() == "true"

# HTML Templates
TEMPLATE_DIR = os.path.dirname(__file__)


def _load_template(name: str) -> str:
    with open(os.path.join(TEMPLATE_DIR, name), "r") as f:
        return f.read()


HTML_TEMPLATE = _load_template("html_template.tpl")
DETAIL_TEMPLATE = _load_template("html_detail.tpl")

# Initialize DB
if GOOGLE_API_KEY or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
    db.init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_MAP = {
    "disaster": "disaster",
    "high": "high",
    "average": "average",
    "warning": "warning",
    "information": "information",
    "info": "information",
    "not classified": "default",
}


def _severity_class(raw: str) -> str:
    """Map a Zabbix severity string to a CSS class."""
    return SEVERITY_MAP.get((raw or "").strip().lower(), "default")


def _escape(text: str) -> str:
    """HTML-escape user-provided text."""
    return html_mod.escape(str(text)) if text else ""


def _extract_event_meta(raw_data: str) -> dict:
    """Extract display-friendly metadata from the raw_data JSON string."""
    try:
        data = json.loads(raw_data) if raw_data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    return {
        "title": data.get("TRIGGER_NAME") or data.get("trigger_name")
                 or data.get("NAME") or data.get("name") or "GenAI Insight",
        "host": data.get("HOST") or data.get("host") or "",
        "severity": data.get("TRIGGER_SEVERITY") or data.get("severity") or "",
        "item_value": data.get("ITEM_VALUE") or data.get("item_value") or "",
        "event_time": data.get("EVENT_DATE") or data.get("event_date") or "",
    }


def _svg_icon(name: str) -> str:
    """Return inline SVG icons used in the dashboard."""
    icons = {
        "server": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>',
        "clock": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
        "tag": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/></svg>',
        "zap": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        "hash": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>',
    }
    return icons.get(name, "")


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

def handle_pruning():
    """Delete files and DB entries based on retention policy."""
    deleted_ids = db.prune_old_outputs(GENAI_MAX_OUTPUTS)
    for oid in deleted_ids:
        try:
            fpath = f"/app/outputs/{oid}.txt"
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception as e:
            print(f"Error deleting file for {oid}: {e}")


async def background_process_alert(event_id: str, event_data: Dict[str, Any]):
    """Background worker for GenAI analysis."""
    try:
        result = genai_engine.analyze_alert(
            event_data=event_data,
            google_api_key=GOOGLE_API_KEY,
            model_name=GENAI_MODEL,
            custom_prompt=GENAI_PROMPT,
            graylog_enabled=GRAYLOG_ENABLED,
        )

        insight = result.get("insight", result.get("error", "Unknown error"))
        siem_logs = result.get("siem_logs")
        model_used = result.get("model", "unknown")
        status = "COMPLETED" if "insight" in result else "ERROR"

        # Prepend model info to insight
        insight_with_meta = f"[Model: {model_used}]\n\n{insight}"

        # Update Database
        db.update_insight_status(event_id, insight_with_meta, status)

        # Save to File if COMPLETED
        if status == "COMPLETED" and GENAI_OUTPUT_TYPE in ["FILE", "BOTH"]:
            filename = f"/app/outputs/{event_id}.txt"
            os.makedirs("/app/outputs", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                content_to_save = insight_with_meta
                if siem_logs:
                    content_to_save += "\n\n--- SIEM ENRICHMENT LOGS ---\n" + siem_logs
                f.write(content_to_save)

        # Run retention policy
        handle_pruning()

    except Exception as e:
        print(f"Background process error for {event_id}: {e}")
        db.update_insight_status(event_id, str(e), "ERROR")


# ---------------------------------------------------------------------------
# Routes — Dashboard
# ---------------------------------------------------------------------------

@app.get("/outputs", response_class=HTMLResponse)
async def list_outputs():
    """HTML dashboard listing all generated insights."""
    rows = db.list_all_insights()

    # --- Stats ---
    total = len(rows)
    completed = sum(1 for r in rows if r[4] == "COMPLETED")
    pending = sum(1 for r in rows if r[4] == "PENDING")
    errors = sum(1 for r in rows if r[4] == "ERROR")

    stats_html = '<div class="stats-bar">'
    stats_html += f'<span class="stat-pill total"><span class="dot"></span>{total} total</span>'
    if completed:
        stats_html += f'<span class="stat-pill completed"><span class="dot"></span>{completed} completed</span>'
    if pending:
        stats_html += f'<span class="stat-pill pending"><span class="dot"></span>{pending} pending</span>'
    if errors:
        stats_html += f'<span class="stat-pill error"><span class="dot"></span>{errors} errors</span>'
    stats_html += "</div>"

    # --- Cards ---
    if not rows:
        content = (
            '<div class="empty-state">'
            '<div class="empty-icon">📡</div>'
            "<p>No insights generated yet. Send a Zabbix alert to "
            "<code>/analyze</code> to get started.</p>"
            "</div>"
        )
        toolbar_display = "display:none"
    else:
        toolbar_display = ""
        list_html = '<ul class="insight-list">'
        for row in rows:
            event_id, timestamp, insight, raw_data, status = row
            meta = _extract_event_meta(raw_data)
            sev_class = _severity_class(meta["severity"])

            # Clean preview: skip [Model: ...] prefix
            preview_text = insight or ""
            if preview_text.startswith("[Model:"):
                newline_pos = preview_text.find("\n")
                if newline_pos > 0:
                    preview_text = preview_text[newline_pos:].strip()
            preview_text = preview_text[:180].replace("\n", " ").replace("\r", " ")
            if len(insight or "") > 180:
                preview_text += "…"

            status_lower = status.lower()

            # Build meta tags
            meta_tags = ""
            if meta["host"]:
                meta_tags += (
                    f'<span class="meta-tag">{_svg_icon("server")} '
                    f'{_escape(meta["host"])}</span>'
                )
            if meta["severity"]:
                meta_tags += (
                    f'<span class="meta-tag">'
                    f'<span class="severity-dot severity-{sev_class}"></span>'
                    f'{_escape(meta["severity"])}</span>'
                )
            if meta["item_value"]:
                meta_tags += (
                    f'<span class="meta-tag">{_svg_icon("zap")} '
                    f'{_escape(meta["item_value"])}</span>'
                )
            meta_tags += (
                f'<span class="meta-tag">{_svg_icon("clock")} '
                f'{_escape(timestamp)}</span>'
            )
            meta_tags += (
                f'<span class="meta-tag">{_svg_icon("hash")} '
                f'{_escape(event_id)}</span>'
            )

            list_html += f"""
            <li class="insight-card" data-status="{status_lower}">
                <a href="/outputs/{_escape(event_id)}" class="insight-link">
                    <div class="card-top">
                        <span class="card-title">{_escape(meta["title"])}</span>
                        <span class="status-badge status-{status_lower}">{status_lower}</span>
                    </div>
                    <div class="card-meta">{meta_tags}</div>
                    <div class="card-preview">{_escape(preview_text)}</div>
                </a>
            </li>
            """
        list_html += "</ul>"
        content = list_html

    provider_info = f"Provider: {LLM_PROVIDER} / {LLM_MODEL}"

    return HTML_TEMPLATE.format(
        content=content,
        stats_bar=stats_html,
        toolbar_display=toolbar_display,
        provider_info=_escape(provider_info),
    )


# ---------------------------------------------------------------------------
# Routes — Detail view
# ---------------------------------------------------------------------------

@app.get("/outputs/{event_id}", response_class=HTMLResponse)
async def get_output(event_id: str):
    """Retrieve a specific insight with a styled detail page."""
    row = db.get_insight_by_id(event_id)

    if not row:
        # Fallback to file
        file_path = f"/app/outputs/{event_id}.txt"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            return _render_detail(
                event_id=event_id,
                title="GenAI Insight",
                status="COMPLETED",
                insight=file_content,
                raw_data=None,
                timestamp="",
            )
        raise HTTPException(status_code=404, detail="Insight not found")

    insight, status = row

    # Fetch full row for metadata
    all_rows = db.list_all_insights()
    full_row = next((r for r in all_rows if r[0] == event_id), None)
    raw_data = full_row[3] if full_row else None
    timestamp = full_row[1] if full_row else ""

    meta = _extract_event_meta(raw_data)

    return _render_detail(
        event_id=event_id,
        title=meta["title"],
        status=status,
        insight=insight,
        raw_data=raw_data,
        timestamp=timestamp,
    )


def _render_detail(
    event_id: str,
    title: str,
    status: str,
    insight: str,
    raw_data: str | None,
    timestamp: str,
) -> HTMLResponse:
    """Render the detail page for a single insight."""
    meta = _extract_event_meta(raw_data)
    sev_class = _severity_class(meta["severity"])
    status_lower = status.lower()

    # Build meta tags
    meta_html = f'<span class="status-badge status-{status_lower}">{status_lower}</span>'
    if meta["host"]:
        meta_html += (
            f'<span class="meta-tag">{_svg_icon("server")} '
            f'{_escape(meta["host"])}</span>'
        )
    if meta["severity"]:
        meta_html += (
            f'<span class="meta-tag">'
            f'<span class="severity-dot severity-{sev_class}"></span>'
            f'{_escape(meta["severity"])}</span>'
        )
    if meta["item_value"]:
        meta_html += (
            f'<span class="meta-tag">{_svg_icon("zap")} '
            f'{_escape(meta["item_value"])}</span>'
        )
    if timestamp:
        meta_html += (
            f'<span class="meta-tag">{_svg_icon("clock")} '
            f'{_escape(timestamp)}</span>'
        )
    meta_html += (
        f'<span class="meta-tag">{_svg_icon("hash")} '
        f'{_escape(event_id)}</span>'
    )

    # Body
    if status == "PENDING":
        body_html = (
            '<div class="pending-banner">'
            '<span class="spinner"></span>'
            "Analysis in progress… this page will refresh automatically."
            "</div>"
        )
        auto_refresh = "<script>setTimeout(() => location.reload(), 5000);</script>"
    else:
        body_html = f'<div class="insight-body">{_escape(insight)}</div>'
        auto_refresh = ""

    return HTMLResponse(
        content=DETAIL_TEMPLATE.format(
            page_title=_escape(title),
            detail_title=_escape(title),
            detail_meta=meta_html,
            detail_body=body_html,
            auto_refresh=auto_refresh,
        )
    )


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.post("/analyze", status_code=202)
async def analyze_event(
    event_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Accept a Zabbix alert payload and start background analysis."""
    has_key = any([
        GOOGLE_API_KEY,
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("DEEPSEEK_API_KEY"),
        LLM_PROVIDER == "ollama",
    ])
    if not has_key:
        raise HTTPException(
            status_code=500,
            detail="No LLM API key configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, or DEEPSEEK_API_KEY.",
        )

    event_id = (
        event_data.get("EVENT_ID")
        or event_data.get("event_id")
        or event_data.get("id")
        or f"event_{datetime.now().strftime('%Y%j%d_%H%M%S')}"
    )

    # Pre-insert into DB as PENDING
    db.save_pending_insight(event_id, event_data)

    # Add to background tasks
    background_tasks.add_task(background_process_alert, event_id, event_data)

    return {
        "status": "accepted",
        "event_id": event_id,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "message": "Analysis started in background",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with provider information."""
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "output_type": GENAI_OUTPUT_TYPE,
        "graylog_enabled": GRAYLOG_ENABLED,
    }
