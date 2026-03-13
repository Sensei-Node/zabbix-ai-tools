#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json
import os
from argparse import ArgumentParser
import genai_engine

# Load environment variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GENAI_PROMPT = os.environ.get("GENAI_PROMPT")
GENAI_MODEL = os.environ.get("GENAI_MODEL", "gemini-pro")
GRAYLOG_ENABLED = os.environ.get("GRAYLOG_ENABLED", "false").lower() == "true"

def parse_event_message(event_message):
    try:
        return json.loads(event_message) if event_message else None
    except json.JSONDecodeError:
        return None

def save_output(event_id, insight, siem_logs=None):
    filename = f"{event_id}.txt"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            content = insight
            if siem_logs:
                content += "\n\n--- SIEM ENRICHMENT LOGS ---\n" + siem_logs
            f.write(content)
        return filepath
    except Exception as e:
        return f"Error saving output: {str(e)}"

def main():
    parser = ArgumentParser()
    parser.add_argument("-m", "--event-message", help="Event Message (JSON)")
    parser.add_argument("-z", "--zabbix", action="store_true", help="Zabbix Media Type format")
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
    
    print(f"Generating insight for Event ID: {event_id}...")
    
    # Call the shared engine
    result = genai_engine.analyze_alert(
        event_data=event_data,
        google_api_key=GOOGLE_API_KEY,
        model_name=GENAI_MODEL,
        custom_prompt=GENAI_PROMPT,
        graylog_enabled=GRAYLOG_ENABLED
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    insight = result["insight"]
    siem_logs = result.get("siem_logs")
    
    output_path = save_output(event_id, insight, siem_logs)
    print(f"Insight generated and saved to: {output_path}")
    print("\n--- Insight ---")
    print(insight)

if __name__ == "__main__":
    main()
