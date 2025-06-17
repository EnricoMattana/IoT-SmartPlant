import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from .base import BaseService 
from copy import copy
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import statistics

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
        self.name = "WateringManagement"
        self.api_key = "05418e63cb684a3a8f2135050250205"
        self.location = "Cagliari"
        self.rain_threshold = PROB_RAIN_THRESHOLD
        self.humidity_threshold = HUMIDITY_THRESHOLD
        self.forecast_cooldown_hr = FORECAST_COOLDOWN_HR
        self.delta_skip_hr = DELTA_SKIP
        self.notification_cooldown_min = NOTIFICATION_COOLDOWN_MIN
    def configure(self, config: Dict[str, Any]):
        preset_defaults = {}

        preset = config.get("preset")
        if preset == "fragile":
            preset_defaults = {
                "rain_threshold": 25,
                "humidity_threshold": 60,
                "delta_skip_hr": 1,
                "forecast_cooldown_hr": 3,
                "notification_cooldown_min": 15,
            }
        elif preset == "normal":
            preset_defaults = {
                "rain_threshold": 60,
                "humidity_threshold": 30,
                "delta_skip_hr": 3,
                "forecast_cooldown_hr": 4,
                "notification_cooldown_min": 30,
            }
        elif preset == "resilient":
            preset_defaults = {
                "rain_threshold": 80,
                "humidity_threshold": 20,
                "delta_skip_hr": 6,
                "forecast_cooldown_hr": 6,
                "notification_cooldown_min": 60,
            }
        

        # Applica i valori effettivi: preset + override solo se presente nel config
        self.api_key = config.get("api_key", self.api_key)
        self.location = config.get("location", self.location)
        self.outdoor = config.get("outdoor", False)
        self.rain_threshold = config.get("rain_threshold", preset_defaults.get("rain_threshold", self.rain_threshold))
        self.humidity_threshold = config.get("humidity_threshold", preset_defaults.get("humidity_threshold", self.humidity_threshold))
        self.forecast_cooldown_hr = config.get("forecast_cd_hr", preset_defaults.get("forecast_cooldown_hr", self.forecast_cooldown_hr))
        self.delta_skip_hr = config.get("delta_skip_hr", preset_defaults.get("delta_skip_hr", self.delta_skip_hr))
        self.notification_cooldown_min = config.get("notification_cd_min", preset_defaults.get("notification_cooldown_min", self.notification_cooldown_min))

    def execute(self, data: Dict, **kwargs) -> Dict[str, Any]:
        plant_id = kwargs.get("plant_id")
        context=kwargs.get("context")
        db=context["DB_SERVICE"]
        print(data)
        print(data.keys())
        if not plant_id:
            raise ValueError("plant_id mancante")

        plant = None
        for dr in data["digital_replicas"]:
            if dr.get("_id") == plant_id and dr.get("type") == "plant":
                plant = dr
                break

        if plant is None:
            raise ValueError(f"⚠️ Nessuna DR di tipo 'plant' trovata con id {plant_id} nel DT")

        metadata = plant.get("metadata", {})
        status = metadata.get("auto_watering_status", {})
        measurement=kwargs.get("measurement")
        now = datetime.utcnow()
        req_action = "0"
        print( self.rain_threshold)
        logger.info(f"[{plant_id}] 🔍 Esecuzione WateringManagement – tipo: {measurement['type']} – valore: {measurement['value']}")

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

        if measurement["type"] != "humidity":
            if status != metadata.get("auto_watering_status", {}):
                metadata["auto_watering_status"] = status
                plant["metadata"] = metadata
                db.update_dr("plant", plant_id, plant)
            return {"action": req_action}

        humidity = measurement["value"]
        ts = measurement["timestamp"]
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
                last_forecast = now - timedelta(hours=100)
            
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
    


class GardenHistoryService(BaseService):
    """
    Analizza lo storico di umidità e luce per ciascuna pianta nel giardino
    e restituisce: max/min con timestamp, media, deviazione standard ecc.
    Può restituire tutto il giardino o solo una pianta specifica.
    """
    def __init__(self):
        super().__init__()
    def execute(self, data: Dict, range: str = "giorno", plant_name: Optional[str] = None) -> Union[List[Dict], Dict]:
        if 'digital_replicas' not in data:
            raise ValueError("Digital Twin privo di digital_replicas")

        now = datetime.utcnow()
        if range == "giorno":
            start = now - timedelta(days=1)
        elif range == "settimana":
            start = now - timedelta(days=7)
        elif range == "mese":
            start = now - timedelta(days=30)
        else:
            raise ValueError(f"Intervallo '{range}' non supportato. Usa: giorno, settimana, mese")

        end = now

        if plant_name:
            dr = next(
                (dr for dr in data.get("digital_replicas", [])
                 if dr.get("type") == "plant" and dr.get("profile", {}).get("name", "").lower() == plant_name.lower()),
                None
            )
            if not dr:
                return {"error": f"Nessuna pianta trovata con nome '{plant_name}'"}
            drs = [dr]
        else:
            drs = [dr for dr in data['digital_replicas'] if dr['type'] == 'plant']

        results = []

        for dr in drs:
            name = dr.get("profile", {}).get("name", dr.get("_id", "unknown"))
            measurements = dr.get("data", {}).get("measurements", [])
            valid = [m for m in measurements if start <= datetime.fromisoformat(m["timestamp"]) <= end]

            hums = [m for m in valid if m['type'] == 'humidity']
            lights = [m for m in valid if m['type'] == 'light']

            plant_stats = {
                "plant": name,
                "humidity": {},
                "light": {},
                "measurements": valid if plant_name else None
            }

            if hums:
                hum_values = [m['value'] for m in hums]
                max_h = max(hums, key=lambda m: m['value'])
                min_h = min(hums, key=lambda m: m['value'])
                plant_stats["humidity"] = {
                    "max": max_h['value'],
                    "max_time": max_h['timestamp'],
                    "min": min_h['value'],
                    "min_time": min_h['timestamp'],
                    "mean": statistics.mean(hum_values),
                    "std": statistics.stdev(hum_values) if len(hum_values) > 1 else 0
                }

            if lights:
                light_values = [m['value'] for m in lights]
                plant_stats["light"] = {
                    "mean": statistics.mean(light_values),
                    "max": max(light_values),
                    "min": min(light_values),
                    "std": statistics.stdev(light_values) if len(light_values) > 1 else 0
                }

            if plant_name:
                return plant_stats
            results.append(plant_stats)

        return results


class GardenStatusService(BaseService):
    """
    Ritorna lo stato attuale (ultima umidità e luce) di tutte le piante nel DT
    o solo di una specifica pianta se specificata.
    """
    def __init__(self):
        super().__init__()
    def execute(self, data: Dict, plant_name: Optional[str] = None) -> Union[List[Dict], Dict]:
        if plant_name:
            dr = next(
                (dr for dr in data.get("digital_replicas", [])
                 if dr.get("type") == "plant" and dr.get("profile", {}).get("name", "").lower() == plant_name.lower()),
                None
            )
            if not dr:
                return {"error": f"Nessuna pianta trovata con nome '{plant_name}'"}
            drs = [dr]
        else:
            drs = [dr for dr in data.get("digital_replicas", []) if dr.get("type") == "plant"]

        results = []
        for dr in drs:
            name = dr.get("profile", {}).get("name", dr.get("_id"))
            measures = dr.get("data", {}).get("measurements", [])

            latest_h = None
            latest_l = None

            for m in sorted(measures, key=lambda x: x["timestamp"], reverse=True):
                if m["type"] == "humidity" and not latest_h:
                    latest_h = m
                if m["type"] == "light" and not latest_l:
                    latest_l = m
                if latest_h and latest_l:
                    break

            plant_status = {
                "plant": name,
                "humidity": latest_h["value"] if latest_h else None,
                "light": latest_l["value"] if latest_l else None,
                "last_updated": latest_h["timestamp"] if latest_h else latest_l["timestamp"] if latest_l else None
            }

            if plant_name:
                return plant_status
            results.append(plant_status)

        return results
