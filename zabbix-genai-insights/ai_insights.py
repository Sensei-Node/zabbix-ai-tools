#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json
import os
import asyncio
from datetime import datetime
from argparse import ArgumentParser

# Engine imports
import genai_engine
import openai_engine
import dsk_engine

# Load environment variables with unified naming
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
# Fallback logic for API keys and Models
AI_API_KEY = os.environ.get("AI_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL")

DEFAULT_PROMPT = os.environ.get("DEFAULT_PROMPT")
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
    parser = ArgumentParser(description="Unified Zabbix AI Alert Script")
    parser.add_argument("-m", "--event-message", help="Event Message (JSON)")
    parser.add_argument("-p", "--provider", help="AI Provider (gemini or openai)")
    parser.add_argument("-k", "--api-key", help="AI API Key (overrides env var)")
    parser.add_argument("-model", "--model", help="AI Model name (overrides env var)")
    options = parser.parse_args()

    if not options.event_message:
        print("Error: Event message is required (-m).")
        sys.exit(1)

    event_data = parse_event_message(options.event_message)
    if not event_data:
        print("Error: Failed to parse event message JSON.")
        sys.exit(1)

    # Resolve Provider
    provider = options.provider or event_data.get("AI_PROVIDER") or AI_PROVIDER
    provider = provider.lower()

    # Resolve API Key (Options > EventData > AI_API_KEY > API_KEY > AI_API_KEY_ENV)
    api_key = options.api_key or event_data.get("AI_API_KEY") or event_data.get("API_KEY") or AI_API_KEY
    if not api_key:
        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        elif provider == "deepseek":
            api_key = os.environ.get("DEEPSEEK_API_KEY")
        else:
            api_key = os.environ.get("GOOGLE_API_KEY")

    # Resolve Model
    model = options.model or event_data.get("AI_MODEL") or AI_MODEL
    if not model:
        if provider == "openai":
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        elif provider == "deepseek":
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        else:
            model = os.environ.get("GENAI_MODEL", "gemini-pro")

    event_id = (
        event_data.get("EVENT_ID") or 
        event_data.get("event_id") or 
        event_data.get("id") or 
        f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    print(f"Generating insight using {provider} ({model}) for Event ID: {event_id}...")
    
    if provider == "openai":
        result = await openai_engine.analyze_alert(
            event_data=event_data,
            openai_api_key=api_key,
            model_name=model,
            custom_prompt=DEFAULT_PROMPT,
            graylog_enabled=GRAYLOG_ENABLED,
            mcp_url=ZABBIX_MCP_URL
        )
    elif provider == "deepseek":
        result = await dsk_engine.analyze_alert(
            event_data=event_data,
            dsk_api_key=api_key,
            model_name=model,
            custom_prompt=DEFAULT_PROMPT,
            graylog_enabled=GRAYLOG_ENABLED,
            mcp_url=ZABBIX_MCP_URL
        )
    else:
        result = await genai_engine.analyze_alert(
            event_data=event_data,
            google_api_key=api_key,
            model_name=model,
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
