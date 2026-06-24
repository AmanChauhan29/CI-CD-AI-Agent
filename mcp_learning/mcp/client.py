from mcp_learning.mcp.registry import ToolRegistry
from mcp_learning.mcp.providers.github import discover_tools

class MCPClient:
    def __init__(self):
        self.registry = ToolRegistry()
    def initialize(self):
        github_tools = discover_tools()
        for tool in github_tools:
            self.registry.register(tool)
    def list_tools(self):
        return self.registry.list_tools()