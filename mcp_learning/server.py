from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Demo Server")


@mcp.tool()
def hello(name: str) -> str:
    """
    Return greeting.
    """
    print("Called hello method using mcp")
    return f"Hello {name}"

@mcp.tool()
def add(a: int, b: int) -> int:
    """
     Add two numbers and return the result."""
    return a + b

if __name__ == "__main__":
    print("Starting FastMCP server...")
    mcp.run()