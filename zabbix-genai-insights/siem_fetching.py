import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta

# Configuration from environment
GRAYLOG_URL = os.environ.get("GRAYLOG_URL")
GRAYLOG_TOKEN = os.environ.get("GRAYLOG_TOKEN")
GRAYLOG_SEARCH_MINUTES = int(os.environ.get("GRAYLOG_SEARCH_MINUTES", 30))

def build_query(value: str) -> str:
    v = value.replace('"', '\\"')
    # Move filtering to the query level for efficiency
    exclusions = 'AND NOT application_name:kernel AND NOT application_name:sshd AND NOT application_name:CRON AND NOT application_name:systemd'
    return f'(source:"{v}" OR message:"{v}") {exclusions}'

def format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts

def search_graylog(host_raw):
    """
    Search Graylog for logs related to a specific host, using example_graylog.py as base.
    """
    if not GRAYLOG_URL or not GRAYLOG_TOKEN:
        return "Graylog integration not fully configured (missing URL or Token)."

    # Process host name: remove IP if present
    hostname = host_raw.split('_')[0] if host_raw else "unknown"
    
    query = build_query(hostname)
    limit = 100
    
    query_url = f"{GRAYLOG_URL.rstrip('/')}/api/search/universal/relative"
    
    params = {
        "query": query,
        "range": str(GRAYLOG_SEARCH_MINUTES * 60),
        "limit": str(limit),
    }
    
    headers = {"Accept": "application/json", "X-Requested-By": "cli"}
    auth = HTTPBasicAuth(GRAYLOG_TOKEN, "token")

    try:
        # verify=False to match example_graylog.py
        response = requests.get(query_url, params=params, auth=auth, headers=headers, verify=False, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        messages = data.get("messages", [])
        
        if not messages:
            return f"No logs found in Graylog for host '{hostname}' in the last {GRAYLOG_SEARCH_MINUTES} minutes."
            
        # Format logs for the prompt
        formatted_logs = [f"Graylog Logs for {hostname} (last {GRAYLOG_SEARCH_MINUTES}m):"]
        for msg_wrapper in messages:
            msg = msg_wrapper.get("message", {})
            timestamp = format_timestamp(msg.get("timestamp", "N/A"))
            source = msg.get("source", "N/A")
            app_name = msg.get("application_name", "N/A")
            message_text = msg.get("message", "N/A")
            
            formatted_logs.append(f"[{timestamp}] {source} | {app_name} | {message_text}")
            
        if len(formatted_logs) == 1:
            return f"No relevant logs found in Graylog for host '{hostname}' (query-level filter applied)."
            
        return "\n".join(formatted_logs)

    except Exception as e:
        return f"Error fetching logs from Graylog for host {hostname}: {str(e)}"
