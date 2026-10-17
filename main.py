import uuid
import logging
import psycopg
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from agents import (flight_agent, 
                    hotel_agent,
                    weather_agent,
                    itinerary_agent,
                    human_review_agent,
                    final_response_agent
                    ,budget_agent,
                    supervisor_agent)
from state import State
from config import DATABASE_URL
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain_mcp_adapters").setLevel(logging.WARNING)

AGENT_ORDER = [
    'flight_agent',
    'hotel_agent',
    'weather_agent',
    'budget_agent',
    'itinerary_agent',


]

ROUTE_MAP={
    "flight_agent": 'flight_agent',
    "hotel_agent": "hotel_agent",
    "weather_agent": "weather_agent",
    "budget_agent": "budget_agent",
    "itinerary_agent": "itinerary_agent",
    "final_response": "final_response",
}

def selected_agents(state: State) -> list[str]:
    selected = state.get("selected_agents", [])
    return [agent for agent in AGENT_ORDER if agent in selected]

def route_from_supervisor(state: State) -> str:
    if state.get("guardrail_blocked", False):
        return "final_response"
    selected = selected_agents(state)
    return selected[0] if selected else "itinerary_agent"

def route_after_agent(current_agent: str):
    def route(state: State) -> str:
        selected = selected_agents(state)
        current_index = AGENT_ORDER.index(current_agent)

        for next_agent in AGENT_ORDER[current_index + 1:]:
            if next_agent in selected:
                return next_agent

        return "itinerary_agent"

    return route

def route_after_human_approval(state: State) -> str:
    if state.get("approved") == "yes":
        return "final_response"

    if state.get("approved") == "no":
        return "itinerary_agent"

    raise ValueError("Invalid human approval status.")

def build_graph():
    graph = StateGraph(State)

    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("flight_agent", flight_agent)
    graph.add_node("hotel_agent", hotel_agent)
    graph.add_node("weather_agent", weather_agent)
    graph.add_node("budget_agent", budget_agent)
    graph.add_node("itinerary_agent", itinerary_agent)
    graph.add_node("human_approval", human_review_agent)
    graph.add_node("final_response", final_response_agent)

    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges("supervisor", route_from_supervisor, ROUTE_MAP)

    graph.add_conditional_edges("flight_agent", route_after_agent("flight_agent"), ROUTE_MAP)
    graph.add_conditional_edges("hotel_agent", route_after_agent("hotel_agent"), ROUTE_MAP)
    graph.add_conditional_edges("weather_agent", route_after_agent("weather_agent"), ROUTE_MAP)
    graph.add_conditional_edges("budget_agent", route_after_agent("budget_agent"), ROUTE_MAP)

    graph.add_edge("itinerary_agent", "human_approval")
    graph.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
        "final_response": "final_response",
        "itinerary_agent": "itinerary_agent",
        }
    )
    graph.add_edge("final_response", END)

    
    if DATABASE_URL:
        conn = psycopg.connect(DATABASE_URL, autocommit=True)
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
    else:
        checkpointer = InMemorySaver()

    return graph.compile(checkpointer=checkpointer)

app = build_graph()

