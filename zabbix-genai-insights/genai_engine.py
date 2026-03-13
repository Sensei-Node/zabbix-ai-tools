import os
import json
import google.generativeai as genai
from datetime import datetime
import siem_fetching

def analyze_alert(event_data, google_api_key=None, model_name="gemini-pro", custom_prompt=None, graylog_enabled=False):
    """
    Core analysis engine shared between standalone script and Docker API.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        google_api_key (str): Google GenAI API Key.
        model_name (str): Gemini model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not google_api_key:
        return {"error": "GOOGLE_API_KEY not configured"}

    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel(model_name)
    
    # 1. SIEM Enrichment
    siem_logs = ""
    if graylog_enabled:
        host_raw = event_data.get("HOST") or event_data.get("host")
        if host_raw:
            siem_logs = siem_fetching.search_graylog(host_raw)

    # 2. Build Prompt
    default_prompt = (
        "You are a infraestructure blockchain analyst with acknowledgements in Docker and Networking." 
        "Analyze the values and tagging as a data input - excluding references likewise ~Notify~ and ~STRAPI~." 
        "Give back some technical insights  and actionables about the event."
    )
    selected_prompt = custom_prompt if custom_prompt else default_prompt
    
    prompt_context = f"Event Data: {json.dumps(event_data, indent=2, ensure_ascii=False)}"
    if siem_logs:
        prompt_context += f"\n\nExtra Context of Logs (SIEM):\n{siem_logs}"

    prompt = f"{selected_prompt}\n\n{prompt_context}"

    # 3. Call GenAI
    try:
        response = model.generate_content(prompt)
        return {
            "insight": response.text,
            "siem_logs": siem_logs
        }
    except Exception as e:
        return {"error": f"Error calling GenAI: {str(e)}"}
