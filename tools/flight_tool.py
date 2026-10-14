
import os
import csv
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.apilayer.net/aviationstack/v1/flights"
AIRPORTS_FILE = Path(__file__).resolve().parent.parent / "airports.csv"



def find_airport(city_name):
    """Find airports by an exact city or municipality name."""
    city_name = city_name.strip().casefold()
    matches = []

    with open(AIRPORTS_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for airport in reader:
            iata = (airport.get("iata_code") or "").strip()
            municipality = (airport.get("municipality") or "").strip()
            scheduled = (airport.get("scheduled_service") or "").strip().lower()

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


def extract_route(query):
    """Extract the origin and destination from 'from X to Y'."""
    query = query.casefold()

    if " from " not in f" {query} " or " to " not in f" {query} ":
        return None, None

    after_from = query.split(" from ", 1)[1]
    origin_text, destination_text = after_from.split(" to ", 1)

    # Remove the extra details that follow the destination.
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
        return None, None

    return origin_airports[0]["iata"], destination_airports[0]["iata"]



def search_flights(query):
    """Search flights using dynamically looked-up airport codes."""
    access_key = os.getenv("AVIATIONSTACK_API_KEY")

    if not access_key:
        return "Error: AVIATIONSTACK_API_KEY is missing from .env."

    dep_iata, arr_iata = extract_route(query)

    if not dep_iata or not arr_iata:
        return (
            "Could not identify both airports. Please write your request "
            "like: 'Plan a trip from Raipur to Jaipur'."
        )

    params = {
        "access_key": access_key,
        "dep_iata": dep_iata,
        "arr_iata": arr_iata,
        "limit": 5
    }

    try:
        response = requests.get(API_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            return f"AviationStack API error: {data['error']}"

        flights = data.get("data", [])

        if not flights:
            return (
                f"No flights were returned for {dep_iata} to {arr_iata}. "
                "This does not necessarily mean no flights operate on this route."
            )

        results = []

        for flight in flights:
            airline = flight.get("airline") or {}
            departure = flight.get("departure") or {}
            arrival = flight.get("arrival") or {}
            flight_info = flight.get("flight") or {}

            results.append(
                f"Airline: {airline.get('name', 'Unknown')}\n"
                f"Flight: {flight_info.get('iata', 'Unknown')}\n"
                f"From: {departure.get('airport', 'Unknown')} "
                f"({departure.get('iata', dep_iata)})\n"
                f"To: {arrival.get('airport', 'Unknown')} "
                f"({arrival.get('iata', arr_iata)})\n"
                f"Departure: {departure.get('scheduled', 'Unavailable')}\n"
                f"Arrival: {arrival.get('scheduled', 'Unavailable')}\n"
                f"Status: {flight.get('flight_status', 'Unknown')}"
            )

        return "\n\n".join(results)

    except requests.RequestException as error:
        return f"Flight API request failed: {error}"
    except ValueError:
        return "Error: The flight API returned invalid JSON."
