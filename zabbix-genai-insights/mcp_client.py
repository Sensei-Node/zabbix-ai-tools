import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

class ZabbixMCPClient:
    """Client for interacting with the Zabbix MCP Server via SSE."""
    
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self._session: Optional[ClientSession] = None
        self._sse_ctx = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        
    async def connect(self):
        """Connect to the MCP server."""
        if self._session:
            return
            
        try:
            self._sse_ctx = sse_client(self.mcp_url)
            read_stream, write_stream = await self._sse_ctx.__aenter__()
            
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()
            await self._session.initialize()
            logger.info(f"Connected to MCP Server at {self.mcp_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP Server: {e}")
            await self.close()
            raise

    async def get_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        try:
            if not self._session:
                await self.connect()
                
            if self._tools_cache is not None:
                return self._tools_cache
                
            tools_response = await self._session.list_tools()
            tools = []
            for t in tools_response.tools:
                tool_def = {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema
                }
                tools.append(tool_def)
                
            self._tools_cache = tools
            return tools
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a specific tool on the MCP server."""
        try:
            if not self._session:
                await self.connect()
                
            logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
            result = await self._session.call_tool(tool_name, arguments)
            
            # Extract content from the result
            if result.isError:
                error_msg = f"MCP tool '{tool_name}' returned error: "
                if hasattr(result, 'content') and result.content:
                     error_msg += str([c.text for c in result.content if hasattr(c, 'text')])
                return json.dumps({"error": error_msg})

            # Normal success path
            if hasattr(result, 'content') and result.content:
               # Usually returns a single TextContent object with a JSON string inside
               text_contents = [c.text for c in result.content if hasattr(c, 'text')]
               joined_text = "\n".join(text_contents).strip()
               
               if not joined_text or joined_text in ["[]", "{}"]:
                   return "Tool executed successfully, but no matching records were found (empty result)."
                   
               return joined_text
            else:
                 return "Tool executed successfully but returned no content."
                
        except Exception as e:
             logger.error(f"Exception calling MCP tool '{tool_name}': {e}")
             return json.dumps({"error": f"Exception executing tool: {str(e)}"})

    async def close(self):
        """Clean up the connection."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing MCP session: {e}")
            finally:
                self._session = None
                
        if self._sse_ctx:
            try:
                 await self._sse_ctx.__aexit__(None, None, None)
            except Exception as e:
                 logger.error(f"Error closing SSE context: {e}")
            finally:
                 self._sse_ctx = None
                 self._tools_cache = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
