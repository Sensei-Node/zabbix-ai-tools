import os
import json
import logging
import asyncio
from openai import AsyncOpenAI
from datetime import datetime
import siem_fetching
from mcp_client import ZabbixMCPClient

logger = logging.getLogger(__name__)

# DeepSeek usually uses an OpenAI-compatible API
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

async def analyze_alert(event_data, dsk_api_key=None, model_name="deepseek-chat", custom_prompt=None, graylog_enabled=False, mcp_url=None, memories=None):
    """
    DeepSeek analysis engine.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        dsk_api_key (str): DeepSeek API Key.
        model_name (str): DeepSeek model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        mcp_url (str): The Zabbix MCP Server SSE endpoint URL.
        memories (str): Optional string of previous extracted facts for context.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not dsk_api_key:
        return {"error": "DEEPSEEK_API_KEY not configured"}

    try:
        # Initialize client with DeepSeek base URL
        client = AsyncOpenAI(api_key=dsk_api_key, base_url=DEEPSEEK_BASE_URL)
    except Exception as e:
        return {"error": f"Failed to initialize DeepSeek client: {str(e)}"}
    
    # 1. SIEM Enrichment
    siem_logs = ""
    if graylog_enabled:
        host_raw = event_data.get("HOST") or event_data.get("host")
        if host_raw:
            siem_logs = siem_fetching.search_graylog(host_raw)

    # 2. Build Prompt
    default_prompt = (
        "You are a senior SRE and Blockchain Infrastructure specialist. "
        "Analyze the Zabbix event data and provide technical insights."
    )
    if mcp_url:
        default_prompt += (
            " You have access to Zabbix via MCP tools. Use them if more context is needed."
        )

    selected_prompt = custom_prompt if custom_prompt else default_prompt
    
    prompt_context = f"Event Data: {json.dumps(event_data, indent=2, ensure_ascii=False)}"
    if siem_logs:
        prompt_context += f"\n\nExtra Context of Logs (SIEM):\n{siem_logs}"

    messages = []
    if memories:
        messages.append({"role": "system", "content": f"Perennial Context (Known facts about this host):\n{memories}"})
    
    messages.append({"role": "system", "content": selected_prompt})
    messages.append({"role": "user", "content": prompt_context})

    # 3. Handle MCP and Tool Calling (DeepSeek supports tool calling on some models)
    tools = []
    mcp_client = None
    
    if mcp_url:
         try:
             mcp_client = ZabbixMCPClient(mcp_url)
             await mcp_client.connect()
             mcp_tools_list = await mcp_client.get_tools()
             
             for t in mcp_tools_list:
                  tool_def = {
                      "type": "function",
                      "function": {
                          "name": t["name"],
                          "description": t["description"],
                          "parameters": t.get("parameters", {"type": "object", "properties": {}})
                      }
                  }
                  tools.append(tool_def)
         except Exception as e:
             logger.error(f"Failed to initialize MCP client for DeepSeek: {e}")

    try:
        kwargs = {
            "model": model_name,
            "messages": messages
        }
        # Note: Tool calling support might vary by DeepSeek model version
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        response_message = response.choices[0].message
        mcp_logs = ""
        
        if response_message.tool_calls:
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                 tool_name = tool_call.function.name
                 try:
                     args = json.loads(tool_call.function.arguments)
                 except Exception:
                     args = {}
                     
                 if mcp_client:
                     try:
                         tool_result_str = await mcp_client.call_tool(tool_name, args)
                         mcp_logs = (mcp_logs or "") + f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                     except Exception as e:
                         tool_result_str = f"Error: {str(e)}"
                         mcp_logs = (mcp_logs or "") + f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                 
                 messages.append({
                     "role": "tool",
                     "tool_call_id": tool_call.id,
                     "name": tool_name,
                     "content": tool_result_str
                 })
                 
            kwargs["messages"] = messages
            second_response = await client.chat.completions.create(**kwargs)
            insight = second_response.choices[0].message.content
        else:
            insight = response_message.content

        if mcp_client:
             await mcp_client.close()

        return {
            "insight": insight,
            "siem_logs": siem_logs,
            "mcp_logs": mcp_logs.strip() if mcp_logs else None
        }
    except Exception as e:
        if mcp_client:
             await mcp_client.close()
        return {"error": f"Error calling DeepSeek: {str(e)}"}
