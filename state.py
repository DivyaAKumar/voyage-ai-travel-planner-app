from typing import Annotated,Any,TypedDict
import operator
from langchain_core.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_id: str
    query : str

    flight_results : str
    hotel_results : str
    itinerary: str
    budget_results : str
    weather_results: str

    trip_constraints: dict[str,Any]
    selected_agents: list[str]
    supervisor_reasoning : str

    approval_request : str
    human_feedback: str
    approved: str

    llm_calls: int
    final_response: str
    guardrail_blocked: bool