
import asyncio
import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from config import get_llm
from mcp_client import (
    tavily_mcp_search, get_airlines, avaiation_mcp_call,
    extract_route, extract_destination, forecast_mcp_search, weather_mcp_search
)
from state import State
from langgraph.types import interrupt

llm = get_llm()


def llm_text(system: str, prompt: str) -> str:
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    return response.content


def json_to_dict(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Supervisor did not return valid JSON.")
    return json.loads(text[start:end + 1])


SUPERVISOR_PROMPT = """
You are the supervisor of VOYAGE, a multi-agent AI travel planning system.

User request:
{query}

Available agents:
- flight_agent: flights, routes, airports, airlines and airfare.
- hotel_agent: hotels, accommodation, amenities and hotel research.
- weather_agent: weather, forecasts, seasonal conditions and packing advice.
- budget_agent: budget analysis, affordability, cost estimates and price comparisons.
- itinerary_agent: day-wise schedules, sightseeing, activities and complete trip planning.

Rules:
1. Select only agents relevant to the user's request.
2. For a complete trip plan, select itinerary_agent and relevant specialist agents.
3. Do not select every agent automatically.
4. Consider budget_agent when a budget, affordability or cost breakdown matters.
5. Do not invent missing trip details.
6. Select only agents from the list above.
7. Record important missing information in trip_constraints.

Extract destination, origin, duration, travel_dates, travelers, budget,
travel_style, special_preferences and missing_information.
Use empty strings for unknown individual values and empty lists when no
special preferences or missing information can be identified.

Briefly explain the agent selection in reasoning.

Return ONLY valid JSON using this schema:
{
    "selected_agents": [],
    "trip_constraints": {
        "destination": "",
        "origin": "",
        "duration": "",
        "travel_dates": "",
        "travelers": "",
        "budget": "",
        "travel_style": "",
        "special_preferences": [],
        "missing_information": []
    },
    "reasoning": ""
}
"""


def supervisor_agent(state: State) -> dict:
    query = state["query"]

    guardrail_prompt = """
Determine whether the following request is a valid travel-planning request.

Allow requests related to travel planning, destinations, flights, hotels,
transportation, sightseeing, itineraries, travel budgets, weather for trips,
packing advice and related travel questions.

Block requests that are unrelated to travel planning or are clearly harmful.

Return ONLY valid JSON in this format:
{
    "allowed": true,
    "reason": ""
}

If allowed, briefly explain why the request is relevant to travel.
If blocked, provide a concise and polite reason.

User request:
{query}
""".replace("{query}", query)

    guardrail_raw = llm_text(
        "You are an input validation guardrail for VOYAGE. Return strict JSON only.",
        guardrail_prompt
    )

    guardrail_result = json_to_dict(guardrail_raw)

    if not isinstance(guardrail_result.get("allowed"), bool):
        raise ValueError("Guardrail returned an invalid allowed value.")

    llm_calls = state.get("llm_calls", 0) + 1

    if not guardrail_result["allowed"]:
        reason = guardrail_result.get("reason", "").strip()
        if not reason:
            reason = "This request is outside VOYAGE's travel-planning scope."

        return {
            "selected_agents": [],
            "trip_constraints": {},
            "supervisor_reasoning": reason,
            "guardrail_blocked": True,
            "final_response": reason,
            "messages": [AIMessage(content=reason)],
            "llm_calls": llm_calls
        }

    prompt = SUPERVISOR_PROMPT.replace("{query}", query)

    raw = llm_text(
        "You are the VOYAGE supervisor. Return valid JSON only.",
        prompt
    )

    parsed = json_to_dict(raw)
    llm_calls += 1

    allowed_agents = {
        "flight_agent",
        "hotel_agent",
        "weather_agent",
        "budget_agent",
        "itinerary_agent"
    }

    selected = parsed.get("selected_agents", [])

    if not isinstance(selected, list) or not all(
        isinstance(agent, str) and agent in allowed_agents
        for agent in selected
    ):
        raise ValueError("Supervisor returned invalid agent selections.")

    constraints = parsed.get("trip_constraints", {})

    if not isinstance(constraints, dict):
        raise ValueError("Supervisor returned invalid trip constraints.")

    return {
        "selected_agents": selected,
        "trip_constraints": constraints,
        "supervisor_reasoning": parsed.get("reasoning", ""),
        "guardrail_blocked": False,
        "messages": [AIMessage(content="Supervisor created the agent plan.")],
        "llm_calls": llm_calls
    }


FLIGHT_AGENT_PROMPT = """
You are a travel flight expert for VOYAGE.

User Query:
{query}

Trip Constraints:
{constraints}

Route Information:
{route_data}

Departure Schedule at the Origin:
{departures}

Arrival Schedule at the Destination:
{arrivals}

Airline Information:
{airline_data}

Instructions:
1. Use the trip constraints to identify the origin, destination and travel dates.
2. Use the route information to verify airport IATA codes.
3. Summarize the supplied departure and arrival schedule information accurately.
4. The departure and arrival data are retrieved separately. Do not claim that
   they represent a matching flight between the requested origin and destination
   unless the returned records explicitly establish that route.
5. Never invent flight numbers, fares, timings, availability or connections.
6. If route-specific flights cannot be verified, say so clearly.
7. Clearly distinguish actual tool results from general travel advice.
8. If essential information is missing, state what is needed.
9. Keep the response concise.

Return only information supported by the supplied data.
"""


def flight_agent(state: State) -> dict:
    query = state["query"]
    constraints = state.get("trip_constraints", {}) or {}
    llm_calls = 0

    try:
        origin = (constraints.get("origin") or "").strip()
        destination = (constraints.get("destination") or "").strip()

        if not origin or not destination:
            missing = []
            if not origin:
                missing.append("departure city")
            if not destination:
                missing.append("destination")

            flight_data = (
                f"Flight schedules cannot be verified yet. "
                f"Please provide the {' and '.join(missing)}."
            )

        else:
            route_query = f"from {origin} to {destination}"
            route = extract_route(route_query)

            if route.get("error"):
                flight_data = (
                    f"{route['error']} Flight schedules cannot be verified "
                    "until a valid origin and destination are identified."
                )
            else:
                origin_iata = route["origin_iata"]
                destination_iata = route["destination_iata"]

                departures = asyncio.run(avaiation_mcp_call(
                    "future_flights_arrival_departure_schedule",
                    {
                        "airport_iata_code": origin_iata,
                        "schedule_type": "departure",
                        "number_of_flights": 10,
                    }
                ))

                arrivals = asyncio.run(avaiation_mcp_call(
                    "future_flights_arrival_departure_schedule",
                    {
                        "airport_iata_code": destination_iata,
                        "schedule_type": "arrival",
                        "number_of_flights": 10,
                    }
                ))

                airline_data = asyncio.run(get_airlines())

                prompt = FLIGHT_AGENT_PROMPT.format(
                    query=query,
                    constraints=json.dumps(constraints, ensure_ascii=False),
                    route_data=json.dumps(route, ensure_ascii=False),
                    departures=str(departures)[:3000],
                    arrivals=str(arrivals)[:3000],
                    airline_data=str(airline_data)[:2000],
                )

                llm_calls += 1
                flight_data = llm_text(
                    "You are an accurate travel flight planner.",
                    prompt
                )

    except Exception:
        flight_data = (
            "Flight information is currently unavailable. Please verify the "
            "route, schedules and flight details with an airline."
        )

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight results fetched.")],
        "llm_calls": state.get("llm_calls", 0) + llm_calls,
    }

def hotel_agent(state: State) -> dict:
    constraints = state.get("trip_constraints", {}) or {}
    destination = constraints.get("destination", "")

    query = f"""
Find actual hotels in {destination or "the destination specified by the user"}.

User request: {state.get("query", "")}
Trip constraints: {constraints}

Search for specific hotel properties, not general travel guides or budget articles.
Prioritize:
- Hotel name and neighborhood
- Price per room per night in INR, if available
- Guest rating and number of reviews, if available
- Amenities and proximity to public transport
- Official website or direct booking link

Include a comparison of 3-5 relevant hotels if the search results support it.
If exact prices or availability are unavailable, say so.
Do not invent hotel names, ratings, prices, amenities or booking links.
"""

    try:
        raw_results = asyncio.run(tavily_mcp_search(query))

        # MCP responses may contain JSON inside a text content block.
        if isinstance(raw_results, list):
            parsed_results = []

            for item in raw_results:
                if not isinstance(item, dict):
                    parsed_results.append(str(item))
                    continue

                text_content = item.get("text")

                if not text_content:
                    continue

                try:
                    data = json.loads(text_content)

                    if isinstance(data, dict):
                        answer = data.get("answer")
                        results = data.get("results", [])

                        if answer:
                            parsed_results.append(f"Search summary:\n{answer}")

                        for result in results:
                            if not isinstance(result, dict):
                                continue

                            title = result.get("title", "Untitled result")
                            url = result.get("url", "")
                            content = result.get("content", "")

                            parsed_results.append(
                                f"**{title}**\n"
                                f"URL: {url}\n"
                                f"Details: {content}"
                            )

                    else:
                        parsed_results.append(str(data))

                except (json.JSONDecodeError, TypeError):
                    parsed_results.append(text_content)

            hotel_results = "\n\n".join(parsed_results)

        elif isinstance(raw_results, dict):
            hotel_results = json.dumps(raw_results, ensure_ascii=False, indent=2)

        else:
            hotel_results = str(raw_results)

        if not hotel_results.strip():
            hotel_results = (
                "No usable hotel search results were returned. "
                "Please verify accommodation options directly."
            )

    except Exception as exc:
        print(f"Hotel research error: {exc}")
        hotel_results = (
            "Hotel information is currently unavailable. "
            "Please verify accommodation options directly."
        )

    return {
        "hotel_results": hotel_results,
        "messages": [AIMessage(content="Hotel research completed.")],
        "llm_calls": state.get("llm_calls", 0),
    }

def weather_agent(state: State) -> dict:
    constraints = state.get("trip_constraints", {}) or {}
    city = constraints.get("destination", "").strip()
    llm_calls = 0

    try:
        if not city:
            llm_calls += 1
            city = extract_destination(state["query"]).strip()

        if not city:
            weather_results = "Weather information is unavailable because the destination could not be identified."
        else:
            weather_data = asyncio.run(weather_mcp_search(city))
            forecast_data = asyncio.run(forecast_mcp_search(city))
            weather_results = f"Current Weather:\n{weather_data}\n\nForecast:\n{forecast_data}"

    except Exception:
        weather_results = (
            "Weather information is currently unavailable. Check a reliable "
            "weather provider before travelling."
        )

    return {
        "weather_results": weather_results,
        "messages": [AIMessage(content="Weather information fetched.")],
        "llm_calls": state.get("llm_calls", 0) + llm_calls
    }


def budget_agent(state: State) -> dict:
    query = state["query"]
    constraints = state.get("trip_constraints", {}) or {}

    prompt = f"""
You are a practical travel budget analyst for VOYAGE.

User request:
{query}

Trip constraints:
{constraints}

Flight results:
{state.get("flight_results", "")}

Hotel results:
{state.get("hotel_results", "")}

Weather results:
{state.get("weather_results", "")}

Assess whether the trip is realistic within the user's budget.
Cover flights, accommodation, food, transport, activities and miscellaneous
expenses where relevant. Use actual prices only when supported by the results.
Clearly label estimates, identify cost risks, suggest savings and assess
feasibility. If prices or essential information are missing, state that
feasibility cannot be confirmed. Never invent confirmed prices.

Return a concise assessment with a budget overview, cost categories,
risks, savings suggestions, feasibility and missing information.
"""
    result = llm_text("You are an accurate and practical travel budget analyst.", prompt)

    return {
        "budget_results": result,
        "messages": [AIMessage(content="Budget analysis completed.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



def itinerary_agent(state: State) -> dict:
    prompt = f"""
You are the itinerary planning agent for VOYAGE.

User request:
{state["query"]}

Trip constraints:
{state.get("trip_constraints", {})}

Flight results:
{state.get("flight_results", "")}

Hotel results:
{state.get("hotel_results", "")}

Weather results:
{state.get("weather_results", "")}

Budget assessment:
{state.get("budget_results", "")}

Previous human feedback:
{state.get("human_feedback", "") or "No previous feedback."}

Create a practical, personalized travel plan.

Include a trip overview, relevant flight and hotel information,
a day-by-day itinerary, weather advice, a budget breakdown,
and important travel tips.

Apply the previous human feedback when revising a draft.
Never invent flight schedules, hotel prices, ratings, weather forecasts,
or booking confirmations. Clearly identify unavailable information
and label cost estimates.

Return the complete travel plan in clean Markdown.
"""

    response = llm.invoke([
        SystemMessage(content="Create accurate, practical travel plans. Never invent missing information."),
        HumanMessage(content=prompt)
    ])

    draft = response.content

    return {
    "itinerary": draft,
    "approval_request": draft,
    "approved": "pending",
    "messages": [AIMessage(content="Draft itinerary created. Awaiting human review.")],
    "llm_calls": state.get("llm_calls", 0) + 1
}


def human_review_agent(state: State) -> dict:
    decision = interrupt({
        "type": "itinerary_review",
        "message": "Please review this draft travel plan and approve it or request changes.",
        "approval_request": state.get("approval_request", "")
    })

    if not isinstance(decision, dict):
        raise ValueError("Human review must return an approval decision.")

    approved = decision.get("approved", False)
    feedback = str(decision.get("feedback", "")).strip()

    if not isinstance(approved, bool):
        raise ValueError("The approved value must be a boolean.")

    if not approved and not feedback:
        feedback = "Please revise the itinerary."

    return {
        "approved": "yes" if approved else "no",
        "human_feedback": feedback,
        "messages": [AIMessage(content="Itinerary approved." if approved else "Changes requested.")]
    }



def final_response_agent(state: State) -> dict:
    if state.get("guardrail_blocked", False):
        reason = state.get("final_response") or "This request is outside VOYAGE's travel-planning scope."
        return {
            "final_response": reason,
            "messages": [AIMessage(content=reason)],
            "llm_calls": state.get("llm_calls", 0)
        }

    if state.get("approved") != "yes":
        raise ValueError("The itinerary must be approved before finalizing.")

    prompt = f"""
You are the final response agent for VOYAGE.

The user has approved the travel itinerary draft.

Original user request:
{state["query"]}

Approved itinerary:
{state.get("itinerary", "")}

Budget assessment:
{state.get("budget_results", "")}

Produce the final, polished, user-ready travel plan.

Instructions:
1. Preserve the approved itinerary's recommendations and structure.
2. Improve clarity, organization and readability without changing
   the substance of the approved plan.
3. Include the budget assessment where relevant.
4. Never invent flight details, hotel prices, availability or weather data.
5. Clearly label estimates and information that has not been verified.
6. Return the complete travel plan in clean Markdown.
"""

    result = llm_text("You produce accurate, polished, user-ready travel plans.", prompt)

    return {
        "final_response": result,
        "messages": [AIMessage(content="Final approved travel plan generated.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


