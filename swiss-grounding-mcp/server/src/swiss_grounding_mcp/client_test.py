
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream):

        async with ClientSession(read_stream, write_stream) as session:

            # Initialize MCP connection
            await session.initialize()

            # See available tools
            tools = await session.list_tools()

            print("Available tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call your tool
            result = await session.call_tool(
                "find_connections",
                arguments={
                    "origin": "Zürich HB",
                    "destination": "Bern",
                    "departure_time": "2026-09-25T09:00:00",
                    "results": 3,
                },
            )

            print("\nResult:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())