import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from src.services.base import BaseService  # o da dove la importi tu



class WeatherForecastService(BaseService):
    def __init__(self, api_key: str, location: str = "Milan", rain_threshold: int = 50):
        super().__init__()
        self.api_key = api_key
        self.location = location
        self.rain_threshold = rain_threshold

    def execute(self, data: Dict, dr_type: str = None, attribute: str = None) -> Dict[str, Any]:
        # Build the WeatherAPI request URL with location and 2-day forecast
        url = (
            f"http://api.weatherapi.com/v1/forecast.json?key={self.api_key}"
            f"&q={self.location}&days=2&aqi=no&alerts=no"
        )
        
        # Make the HTTP request and parse the JSON
        response = requests.get(url)
        forecast = response.json()

        # Get the current time and calculate the next 3 full hours
        now = datetime.now()
        target_hours = [(now + timedelta(hours=i)).strftime("%Y-%m-%d %H:00") for i in range(1, 4)]

        # Combine hourly forecasts from today and tomorrow
        all_hours = []
        for day in forecast["forecast"]["forecastday"]:
            all_hours.extend(day["hour"])

        # Select only the hours that match the 3 future time targets
        selected = [
            hour for hour in all_hours
            if hour["time"] in target_hours
        ]

        # If no forecast found for those hours, return error
        if not selected:
            return {"status": "error", "reason": "no matching hours"}

        # Compute the average chance of rain over the 3 hours
        total = sum(int(hour.get("chance_of_rain", 0)) for hour in selected)
        average = total / len(selected)

        # Decide whether to water or skip based on the threshold
        decision = "water" if average < self.rain_threshold else "skip"

        # Return decision and data for logging or further use
        return {
            "status": "ok",
            "decision": decision,
            "chance_of_rain_avg": average,
            "hours": [h["time"] for h in selected],
            "location": self.location
    }



if __name__ == "__main__":
    service = WeatherForecastService(api_key="05418e63cb684a3a8f2135050250205", location="Milano")
    result = service.execute({})
    print(result)
