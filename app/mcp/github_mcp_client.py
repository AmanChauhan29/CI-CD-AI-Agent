import asyncio
import requests
import os
from unittest import result
import httpx
# from app.config import GITHUB_TOKEN
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from dotenv import load_dotenv

load_dotenv()


GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"

GITHUB_PAT = os.getenv("GITHUB_TOKEN")

response = requests.get(
    "https://api.github.com/user",
    headers={
        "Authorization": f"Bearer {GITHUB_PAT}"
    }
)

print(
    response.headers.get(
        "X-OAuth-Scopes"
    )
)

async def main():

    token = GITHUB_PAT

    http_client = httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    async with streamable_http_client(
        GITHUB_MCP_URL,
        http_client=http_client
    ) as (
        read_stream,
        write_stream,
        _
    ):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()
            result = await session.call_tool(
                "get_me",
                {}
            )
            print(result)
            tools = await session.list_tools()

            print("\n===== AVAILABLE TOOLS =====\n")

            for tool in tools.tools:

                # print(tool.name)
                print("\n================")
                print(tool.name)
                # print(tool.description)
                # print(tool.inputSchema)

            

            

    await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())