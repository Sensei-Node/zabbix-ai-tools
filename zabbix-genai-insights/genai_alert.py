#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json
import os
import asyncio
from datetime import datetime
from argparse import ArgumentParser
import genai_engine

# Load environment variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
DEFAULT_PROMPT = os.environ.get("DEFAULT_PROMPT")
GENAI_MODEL = os.environ.get("GENAI_MODEL", "gemini-pro")
GRAYLOG_ENABLED = os.environ.get("GRAYLOG_ENABLED", "false").lower() == "true"
MCP_ENABLED = os.environ.get("MCP_ENABLED", "false").lower() == "true"
ZABBIX_MCP_URL = os.environ.get("ZABBIX_MCP_URL") if MCP_ENABLED else None

def parse_event_message(event_message):
    try:
        return json.loads(event_message) if event_message else None
    except json.JSONDecodeError:
        return None

def save_output(event_id, insight, siem_logs=None, mcp_logs=None):
    filename = f"{event_id}.txt"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            content = insight
            if siem_logs:
                content += "\n\n--- SIEM ENRICHMENT LOGS ---\n" + siem_logs
            if mcp_logs:
                content += "\n\n--- ZABBIX MCP ENRICHMENT LOGS ---\n" + mcp_logs
            f.write(content)
        return filepath
    except Exception as e:
        return f"Error saving output: {str(e)}"

async def async_main():
    parser = ArgumentParser()
    parser.add_argument("-m", "--event-message", help="Event Message (JSON)")
    parser.add_argument("-z", "--zabbix", action="store_true", help="Zabbix Media Type format")
    parser.add_argument("-k", "--api-key", help="Google Gemini API Key (overrides env var)")
    options = parser.parse_args()

    if not options.event_message:
        print("Error: Event message is required.")
        sys.exit(1)

    event_data = parse_event_message(options.event_message)
    if not event_data:
        print("Error: Failed to parse event message JSON.")
        sys.exit(1)

    event_id = (
        event_data.get("EVENT_ID") or 
        event_data.get("event_id") or 
        event_data.get("id") or 
        f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    api_key_to_use = event_data.get("API_KEY") or options.api_key or GOOGLE_API_KEY

    print(f"Generating insight for Event ID: {event_id}...")
    
    # Call the shared engine
    result = await genai_engine.analyze_alert(
        event_data=event_data,
        google_api_key=api_key_to_use,
        model_name=GENAI_MODEL,
        custom_prompt=DEFAULT_PROMPT,
        graylog_enabled=GRAYLOG_ENABLED,
        mcp_url=ZABBIX_MCP_URL
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    insight = result["insight"]
    siem_logs = result.get("siem_logs")
    mcp_logs = result.get("mcp_logs")
    
    output_path = save_output(event_id, insight, siem_logs, mcp_logs)
    print(f"Insight generated and saved to: {output_path}")
    print("\n--- Insight ---")
    print(insight)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
