import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from .base import BaseService 
from copy import copy
import logging

logger = logging.getLogger(__name__)

FORECAST_COOLDOWN_HR = 3
FAIL_TOLERANCE = 3
DELTA_SKIP = 2.5
HUMIDITY_THRESHOLD = 20.0
PROB_RAIN_THRESHOLD = 50.0
NOTIFICATION_COOLDOWN_MIN = 15

class WateringManagement(BaseService):
    def __init__(self):
        super().__init__()
        self.name = "Watering"
        self.api_key = "05418e63cb684a3a8f2135050250205"
        self.location = "Cagliari"
        self.rain_threshold = PROB_RAIN_THRESHOLD
        self.humidity_threshold = HUMIDITY_THRESHOLD
        self.forecast_cooldown_hr = FORECAST_COOLDOWN_HR
        self.delta_skip_hr = DELTA_SKIP
        self.notification_cooldown_min = NOTIFICATION_COOLDOWN_MIN

    def configure(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", self.api_key)
        self.location = config.get("location", self.location)
        self.outdoor = config.get("outdoor", False)
        self.rain_threshold = config.get("rain_threshold", self.rain_threshold)
        self.forecast_cooldown_hr = config.get("forecast_cd_hr", self.forecast_cooldown_hr)
        self.delta_skip_hr = config.get("delta_skip_hr", self.delta_skip_hr)

    def execute(self, plant_id: str, data: Dict, context: Dict[str, Any]) -> Dict[str, Any]:
        db = context["DB_SERVICE"]
        plant = db.get_dr("plant", plant_id)
        metadata = plant.get("metadata", {})
        status = copy(metadata.get("auto_watering_status", {}))
        now = datetime.utcnow()
        req_action = "0"

        logger.info(f"[{plant_id}] 🔍 Esecuzione WateringManagement – tipo: {data['type']} – valore: {data['value']}")

        if plant["profile"].get("outdoor", False) and plant["profile"].get("auto_watering", False):
            last_forecast = status.get("last_forecast")
            if not isinstance(last_forecast, datetime):
                last_forecast = now - timedelta(hours=10)

            if now - last_forecast >= timedelta(hours=self.forecast_cooldown_hr):
                logger.info(f"[{plant_id}] 🌤️ Forecast scaduto, aggiorno le previsioni meteo...")
                status["last_forecast"] = now
                prediction = self.get_forecast(now)
                logger.info(f"[{plant_id}] 📈 Probabilità pioggia nelle prossime ore: {prediction.get('chance_of_rain', '?')}%")

                if prediction.get("chance_of_rain", 0) > self.rain_threshold and not status.get("skip_pred", False):
                    logger.info(f"[{plant_id}] ☔ Pioggia prevista → disabilito autowatering")
                    status["disable_aw"] = True
                else:
                    logger.info(f"[{plant_id}] 🌤️ Nessuna pioggia significativa → watering abilitato")
                    status["disable_aw"] = False

                status["skip_pred"] = False

        if data["type"] != "humidity":
            if status != metadata.get("auto_watering_status", {}):
                metadata["auto_watering_status"] = status
                plant["metadata"] = metadata
                db.update_dr("plant", plant_id, plant)
            return {"action": req_action}

        humidity = data["value"]
        ts = data["timestamp"]
        if not isinstance(ts, datetime):
            ts = now  # fallback

        if humidity >= self.humidity_threshold:
            logger.info(f"[{plant_id}] 💧 Umidità sufficiente ({humidity}%) → nessuna azione")
            if status != metadata.get("auto_watering_status", {}):
                metadata["auto_watering_status"] = status
                plant["metadata"] = metadata
                db.update_dr("plant", plant_id, plant)
            return {"action": req_action}

        last_warning_ts = plant.get("metadata", {}).get("last_warning_ts")
        if not isinstance(last_warning_ts, datetime):
            last_warning_ts = now - timedelta(hours=10)
        
        
        
        if not plant["profile"].get("auto_watering", False):
            if now - last_warning_ts  >= timedelta(minutes=self.notification_cooldown_min):
                last_warning_ts = now
                logger.info(f"[{plant_id}] 🛑 AutoWatering disattivato → invia notifica")
                req_action = "notify"
            else:
                logger.info(f"[{plant_id}] 🛑 AutoWatering disattivato → notifica in CD")
        elif not plant["profile"].get("outdoor", False):
            logger.info(f"[{plant_id}] 🪴 Pianta indoor → procedo con annaffiatura")
            req_action = "water"
        elif not status.get("disable_aw", False):
            logger.info(f"[{plant_id}] ✅ AutoWatering abilitato → procedo con annaffiatura")
            req_action = "water"
        else:
            last_forecast = status.get("last_forecast")
            if not isinstance(last_forecast, datetime):
                last_forecast = now - timedelta(hours=10)
            
            if ts - last_forecast >= timedelta(hours=self.delta_skip_hr):
                logger.info(f"[{plant_id}] ⏱️ Timeout superato → forzo annaffiatura e skip_pred = True")
                status["skip_pred"] = True
                req_action = "water"
            else:
                logger.info(f"[{plant_id}] 🚫 Forecast recente → annaffiatura bloccata")
        
        if status != metadata.get("auto_watering_status", {}) or plant.get("metadata", {}).get("last_warning_ts") != last_warning_ts:
            metadata["auto_watering_status"] = status
            if plant.get("metadata", {}).get("last_warning_ts") != last_warning_ts:
                metadata["last_warning_ts"] = last_warning_ts
            plant["metadata"] = metadata
            db.update_dr("plant", plant_id, plant)

        return {"action": req_action}

    def get_forecast(self, now: datetime) -> Dict[str, Any]:
        url = (
            f"http://api.weatherapi.com/v1/forecast.json?key={self.api_key}"
            f"&q={self.location}&days=2&aqi=no&alerts=no"
        )
        response = requests.get(url)
        forecast = response.json()

        target_hours = [(now + timedelta(hours=i)).strftime("%Y-%m-%d %H:00") for i in range(1, 4)]
        all_hours = []
        for day in forecast.get("forecast", {}).get("forecastday", []):
            all_hours.extend(day.get("hour", []))

        selected = [hour for hour in all_hours if hour.get("time") in target_hours]
        if not selected:
            logger.warning("⚠️ Nessuna previsione trovata nelle prossime ore")
            return {"status": "error", "reason": "no matching hours"}

        max_prob = max(int(hour.get("chance_of_rain", 0)) for hour in selected)
        return {
            "status": "ok",
            "chance_of_rain": max_prob,
            "hours": [h["time"] for h in selected],
            "location": self.location
        }

