import os
import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

AVIATIONSTACK_API_KEY = os.getenv('AVIATIONSTACK_API_KEY')

client = MultiServerMCPClient(
    {
        'aviationstack':{
            'transport': 'stdio',
            'command': r'D:\travel_agent\aviationstack-mcp\.venv\Scripts\python.exe',
            'args': [
                '-m',
                'aviationstack_mcp',
                'mcp',
                'run'
            ],
            'env':{
                'AVIATIONSTACK_API_KEY': AVIATIONSTACK_API_KEY
            }
        }
    }
)


async def main():
    tools = await client.get_tools()
    print("\nFlight Tool Schemas\n")

    for tool in tools:
        if 'flight' in tool.name or 'schedule' in tool.name:
            print(f"\nTool: {tool.name}")
            print(tool.args_schema)

asyncio.run(main())

'''
if __name__ == '___main__':
    asyncio.run(main())'''