import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from dateutil import parser  # Manca questo import!
from .base import BaseService 

FORECAST_COOLDOWN_HR = 24  # default: 24 ore
FAIL_TOLERANCE = 3        # default: 3 tentativi


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
    """Decision engine for automatic irrigation."""

    def __init__(self):
        super().__init__()
        self.name = "AutoWateringService"

    def configure(self, config: Dict[str, Any]):
        global FORECAST_COOLDOWN_HR, FAIL_TOLERANCE
        FORECAST_COOLDOWN_HR = config.get("forecast_cd_hr", FORECAST_COOLDOWN_HR)
        FAIL_TOLERANCE       = config.get("fail_tolerance", FAIL_TOLERANCE)

    def execute(self, data: Dict, context: Dict[str, Any]) -> tuple[str, str]:

        db       = context["db"]
        forecast = context.get("weather_result")
        now      = datetime.utcnow()

        profile  = data.get("profile", {})
        metadata = data.get("metadata", {}).copy()
        autow    = metadata.get("auto_watering_status", {}).copy()
        plant_id = data.get("_id", "unknown")

        last_block = autow.get("last_block")
        last_water = autow.get("last_water")
        forecast_blocked = last_block and (
            now - last_block < timedelta(hours=FORECAST_COOLDOWN_HR))

        consec_failed = autow.get("consec_fai9led", 0)
        reset_failed = now - last_water < timedelta(minutes=5)


        # ─── FAIL‑TOLERANCE GLOBALE (vale indoor & outdoor) ────────────
        if consec_failed >= FAIL_TOLERANCE:
            return "notification", "possible_irrigation_failure"

        is_outdoor = profile.get("outdoor", False)

        # ─── INDOOR ────────────────────────────────────────────────────
        if not is_outdoor:
            self._save_action(db, plant_id, metadata, autow, now, reset_failed)
            return "water", "indoor"

        # ─── OUTDOOR ───────────────────────────────────────────────────
        if forecast_blocked:
            return "no_water", "forecast_cooldown"
        if not forecast or forecast.get("status") != "ok":
            return "notification", "weather_service_failed"
        if forecast["decision"] == "skip":
            autow["last_block"] = now  # salviamo direttamente datetime
            self._persist_metadata(db, plant_id, metadata | {"autowatering": autow})
            return "no_water", "weather_block"

        # forecast == water
        self._save_action(db, plant_id, metadata, autow, now, reset_failed)
        return "water", "weather_allowed"

    # helpers -----------------------------------------------------------
    def _iso(self, dt: datetime) -> str:
        return dt.replace(microsecond=0).isoformat()

    def _save_action(self, db, plant_id, metadata, autow, when: datetime, reset_failed: bool):
        autow["last_water"] = when  # salviamo direttamente datetime
        autow["consecutive_watering"] = autow.get("consecutive_watering", 0) + 1
        if reset_failed:
            autow["consecutive_failed_irrigations"] = 0
        metadata["autowatering"] = autow
        self._persist_metadata(db, plant_id, metadata)

    def _persist_metadata(self, db, plant_id, new_md):
        plant = db.get_dr("plant", plant_id)
        if not plant:
            return
        plant["metadata"] = plant.get("metadata", {}) | new_md
        db.update_dr("plant", plant_id, plant)




