
from tools.flight_tool import extract_route, search_flights

query = (
    "plan a 3 day trip from Raipur to Jaipur "
    "including flights, hotels and sightseeing under 1 lakh"
)

print("Detected route:", extract_route(query))
print()
print(search_flights(query))
