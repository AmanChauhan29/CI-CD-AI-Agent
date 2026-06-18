import asyncio

from mcp import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters
)


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

            result = await session.call_tool(
                "hello",
                {
                    "name": "Aman"
                }
            )

            print("\nHELLO RESULT:")
            print(result)

            result = await session.call_tool(
                "add",
                {
                    "a": 5,
                    "b": 10
                }
            )

            print("\nADD RESULT:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())