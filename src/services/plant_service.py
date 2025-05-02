import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from .base import BaseService 



class WeatherForecastService(BaseService):
    def __init__(self):
        super().__init__()
        self.name = "WeatherForecastService"
        self.api_key = "05418e63cb684a3a8f2135050250205"
        self.location = "Milan"
        self.rain_threshold = 50

    def configure(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.location = config.get("location", "Milan")
        self.rain_threshold = config.get("rain_threshold", 50)

    def execute(self, data: Dict, dr_type: str = None, attribute: str = None) -> Dict[str, Any]:
        url = (
            f"http://api.weatherapi.com/v1/forecast.json?key={self.api_key}"
            f"&q={self.location}&days=2&aqi=no&alerts=no"
        )
        response = requests.get(url)
        forecast = response.json()

        now = datetime.now()
        target_hours = [(now + timedelta(hours=i)).strftime("%Y-%m-%d %H:00") for i in range(1, 4)]

        all_hours = []
        for day in forecast["forecast"]["forecastday"]:
            all_hours.extend(day["hour"])

        selected = [hour for hour in all_hours if hour["time"] in target_hours]

        if not selected:
            return {"status": "error", "reason": "no matching hours"}

        total = sum(int(hour.get("chance_of_rain", 0)) for hour in selected)
        average = total / len(selected)
        decision = "water" if average < self.rain_threshold else "skip"

        return {
            "status": "ok",
            "decision": decision,
            "chance_of_rain_avg": average,
            "hours": [h["time"] for h in selected],
            "location": self.location
        }



class AutoWateringService(BaseService):
    def __init__(self):
        super().__init__()
        self.name = "AutoWateringService"
        self.weather_service = WeatherForecastService()

    def configure(self, config: Dict[str, Any]):
        # Se vuoi passare la stessa config anche al weather_service
        self.weather_service.configure(config)

    def execute(self, data: Dict, dr_type: str = None, attribute: str = None) -> Dict[str, Any]:
        profile = data.get("profile", {})
        
        if not profile.get("auto_watering", False):
            return {
                "status": "ok",
                "decision": "skip",
                "reason": "auto_watering_disabled"
            }

        location = profile.get("location", "indoor").lower()

        if location == "indoor":
            return {
                "status": "ok",
                "decision": "water",
                "reason": "indoor_location"
            }

        weather_result = self.weather_service.execute(data)

        if weather_result.get("status") != "ok":
            return {
                "status": "error",
                "reason": "weather_service_failed",
                "details": weather_result
            }

        return {
            "status": "ok",
            "decision": weather_result["decision"],
            "weather": weather_result
        }

