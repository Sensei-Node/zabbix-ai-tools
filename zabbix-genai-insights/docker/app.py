from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any

# Ensure parent directory is in path for library imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genai_engine
import openai_engine
import db

app = FastAPI(title="Zabbix AI Alert API")

# Load environment variables
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()

# Gemini Config
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GENAI_MODEL = os.environ.get("GENAI_MODEL", "gemini-pro")

# OpenAI Config
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Shared Prompt Config
DEFAULT_PROMPT = os.environ.get("DEFAULT_PROMPT")

GENAI_OUTPUT_TYPE = os.environ.get("GENAI_OUTPUT_TYPE", "BOTH").upper() # FILE, DB, BOTH
GENAI_MAX_OUTPUTS = int(os.environ.get("GENAI_MAX_OUTPUTS", 0))

# Graylog Config
GRAYLOG_ENABLED = os.environ.get("GRAYLOG_ENABLED", "false").lower() == "true"
GRAYLOG_URL = os.environ.get("GRAYLOG_URL")

# Path for the HTML Template
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "html_template.tpl")

def load_template():
    with open(TEMPLATE_PATH, "r") as f:
        return f.read()

HTML_TEMPLATE = load_template()

if GOOGLE_API_KEY or OPENAI_API_KEY:
    db.init_db()

def handle_pruning():
    """Handles deletion of files and DB entries based on retention policy."""
    deleted_ids = db.prune_old_outputs(GENAI_MAX_OUTPUTS)
    for oid in deleted_ids:
        try:
            fpath = f"/app/outputs/{oid}.txt"
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception as e:
            print(f"Error deleting file for {oid}: {e}")

# MCP Config
MCP_ENABLED = os.environ.get("MCP_ENABLED", "false").lower() == "true"
ZABBIX_MCP_URL = os.environ.get("ZABBIX_MCP_URL") if MCP_ENABLED else None

async def background_process_alert(event_id: str, event_data: Dict[str, Any]):
    """Background worker for AI analysis."""
    try:
        req_provider = event_data.get("AI_PROVIDER", AI_PROVIDER).lower()
        req_api_key = event_data.get("API_KEY")

        if req_provider == "openai":
            key_to_use = req_api_key or OPENAI_API_KEY
            result = await openai_engine.analyze_alert(
                event_data=event_data,
                openai_api_key=key_to_use,
                model_name=OPENAI_MODEL,
                custom_prompt=DEFAULT_PROMPT,
                graylog_enabled=GRAYLOG_ENABLED,
                mcp_url=ZABBIX_MCP_URL
            )
        else:
            key_to_use = req_api_key or GOOGLE_API_KEY
            result = await genai_engine.analyze_alert(
                event_data=event_data,
                google_api_key=key_to_use,
                model_name=GENAI_MODEL,
                custom_prompt=DEFAULT_PROMPT,
                graylog_enabled=GRAYLOG_ENABLED,
                mcp_url=ZABBIX_MCP_URL
            )

        insight = result.get("insight", result.get("error", "Unknown error"))
        siem_logs = result.get("siem_logs")
        mcp_logs = result.get("mcp_logs")
        status = "COMPLETED" if "insight" in result else "ERROR"

        # Update Database
        db.update_insight_status(event_id, insight, status)

        # Save to File if COMPLETED
        if status == "COMPLETED" and GENAI_OUTPUT_TYPE in ["FILE", "BOTH"]:
            filename = f"/app/outputs/{event_id}.txt"
            os.makedirs("/app/outputs", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                content_to_save = insight
                if siem_logs:
                    content_to_save += "\n\n--- SIEM ENRICHMENT LOGS ---\n" + siem_logs
                if mcp_logs:
                    content_to_save += "\n\n--- ZABBIX MCP ENRICHMENT LOGS ---\n" + mcp_logs
                f.write(content_to_save)

        # Run retention policy
        handle_pruning()

    except Exception as e:
        print(f"Background process error for {event_id}: {e}")
        db.update_insight_status(event_id, str(e), "ERROR")

@app.get("/outputs", response_class=HTMLResponse)
async def list_outputs():
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
            except:
                title = "GenAI Insight"
            
            preview = (insight[:120] + '...') if len(insight) > 120 else insight
            preview = preview.replace('\\n', ' ').replace('\\r', ' ')
            
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
        list_html += '</ul>'
        content = list_html
    return HTML_TEMPLATE.format(content=content)

@app.post("/analyze", status_code=202)
async def analyze_event(event_data: Dict[str, Any], background_tasks: BackgroundTasks):
    req_provider = event_data.get("AI_PROVIDER", AI_PROVIDER).lower()
    req_api_key = event_data.get("API_KEY")

    if req_provider == "openai" and not (OPENAI_API_KEY or req_api_key):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured or provided")
    elif req_provider == "gemini" and not (GOOGLE_API_KEY or req_api_key):
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured or provided")

    # Extract event_id immediately
    event_id = (
        event_data.get("EVENT_ID") or 
        event_data.get("event_id") or 
        event_data.get("id") or 
        f"event_{datetime.now().strftime('%Y%j%d_%H%M%S')}"
    )

    # Pre-insert into DB as PENDING
    db.save_pending_insight(event_id, event_data)

    # Add to background tasks
    background_tasks.add_task(background_process_alert, event_id, event_data)

    return {
        "status": "accepted",
        "event_id": event_id,
        "message": "Analysis started in background"
    }

@app.get("/outputs/{event_id}")
async def get_output(event_id: str):
    row = db.get_insight_by_id(event_id)

    if row:
        insight, status = row
        if status == "PENDING":
             return Response(content="[ PENDING ] Analysis is still in progress. Please refresh in a few seconds.", media_type="text/plain")
        return Response(content=insight, media_type="text/plain")

    file_path = f"/app/outputs/{event_id}.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/plain")
    raise HTTPException(status_code=404, detail="Insight not found")

@app.get("/health")
async def health_check():
    model_used = OPENAI_MODEL if AI_PROVIDER == "openai" else GENAI_MODEL
    health_status = {
        "status": "ok",
        "provider": AI_PROVIDER,
        "model": model_used,
        "output_type": GENAI_OUTPUT_TYPE,
        "siem_enrichment": GRAYLOG_ENABLED,
        "mcp_enabled": MCP_ENABLED
    }

    if GRAYLOG_ENABLED and GRAYLOG_URL:
        try:
            # Check Graylog connectivity
            # We hit /api/system/status which is a common health endpoint for Graylog
            g_url = f"{GRAYLOG_URL.rstrip('/')}/api/system/status"
            resp = requests.get(g_url, timeout=5, verify=False)
            health_status["siem_reachable"] = resp.status_code == 200
        except Exception as e:
            print(f"Health check: Graylog unreachable at {GRAYLOG_URL}: {e}")
            health_status["siem_reachable"] = False

    if MCP_ENABLED and ZABBIX_MCP_URL:
        try:
            # Check MCP connectivity
            # ZABBIX_MCP_URL usually points to /sse, we check if we can reach it
            resp = requests.get(ZABBIX_MCP_URL, timeout=5)
            # If server responds with anything but a server error, we consider it alive
            health_status["mcp_reachable"] = resp.status_code < 500
        except Exception as e:
            print(f"Health check: Zabbix MCP unreachable at {ZABBIX_MCP_URL}: {e}")
            health_status["mcp_reachable"] = False

    return health_status
