import os
import asyncio 
import csv
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

AVIATIONSTACK_API_KEY = os.getenv('AVIATIONSTACK_API_KEY')
TAVILY_API_API=os.getenv('TAVILY_API_KEY')

mcp = FastMCP("aviationstack")

AIRPORTS_FILE = (
    Path(__file__).resolve().parent.parent / "airports.csv"
)

client = MultiServerMCPClient(
    #konse server ke saath kis mcp client ko use krna h
    {
        'tavily':{
            'transport': 'streamable_http',
            'url': f'https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_API}'
        },
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

#tool discovery
'''async def main():
    tools = await client.get_tools()
    print('\n Available MCP Tools:\n')
    for tool in tools:
        print(tool.name)

if __name__ == "__main__":
    asyncio.run(main()) '''
'''
async def main():
    tools = await client.get_tools()
    search_tool = next(
        tool
        for tool in tools
        if tool.name =='tavily_search'
    )

    result = await search_tool.ainvoke(
        {
            'query': 'best hotels in delhi'
        }
    )
    print(result)
asyncio.run(main()) '''
'''
if __name__ == "__main__":
    asyncio.run(main()) '''

search_tool = None 
aviation_tools = {}

'''
async def initialize_mcp():
    global search_tool
    if search_tool is not None:
        return

    tools = await client.get_tools()
    print('\nAvailable MCP Tools:\n')
    for tool in tools:
        print(tool.name)
    search_tool = next(
        tool
        for tool in tools
        if tool.name =='tavily_search'
    )'''
async def initialize_mcp():
    global search_tool
    global aviation_tools

    if search_tool is not None and aviation_tools:
        return

    tools = await client.get_tools()
    print('\nAvailable MCP Tools:\n')
    for tool in tools:
        print(tool.name)
    search_tool = next(
        tool
        for tool in tools
        if tool.name =='tavily_search'
    )
    aviation_tools = {
        tool.name : tool
        for tool in tools
        if tool.name != 'tavily_search'

    }



async def tavily_mcp_search(query: str):
    await initialize_mcp()
    result = await search_tool.ainvoke({'query': query} )
    return result

async def avaiation_mcp_call(tool_name: str, tool_args: dict=None):
    tools = await client.get_tools()
    tool = next(
        t for t in tools
        if t.name == tool_name
    )
    result = await tool.ainvoke(
        tool_args or {}
    )
    return result
'''
async def get_airports():
    await initialize_mcp()
    tool = aviation_tools.get('list_airports')
    if not tool:
        return 'Airport tool unavailable'
    result = await tool.ainvoke({})
    return result 
'''
async def get_airlines():
    await initialize_mcp()
    tool = aviation_tools.get('list_airlines')
    if not tool:
        return 'Airline tool unavailable'
    result = await tool.ainvoke({})
    return result


@mcp.tool()
def find_airport(city_name: str) -> list[dict]:
    """Find scheduled-service airports by exact city or municipality name."""
    city_name = city_name.strip().casefold()
    matches = []

    with open(AIRPORTS_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for airport in reader:
            iata = (airport.get("iata_code") or "").strip()
            municipality = (airport.get("municipality") or "").strip()
            scheduled = (
                airport.get("scheduled_service") or ""
            ).strip().lower()

            if (
                iata
                and scheduled == "yes"
                and municipality.casefold() == city_name
            ):
                matches.append({
                    "name": airport.get("name", ""),
                    "city": municipality,
                    "iata": iata
                })

    return matches


@mcp.tool()
def extract_route(query: str) -> dict:
    """Extract origin and destination airport IATA codes from a travel request."""
    query = query.casefold()

    if " from " not in f" {query} " or " to " not in f" {query} ":
        return {
            "origin_iata": None,
            "destination_iata": None,
            "error": "Request must contain a route in the format 'from X to Y'."
        }

    after_from = query.split(" from ", 1)[1]
    origin_text, destination_text = after_from.split(" to ", 1)

    stop_phrases = [
        " including ", " with ", " under ", " for ",
        " and ", " on ", " during ", ",", "."
    ]

    for phrase in stop_phrases:
        if phrase in destination_text:
            destination_text = destination_text.split(phrase, 1)[0]

    origin_text = origin_text.strip()
    destination_text = destination_text.strip()

    origin_airports = find_airport(origin_text)
    destination_airports = find_airport(destination_text)

    if not origin_airports or not destination_airports:
        return {
            "origin_iata": None,
            "destination_iata": None,
            "error": "Could not find a matching scheduled-service airport for both cities."
        }

    return {
        "origin_iata": origin_airports[0]["iata"],
        "destination_iata": destination_airports[0]["iata"]
    }
