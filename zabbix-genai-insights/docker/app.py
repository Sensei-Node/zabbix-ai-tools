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

# HTML Template
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "html_template.tpl")


def load_template():
    with open(TEMPLATE_PATH, "r") as f:
        return f.read()


HTML_TEMPLATE = load_template()

# Initialize DB
if GOOGLE_API_KEY or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
    db.init_db()


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
# Routes
# ---------------------------------------------------------------------------

@app.get("/outputs", response_class=HTMLResponse)
async def list_outputs():
    """HTML dashboard listing all generated insights."""
    rows = db.list_all_insights()

    if not rows:
        content = '<div class="empty-state">No insights found yet. Send an alert to generate one!</div>'
    else:
        list_html = '<ul class="insight-list">'
        for row in rows:
            event_id, timestamp, insight, raw_data, status = row
            try:
                data = json.loads(raw_data) if raw_data else {}
                title = data.get("NAME") or data.get("name") or "GenAI Insight"
            except Exception:
                title = "GenAI Insight"

            preview = (insight[:120] + "...") if len(insight) > 120 else insight
            preview = preview.replace("\\n", " ").replace("\\r", " ")

            status_class = f"status-{status.lower()}"

            list_html += f"""
            <li class="insight-card">
                <a href="/outputs/{event_id}" class="insight-link">
                    <div class="insight-header">
                        <span class="event-id">{title}</span>
                        <span class="status-badge {status_class}">{status}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size: 0.8rem; color: var(--accent);">EventID: {event_id}</span>
                        <span class="timestamp">{timestamp}</span>
                    </div>
                    <div class="preview">{preview}</div>
                </a>
            </li>
            """
        list_html += "</ul>"
        content = list_html
    return HTML_TEMPLATE.format(content=content)


@app.post("/analyze", status_code=202)
async def analyze_event(
    event_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Accept a Zabbix alert payload and start background analysis."""
    # Verify at least one provider key is configured
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


@app.get("/outputs/{event_id}")
async def get_output(event_id: str):
    """Retrieve a specific insight by event ID."""
    row = db.get_insight_by_id(event_id)

    if row:
        insight, status = row
        if status == "PENDING":
            return Response(
                content="[ PENDING ] Analysis is still in progress. Please refresh in a few seconds.",
                media_type="text/plain",
            )
        return Response(content=insight, media_type="text/plain")

    file_path = f"/app/outputs/{event_id}.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/plain")
    raise HTTPException(status_code=404, detail="Insight not found")


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
