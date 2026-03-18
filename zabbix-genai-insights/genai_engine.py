import os
import json
import logging
import asyncio
from google import genai
from google.genai import types
from datetime import datetime
import siem_fetching
from mcp_client import ZabbixMCPClient

logger = logging.getLogger(__name__)

def _convert_schema_to_genai_param(schema: dict):
    """Recursively convert MCP JSON schema to GenAI (google-genai) format."""
    # The new SDK uses types.Schema which follows JSON schema closely
    result = {"type": schema.get("type", "object").upper()}
    if "properties" in schema:
        result["properties"] = {}
        for k, v in schema["properties"].items():
            result["properties"][k] = _convert_schema_to_genai_param(v)
    if "required" in schema:
        result["required"] = schema["required"]
    if "description" in schema:
        result["description"] = schema["description"]
    if "items" in schema and schema["type"] == "array":
        result["items"] = _convert_schema_to_genai_param(schema["items"])
    return result

async def analyze_alert(event_data, google_api_key=None, model_name="gemini-2.0-flash", custom_prompt=None, graylog_enabled=False, mcp_url=None, memories=None):
    """
    Core analysis engine using the new google-genai SDK.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        google_api_key (str): Google GenAI API Key.
        model_name (str): Gemini model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        mcp_url (str): The Zabbix MCP Server SSE endpoint URL.
        memories (str): Optional string of previous extracted facts for context.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not google_api_key:
        return {"error": "GOOGLE_API_KEY not configured"}

    client = genai.Client(api_key=google_api_key)
    
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
    if memories:
        prompt_context += f"\n\nPerennial Context (Known facts about this host):\n{memories}"

    # 3. Handle MCP and Tool Calling
    tools = []
    mcp_client = None
    
    if mcp_url:
         try:
             mcp_client = ZabbixMCPClient(mcp_url)
             await mcp_client.connect()
             mcp_tools_list = await mcp_client.get_tools()
             
             # Convert MCP tools to google-genai FunctionDeclarations
             function_declarations = []
             for t in mcp_tools_list:
                  parameters = None
                  if "parameters" in t and "properties" in t["parameters"]:
                        parameters = _convert_schema_to_genai_param(t["parameters"])

                  func_decl = types.FunctionDeclaration(
                      name=t["name"],
                      description=t["description"],
                      parameters=parameters
                  )
                  function_declarations.append(func_decl)
             if function_declarations:
                 tools = [types.Tool(function_declarations=function_declarations)]
         except Exception as e:
             logger.error(f"Failed to invoke MCP client: {e}")

    try:
        # Construct the generation config
        config = types.GenerateContentConfig(
            system_instruction=selected_prompt,
            tools=tools
        )

        mcp_logs = ""
        
        # Start the generation flow. The new SDK handles function calling via a loop or automatic mechanisms
        # But we'll do it manually to maintain control over the MCP client.
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_context,
            config=config
        )
        
        # In a real situation with many tools, this could be a loop.
        # Check for tool calls in the response
        if response.candidates and response.candidates[0].content.parts:
            parts = response.candidates[0].content.parts
            tool_calls = [p.function_call for p in parts if p.function_call]
            
            if tool_calls and mcp_client:
                tool_results = []
                for fc in tool_calls:
                    tool_name = fc.name
                    args = fc.args or {}
                    logger.info(f"GenAI requested tool call: {tool_name} with args {args}")
                    
                    try:
                        tool_result_str = await mcp_client.call_tool(tool_name, args)
                        mcp_logs += f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                    except Exception as e:
                        logger.error(f"MCP Tool {tool_name} execution error: {e}")
                        tool_result_str = f"Error: {str(e)}"
                        mcp_logs += f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                    
                    tool_results.append(types.Part.from_function_response(
                        name=tool_name,
                        response={"content": tool_result_str}
                    ))
                
                # Send the tool results back to get final answer
                # Contents should include original prompt, model's tool call part, and our response part
                new_contents = [
                    types.Content(role="user", parts=[types.Part.from_text(prompt_context)]),
                    response.candidates[0].content, # Model's tool call
                    types.Content(role="user", parts=tool_results) # Our response
                ]
                
                final_response = client.models.generate_content(
                    model=model_name,
                    contents=new_contents,
                    config=config
                )
                result_text = final_response.text
            else:
                result_text = response.text
        else:
            result_text = response.text
        
        if mcp_client:
             await mcp_client.close()
             
        return {
            "insight": result_text if result_text else "No insight generated.",
            "siem_logs": siem_logs,
            "mcp_logs": mcp_logs.strip() if mcp_logs else None
        }
    except Exception as e:
        if mcp_client:
             await mcp_client.close()
        logger.error(f"Error calling GenAI: {str(e)}")
        return {"error": f"Error calling GenAI: {str(e)}"}
