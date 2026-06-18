import asyncio

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def main():

    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    async with stdio_client(server_params) as (
        read_stream,
        write_stream
    ):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            tools = await session.list_tools()

            print("\nAvailable Tools:\n")

            for tool in tools.tools:
                print(
                    f"Tool: {tool.name}"
                )
                print(
                    f"Description: "
                    f"{tool.description}"
                )
                print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())