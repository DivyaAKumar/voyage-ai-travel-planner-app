import csv
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import AVIATIONSTACK_API_KEY, TAVILY_API_KEY, OPENWEATHER_API_KEY, get_llm

load_dotenv()

mcp = FastMCP("aviationstack")

AIRPORTS_FILE = Path(__file__).resolve().parent / "airports.csv"

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
        },
        "aviationstack": {
            "transport": "stdio",
            "command": r"D:\travel_agent\aviationstack-mcp\.venv\Scripts\python.exe",
            "args": ["-m", "aviationstack_mcp", "mcp", "run"],
            "env": {"AVIATIONSTACK_API_KEY": AVIATIONSTACK_API_KEY}
        },
        "weather": {
            "transport": "stdio",
            "command": r"D:\travel_agent\.venv_new\Scripts\python.exe",
            "args": [r"D:\travel_agent\weather_mcp_server.py"],
            "env": {"OPENWEATHER_API_KEY": OPENWEATHER_API_KEY}
        }
    }
)

search_tool = None
aviation_tools = {}
weather_tool = None
forecast_tool = None
llm = get_llm()


async def initialize_mcp():
    global search_tool, aviation_tools

    if search_tool is not None and aviation_tools:
        return

    tools = await client.get_tools()

    search_tool = next(
        (tool for tool in tools if tool.name == "tavily_search"),
        None
    )

    if search_tool is None:
        raise RuntimeError("Tavily search tool is unavailable.")

    aviation_tools = {
        tool.name: tool
        for tool in tools
        if tool.name != "tavily_search"
    }


async def initialize_weather_tool():
    global weather_tool, forecast_tool

    if weather_tool is not None and forecast_tool is not None:
        return

    tools = await client.get_tools()

    weather_tool = next(
        (tool for tool in tools if tool.name == "get_current_weather"),
        None
    )

    forecast_tool = next(
        (tool for tool in tools if tool.name == "get_forecast"),
        None
    )

    if weather_tool is None or forecast_tool is None:
        raise RuntimeError("Weather MCP tools are unavailable.")


async def tavily_mcp_search(query: str):
    await initialize_mcp()
    return await search_tool.ainvoke({"query": query})


async def avaiation_mcp_call(tool_name: str, tool_args: dict = None):
    await initialize_mcp()

    tool = aviation_tools.get(tool_name)

    if tool is None:
        raise ValueError(f"MCP tool '{tool_name}' is unavailable.")

    return await tool.ainvoke(tool_args or {})


async def weather_mcp_search(city: str):
    await initialize_weather_tool()
    return await weather_tool.ainvoke({"city": city})


async def forecast_mcp_search(city: str):
    await initialize_weather_tool()
    return await forecast_tool.ainvoke({"city": city})


async def get_airlines():
    await initialize_mcp()
    tool = aviation_tools.get("list_airlines")

    if tool is None:
        return "Airline information is unavailable."

    return await tool.ainvoke({})


def extract_destination(query: str):
    prompt = f"""
Extract only the destination city or country from the travel request.

User request:
{query}

Return only the destination name.
"""

    response = llm.invoke(prompt)
    return response.content.strip()


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
            scheduled = (airport.get("scheduled_service") or "").strip().lower()

            if iata and scheduled == "yes" and municipality.casefold() == city_name:
                matches.append({
                    "name": airport.get("name", ""),
                    "city": municipality,
                    "iata": iata
                })

    return matches


@mcp.tool()
def extract_route(query: str) -> dict:
    """Extract origin and destination airport IATA codes from a travel request."""
    query = query.strip().casefold()

    if not query:
        return {
            "origin_iata": None,
            "destination_iata": None,
            "error": "Please provide a destination."
        }

    origin_text = ""
    destination_text = ""

    if query.startswith("from ") and " to " in query:
        origin_text, destination_text = query[5:].split(" to ", 1)

    elif query.startswith("to "):
        destination_text = query[3:]

    elif " to " in query:
        origin_text, destination_text = query.split(" to ", 1)

    else:
        destination_text = query

    stop_phrases = [
        " including ", " with ", " under ", " for ",
        " and ", " on ", " during ", " in ", " by ", ",", "."
    ]

    for phrase in stop_phrases:
        if phrase in destination_text:
            destination_text = destination_text.split(phrase, 1)[0]

    origin_text = origin_text.strip()
    destination_text = destination_text.strip()

    origin_airports = find_airport(origin_text) if origin_text else []
    destination_airports = find_airport(destination_text) if destination_text else []

    if not destination_airports:
        return {
            "origin_iata": origin_airports[0]["iata"] if origin_airports else None,
            "destination_iata": None,
            "error": "Could not identify a matching scheduled-service airport for the destination."
        }

    return {
        "origin_iata": origin_airports[0]["iata"] if origin_airports else None,
        "destination_iata": destination_airports[0]["iata"],
        "error": None if origin_airports else "Origin not provided or airport not found. Departure airport is needed for route-specific flight searches."
    }
