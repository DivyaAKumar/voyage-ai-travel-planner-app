
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
print("API key loaded:", API_KEY is not None)
print("API key length:", len(API_KEY) if API_KEY else 0)


def search_flights(query):
    url = "https://api.apilayer.net/aviationstack/v1/flights"

    params = {
        "access_key": API_KEY,
        "limit": 5
    }

    response = requests.get(url, params=params, timeout=30)

    print("HTTP Status Code:", response.status_code)
    print("API response:", response.text)

    response.raise_for_status()

    data = response.json()

    # Print the entire JSON response
    print("\n========== COMPLETE API RESPONSE ==========\n")
    print(json.dumps(data, indent=4, ensure_ascii=False))

    return data


if __name__ == "__main__":
    search_flights("")
