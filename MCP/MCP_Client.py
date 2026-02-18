import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv()
class MCPClient:
    def __init__(self):
        self.session:ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        if is_python:
            path = Path(server_script_path).resolve()
            server_params = StdioServerParameters(
                command="uv",
                args=["run", "--with", "mcp", str(Path(server_script_path).resolve())],
                env=os.environ.copy(),
            )


        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("Connected to server with tools:", [tool.name for tool in tools])

    async def call_tools(self, tool_name, tool_args) -> str:
         result = await self.session.call_tool(tool_name, tool_args)
         return result
    
    async def get_tools(self):
        response = await self.session.list_tools()
        return [
            {"name": t.name, "description": t.description,
                "input_schema": t.inputSchema}
            for t in response.tools
        ]
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()      

#Client wrapper
_client = None

async def init_client(server_path):
    global _client
    _client = MCPClient()
    await _client.connect_to_server(server_path)

async def get_tools():
    return await _client.get_tools()

async def call_tool(name, args):
    return await _client.call_tools(name, args)

async def cleanup():
    await _client.cleanup()