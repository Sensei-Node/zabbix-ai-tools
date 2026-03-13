import os
import json
from openai import OpenAI
from datetime import datetime
import siem_fetching

def analyze_alert(event_data, openai_api_key=None, model_name="gpt-4o-mini", custom_prompt=None, graylog_enabled=False):
    """
    Core analysis engine shared between standalone script and Docker API.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        openai_api_key (str): OpenAI API Key.
        model_name (str): OpenAI model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        return {"error": f"Failed to initialize OpenAI client: {str(e)}"}
    
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
        "Give back some technical insights and actionables about the event."
    )
    selected_prompt = custom_prompt if custom_prompt else default_prompt
    
    prompt_context = f"Event Data: {json.dumps(event_data, indent=2, ensure_ascii=False)}"
    if siem_logs:
        prompt_context += f"\n\nExtra Context of Logs (SIEM):\n{siem_logs}"

    # 3. Call OpenAI API
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": selected_prompt},
                {"role": "user", "content": prompt_context}
            ]
        )
        return {
            "insight": response.choices[0].message.content,
            "siem_logs": siem_logs
        }
    except Exception as e:
        return {"error": f"Error calling OpenAI: {str(e)}"}
