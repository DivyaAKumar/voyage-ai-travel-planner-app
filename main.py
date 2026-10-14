import os 
from typing import TypedDict, Annotated
import operator
import psycopg
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage,SystemMessage
from langchain_openai import ChatOpenAI
import uuid
from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights, find_airport
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI()

DATABASE_URL = os.getenv('DATABASE_URL')

class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    query : str
    flight_results : str
    hotel_results : str
    itinerary: str
    llm_calls: int


def flight_agent(state: State) -> State:
    query = state['query']
    flight_data = search_flights(query)
    return{
        'flight_results': flight_data,
        'messages': [
            AIMessage(content = 'Flight results fetched')
        ],
        'llm_calls': state.get('llm_calls',0) +1
    }


def hotel_agent(state: State) -> State:
    query = f"""
Find hotels for this travel request:

{state['query']}

Identify the actual destination from the request.
Search for hotels only in that destination.
Prioritize hotel names, locations, prices, ratings,
amenities, and official booking links when available.

Do not invent prices, ratings, or availability.
"""

    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



def itenary_agent(state: State) -> State:
    prompt = f"""
You are an expert travel itinerary planner.

Create a practical, personalized sightseeing itinerary based on
the user's travel request.

User's Travel Request:
{state['query']}

Instructions:
- Identify the destination, trip duration, travel dates, and interests.
- Create a day-by-day sightseeing plan.
- Divide each day into morning, afternoon, and evening.
- Group nearby attractions together to minimize travel time.
- Include suitable local food experiences and reasonable breaks.
- Consider arrival and departure times only if they are provided.
- Do not invent travel dates or arrival and departure times.
- Do not recommend specific flights or hotels.
- Do not invent ticket prices or claim that bookings have been made.
- If important details are missing, state the assumptions clearly.

Return a well-organized itinerary in Markdown with:
1. Trip overview
2. Day-by-day sightseeing itinerary
3. Food and local experiences
4. Transportation and practical tips
5. Missing information or assumptions
"""

    response = llm.invoke([
        SystemMessage(
            content="You create practical sightseeing itineraries."
        ),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




def final_agent(state: State) -> State:
    final_prompt = f"""
You are the final AI travel planning agent.

Create one complete, practical, personalized travel plan by combining
the original request, flight search results, hotel search results,
and sightseeing itinerary.

USER'S ORIGINAL REQUEST:
{state['query']}

FLIGHT SEARCH RESULTS:
{state['flight_results']}

HOTEL SEARCH RESULTS:
{state['hotel_results']}

SIGHTSEEING ITINERARY:
{state['itinerary']}

INSTRUCTIONS:

1. Understand the user's requirements
- Preserve the origin, destination, duration, budget, and preferences
  from the original request.
- Do not silently change the requested destination.

2. Flight recommendations
- Summarize relevant flight results only when they are available.
- Include airline, airports, flight number, and timings when provided.
- If no relevant flights were returned, clearly say that flight details
  could not be verified.
- Never invent fares, schedules, or booking confirmations.

3. Hotel recommendations
- Summarize relevant hotels from the supplied search results.
- Include names, locations, prices, ratings, amenities, and links only
  when supported by those results.
- If no suitable hotels can be verified, say so.
- Never invent hotel prices, availability, or ratings.

4. Sightseeing itinerary
- Incorporate the itinerary supplied by the itinerary agent.
- Preserve its day-by-day organization.
- Adapt the schedule to verified arrival and departure information
  when available.
- Do not invent flight timings.

5. Budget breakdown
- Cover flights, accommodation, local transport, food, activities,
  and miscellaneous expenses.
- Use actual costs only when supplied by the available results.
- Clearly label any reasonable estimates.
- Calculate a total only when sufficient cost information is available.
- Never claim the trip fits the budget without adequate evidence.

6. Missing information and reliability
- Identify missing travel dates, prices, or other essential details.
- Distinguish verified search results from general recommendations.
- Do not claim that flights or hotels have been booked.

OUTPUT FORMAT:

# Your Personalized Travel Plan

## 1. Trip Overview
Summarize the origin, destination, duration, dates, travelers, and budget.
Use "Not specified" for missing information.

## 2. Flight Options
Present available flight information or explain what could not be verified.

## 3. Hotel Recommendations
Present relevant hotel options and their available details.

## 4. Day-by-Day Itinerary
Present the sightseeing plan, meals, and practical transportation notes.

## 5. Budget Breakdown
List the available costs, estimates, and unavailable amounts separately.

## 6. Important Travel Tips
Provide relevant practical advice.

## 7. Missing Information
List the details needed to make the plan more accurate.

Return only the finished travel plan in clean Markdown.
"""

    response = llm.invoke([
        SystemMessage(
            content=(
                "You combine travel research and itinerary information "
                "into one accurate final travel plan."
            )
        ),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [
            AIMessage(content=response.content)
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

graph = StateGraph(State)

graph.add_node('flight_agent', flight_agent)
graph.add_node('hotel_agent', hotel_agent)
graph.add_node('itinerary_agent', itenary_agent)
graph.add_node('final_agent', final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

conn = psycopg.connect(DATABASE_URL, autocommit=True)
checkpointer = PostgresSaver(conn)
checkpointer.setup()

app = graph.compile(checkpointer=checkpointer)

if __name__ == "__main__":
    config = {
        'configurable': {
            'thread_id': 'user_divya'
        }
    }

    user_input = input("Enter your travel request: ")

    result = app.invoke(
        {
            'messages': [HumanMessage(content=user_input)],
            'query': user_input,
            'flight_results': "",
            'hotel_results': "",
            'itinerary': "",
            "llm_calls": 0
         },
         config=config
    )

    print('\n FINAL RESPONSE: \n')
    for msg in result['messages']:
        print(msg.content)