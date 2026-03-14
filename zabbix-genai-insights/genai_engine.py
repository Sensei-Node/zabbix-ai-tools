import os
import json
import logging
import asyncio
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from datetime import datetime
import siem_fetching
from mcp_client import ZabbixMCPClient

logger = logging.getLogger(__name__)

def _convert_schema_to_genai_param(schema: dict):
    """Recursively convert MCP JSON schema to GenAI format."""
    result = {"type_": schema.get("type", "object").upper()}
    if "properties" in schema:
        result["properties"] = {}
        for k, v in schema["properties"].items():
            result["properties"][k] = _convert_schema_to_genai_param(v)
    if "required" in schema:
        # GenAI doesn't directly use this "required" array format in its current structure usually,
        # but we pass it anyway.
        pass
    if "description" in schema:
        result["description"] = schema["description"]
    if "items" in schema and schema["type"] == "array":
         result["items"] = _convert_schema_to_genai_param(schema["items"])
    return result

def _pb_to_native(obj):
    """Recursively convert Gemini's protobuf MapComposite and RepeatedComposite to native dict/list."""
    if hasattr(obj, "items"):
        return {str(k): _pb_to_native(v) for k, v in obj.items()}
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
        return [_pb_to_native(i) for i in obj]
    else:
        return obj
    
async def analyze_alert(event_data, google_api_key=None, model_name="gemini-pro", custom_prompt=None, graylog_enabled=False, mcp_url=None):
    """
    Core analysis engine shared between standalone script and Docker API.
    
    Args:
        event_data (dict): The alert data from Zabbix.
        google_api_key (str): Google GenAI API Key.
        model_name (str): Gemini model name.
        custom_prompt (str): Optional context prompt override.
        graylog_enabled (bool): Whether to fetch SIEM enrichment logs.
        mcp_url (str): The Zabbix MCP Server SSE endpoint URL.
        
    Returns:
        dict: A dictionary containing the insight and any enrichment logs used.
    """
    if not google_api_key:
        return {"error": "GOOGLE_API_KEY not configured"}

    genai.configure(api_key=google_api_key)
    
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

    # 3. Handle MCP and Tool Calling
    tools = []
    mcp_client = None
    
    if mcp_url:
         try:
             mcp_client = ZabbixMCPClient(mcp_url)
             await mcp_client.connect()
             mcp_tools_list = await mcp_client.get_tools()
             
             # Convert MCP tools to GenAI FunctionDeclarations
             function_declarations = []
             for t in mcp_tools_list:
                  parameters = None
                  # Convert JSON schema to GenAI structure if params exist
                  if "parameters" in t and "properties" in t["parameters"]:
                        parameters = _convert_schema_to_genai_param(t["parameters"])
                        # GenAI function schema needs 'type_' and 'properties'
                        # Make sure root object is a dictionary with type_
                        if not isinstance(parameters, dict):
                            parameters = {"type_": "OBJECT", "properties": {}}

                  func_decl = FunctionDeclaration(
                      name=t["name"],
                      description=t["description"],
                      parameters=parameters
                  )
                  function_declarations.append(func_decl)
             if function_declarations:
                 # In Google SDK, Tool wraps multiple FunctionDeclarations
                 tools = [Tool(function_declarations=function_declarations)]
         except Exception as e:
             logger.error(f"Failed to invoke MCP client: {e}")

    try:
        model = genai.GenerativeModel(model_name=model_name, system_instruction=selected_prompt, tools=tools)
        # Using chat mode to allow the model to call functions and then respond
        chat = model.start_chat()
        
        mcp_logs = ""
        
        response = chat.send_message(prompt_context)
        
        # Check if the model decided to call a function
        # Check if the model decided to call any functions in its response parts
        has_function_call = False
        if response.parts:
            for part in response.parts:
                if getattr(part, "function_call", None):
                    has_function_call = True
                    fc = part.function_call
                    tool_name = fc.name
                    # Parse arguments safely, preventing protobuf RepeatedComposite serialization crashes
                    args = _pb_to_native(fc.args) if fc.args else {}
                    logger.info(f"GenAI requested tool call: {tool_name} with args {args}")
                    
                    if mcp_client:
                        try:
                            tool_result_str = await mcp_client.call_tool(tool_name, args)
                            mcp_logs += f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                        except Exception as e:
                            logger.error(f"MCP Tool {tool_name} execution error: {e}")
                            tool_result_str = "Error executing tool. MCP server might be unavailable. Proceed with your analysis disregarding this tool's response."
                            mcp_logs += f"\n[MCP Tool: {tool_name}] => {tool_result_str}\n"
                        
                        # Send back the result to the model
                        response = chat.send_message(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"content": tool_result_str}
                                )
                            )
                        )
                    else:
                        response = chat.send_message(
                             genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"error": "MCP client not initialized or failed. Proceed with analysis using only the previous context."}
                                )
                             )
                        )

        # Allow GenAI to process the tool results and form a final answer if a function was called.
        # If it wasn't, the initial response already contains the insight.
        result_text = chat.history[-1].parts[0].text
        
        if mcp_client:
             await mcp_client.close()
             
        return {
            "insight": result_text,
            "siem_logs": siem_logs,
            "mcp_logs": mcp_logs.strip() if mcp_logs else None
        }
    except Exception as e:
        if mcp_client:
             await mcp_client.close()
        return {"error": f"Error calling GenAI: {str(e)}"}
