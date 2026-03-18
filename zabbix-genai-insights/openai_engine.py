import os
import json
import logging
import asyncio
from openai import AsyncOpenAI
from datetime import datetime
import siem_fetching
from mcp_client import ZabbixMCPClient

logger = logging.getLogger(__name__)

async def analyze_alert(event_data, openai_api_key=None, model_name="gpt-4o-mini", custom_prompt=None, graylog_enabled=False, mcp_url=None, memories=None):
    """
    Core analysis engine shared between standalone script and Docker API.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        openai_api_key (str): OpenAI API Key.
        model_name (str): OpenAI model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        mcp_url (str): The Zabbix MCP Server SSE endpoint URL.
        memories (str): Optional string of previous extracted facts for context.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    try:
        client = AsyncOpenAI(api_key=openai_api_key)
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
        "You are an infrastructure blockchain analyst with acknowledgements in Docker and Networking. " 
        "Analyze the values and tagging as a data input - excluding references likewise ~Notify~ and ~STRAPI~. " 
        "Give back some technical insights and actionables about the event."
    )
    if mcp_url:
        default_prompt += (
            " You have access to Zabbix via MCP tools. If the alert lacks context, "
            "use these tools to query Zabbix for more info on the host, recent problems, triggers, etc."
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

    # 3. Handle MCP and Tool Calling
    tools = []
    mcp_client = None
    
    if mcp_url:
         try:
             mcp_client = ZabbixMCPClient(mcp_url)
             await mcp_client.connect()
             mcp_tools_list = await mcp_client.get_tools()
             
             # Convert MCP tools to OpenAI tool format
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
             logger.error(f"Failed to initialize MCP client for OpenAI: {e}")

    try:
        kwargs = {
            "model": model_name,
            "messages": messages
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        response_message = response.choices[0].message
        mcp_logs = ""
        
        # Check if the model decided to call a function
        if response_message.tool_calls:
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                 tool_name = tool_call.function.name
                 try:
                     args = json.loads(tool_call.function.arguments)
                 except Exception:
                     args = {}
                     
                 logger.info(f"OpenAI requested tool call: {tool_name} with args {args}")
                 
                 if mcp_client:
                     try:
                         tool_result_str = await mcp_client.call_tool(tool_name, args)
                         mcp_logs = (mcp_logs or "") + f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                     except Exception as e:
                         logger.error(f"MCP Tool {tool_name} execution error: {e}")
                         tool_result_str = "Error executing tool. MCP server might be unavailable. Proceed with your analysis disregarding this tool's response."
                         mcp_logs = (mcp_logs or "") + f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                 else:
                     tool_result_str = "Error: MCP client not initialized. Proceed with analysis using only the previous context."
                     mcp_logs = (mcp_logs or "") + f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                     
                 messages.append({
                     "role": "tool",
                     "tool_call_id": tool_call.id,
                     "name": tool_name,
                     "content": tool_result_str
                 })
                 
            # Second call to get final response
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
        return {"error": f"Error calling OpenAI: {str(e)}"}
