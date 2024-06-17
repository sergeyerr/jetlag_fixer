import requests
from datetime import datetime
from langchain.tools import BaseTool, StructuredTool, tool
import os
from dotenv import load_dotenv, find_dotenv
from typing import Optional, Type
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
# Import things that are needed generically
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import ToolException

_ = load_dotenv(find_dotenv())

RAPID_API_KEY = os.environ['RAPID_API_KEY']
RAPID_API_HOST = os.environ['RAPID_API_HOST']

class FlightInfoInput(BaseModel):
    flight_number: str = Field(description="The flight number in the format of a carrier code followed by a numeric part (e.g., 'AA100').")
    search_date: Optional[datetime] = Field(default=None, description="The date and time to search for the next available fligh")

class FlightInfoTool(BaseTool):
    name = "flight_info_tool"
    description = "Fetches the next available flight information for a given flight number using the RapidAPI Flight Info API"
    args_schema: Type[BaseModel] = FlightInfoInput

    def _run(
        self, flight_number: str, search_date: Optional[datetime] = None, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Fetches the next available flight information for a given flight number using the RapidAPI Flight Info API.

        This function retrieves the next available flight within the current date and up to 30 days ahead from the given date (if provided, otherwise - current time).

        Parameters:
        flight_number (str): The flight number in the format of a carrier code followed by a numeric part (e.g., 'AA100').
        search_date (datetime): The date and time to search for the next available flight.

        Returns:
        dict: A dictionary containing the departure date, departure time, departure airport, arrival date, arrival time, and arrival airport of the flight.
            Returns None if no flights are found.
            Returns an error message if there is an issue with the API request.
        """
        # can't search for flights in the past
        if not search_date or search_date < datetime.now(search_date.tzinfo):
            search_date = datetime.now()

        search_date_str = search_date.strftime('%Y-%m-%d')

        base_url = f"https://{RAPID_API_HOST}/flights/number/{flight_number}/{search_date_str}"
        
        # Construct the query parameters
        params = {
            'withAircraftImage': 'false',
            'withLocation': 'false'
        }
        
        headers = {
            'x-rapidapi-host': RAPID_API_HOST,
            'x-rapidapi-key': RAPID_API_KEY
        }
        
        # Request flight information
        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ToolException(f"No flights found for the given flight number.")
        
        closest_flight = data[0]
        
        
        flight_info = {
            'departure_date': closest_flight['departure']['scheduledTime']['local'],
            'departure_airport': closest_flight['departure']['airport']['iata'],
            'arrival_date': closest_flight['arrival']['scheduledTime']['local'] if "scheduledTime" in closest_flight['arrival'] else "N/A",
            'arrival_airport': closest_flight['arrival']['airport']['iata'],
        }
        
        #parse the date and time from format 2024-06-16 22:55+03:00 to datetime
        flight_info['departure_date'] = datetime.strptime(flight_info['departure_date'], '%Y-%m-%d %H:%M%z')
        flight_info['arrival_date'] = datetime.strptime(flight_info['arrival_date'], '%Y-%m-%d %H:%M%z') if flight_info['arrival_date'] != "N/A" else "N/A"
        return flight_info

if __name__ == "__main__":
    # Usage examples
    tool = FlightInfoTool(handle_tool_error=True)
    print(tool.run({'flight_number': 'XQ133'}))
   #print(tool.run({'flight_number': 'AA100', "search_date" :datetime(2024, 6, 10, 12, 0)}))
    #print(tool.run({'flight_number': 'HEHMDA228', "search_date" :datetime(2024, 6, 10, 12, 0)}))
