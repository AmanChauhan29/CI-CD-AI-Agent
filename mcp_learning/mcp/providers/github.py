from mcp_learning.mcp.models import MCPTool

def discover_tools():
    return [
        MCPTool(
            name="get_workflow_logs",
            description="Download workflow logs",
            provider="github",
            input_schema={}
        ),
        MCPTool(
            name="create_pull_request",
            description="Create pull request",
            provider="github",
            input_schema={}
        ),
        MCPTool(
            name="merge_pull_request",
            description="Merge pull request",
            provider="github",
            input_schema={}
        )
    ]