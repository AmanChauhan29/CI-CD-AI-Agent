from dataclasses import dataclass


@dataclass
class MCPTool:
    name: str
    description: str
    provider: str
    input_schema: dict