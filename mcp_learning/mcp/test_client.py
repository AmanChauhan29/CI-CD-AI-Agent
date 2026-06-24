
from mcp_learning.mcp.client import MCPClient


client = MCPClient()
client.initialize()
for tool in client.list_tools():
    print(tool)