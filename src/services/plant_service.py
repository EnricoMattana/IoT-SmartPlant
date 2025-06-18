import requests
from typing import Dict, Any
from .base import BaseService 
from copy import copy
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Union
import statistics
from timezonefinder import TimezoneFinder
import pytz

logger = logging.getLogger(__name__)

FORECAST_COOLDOWN_HR = 3
DELTA_SKIP = 2.5
HUMIDITY_THRESHOLD = 20.0
PROB_RAIN_THRESHOLD = 50.0
NOTIFICATION_COOLDOWN_MIN = 15
LAST_H_LIGHT = 0.1
class PlantManagement(BaseService):
    def __init__(self):
        super().__init__()
        self.name = "PlantManagement"
        self.api_key = "05418e63cb684a3a8f2135050250205"
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
                "light_threshold": 30
            }
        elif preset == "normal":
            preset_defaults = {
                "rain_threshold": 60,
                "humidity_threshold": 30,
                "delta_skip_hr": 3,
                "forecast_cooldown_hr": 4,
                "notification_cooldown_min": 30,
                "light_threshold": 20

            }
        elif preset == "resilient":
            preset_defaults = {
                "rain_threshold": 80,
                "humidity_threshold": 20,
                "delta_skip_hr": 6,
                "forecast_cooldown_hr": 6,
                "notification_cooldown_min": 60,
                "light_threshold": 10
            }
        

        # Applica i valori effettivi: preset + override solo se presente nel config
        self.rain_threshold = preset_defaults.get("rain_threshold")
        self.humidity_threshold = preset_defaults.get("humidity_threshold")
        self.forecast_cooldown_hr = preset_defaults.get("forecast_cooldown_hr")
        self.delta_skip_hr = preset_defaults.get("delta_skip_hr")
        self.notification_cooldown_min = preset_defaults.get("notification_cooldown_min")
        self.light_threshold = preset_defaults.get("light_threshold")

    def execute(self, data: Dict, **kwargs) -> Dict[str, Any]:
        plant_id = kwargs.get("plant_id")
        context = kwargs.get("context")
        db = context["DB_SERVICE"]
        dr_factory=context["DR_FACTORY"]
        duration=None
        if not plant_id:
            raise ValueError("plant_id mancante")

        plant = None
        for dr in data["digital_replicas"]:
            if dr.get("_id") == plant_id and dr.get("type") == "plant":
                plant = dr
                break

        if plant is None:
            raise ValueError(f"⚠️ Nessuna DR di tipo 'plant' trovata con id {plant_id} nel DT")

        preset = plant["profile"].get("preset")
        self.configure({"preset": preset})
        metadata = plant.get("metadata", {})
        status = metadata.get("management_info", {})
        measurement = kwargs.get("measurement")
        status.setdefault("pending_actions", [])
        now = datetime.utcnow()
        req_action = "0"

        logger.info(f"[{plant_id}] 🔍 Esecuzione PlantManagement – tipo: {measurement['type']} – valore: {measurement['value']}")

        last_forecast = status.get("last_forecast")
        if not isinstance(last_forecast, datetime):
            last_forecast = now - timedelta(hours=100)

        if now - last_forecast >= timedelta(hours=self.forecast_cooldown_hr):
            logger.info(f"[{plant_id}] 🌤️ Forecast scaduto, aggiorno le previsioni meteo...")
            status["last_forecast"] = now
            location = plant["profile"].get("location")
            prediction = self.get_forecast(now, location)

            status["sunrise_h"] = prediction["sunrise_h"].strftime("%H:%M") 
            status["sunset_h"]  = prediction["sunset_h"].strftime("%H:%M")
            status["Sunny"] = prediction["sunny"]
            if plant["profile"].get("outdoor") and plant["profile"].get("auto_watering"):
                logger.info(f"[{plant_id}] 📈 Probabilità pioggia nelle prossime ore: {prediction.get('chance_of_rain', '?')}%")
                if prediction.get("chance_of_rain", 0) > self.rain_threshold and not status.get("skip_pred", False):
                    logger.info(f"[{plant_id}] ☔ Pioggia prevista → disabilito autowatering")
                    status["disable_aw"] = True
                else:
                    logger.info(f"[{plant_id}] 🌤️ Nessuna pioggia significativa → watering abilitato")
                    status["disable_aw"] = False

                status["skip_pred"] = False

        if measurement["type"] == "light":
            timestamp = measurement["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
                print("replaced")
            profile = plant.get("profile", {})
            preset = profile.get("preset", "normal")

            all_meas = plant.get("data", {}).get("measurements", [])
            last_m = []
            for m in all_meas:
                if m.get("type") != "light":
                    continue
                ts = m.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                if ts >= timestamp - timedelta(hours=LAST_H_LIGHT):
                    last_m.append(m)

            print(status)
            sunrise_h = status.get("sunrise_h")   # stringa "HH:MM"
            sunset_h = status.get("sunset_h")     # stringa "HH:MM"
            sunny = status.get("Sunny", True)

            # 🕐 Cooldown (tempo ultimo avviso luce)
            last_warn_ts = status.get("last_warning_ts_l")
            if isinstance(last_warn_ts, str):
                last_warn_ts = datetime.fromisoformat(last_warn_ts) 

            should_send = False
            sunrise_ht = datetime.strptime(sunrise_h, "%H:%M").time()
            sunset_ht = datetime.strptime(sunset_h, "%H:%M").time()
            if measurement["type"] in status["pending_actions"]:
                status["pending_actions"].remove(measurement["type"])
            if last_m:
                avg = sum(m["value"] for m in last_m) / len(last_m)
                logger.info(f"[{plant_id}] 💡 Media luce (ultime 3h): {avg:.1f} (soglia {self.light_threshold}%)")

                if (
                    avg < self.light_threshold
                    and sunrise_ht and sunset_ht
                    and sunrise_ht <= now.time() <= sunset_ht
                    and sunny
                ):
                    if measurement["type"] not in status["pending_actions"]:
                            status["pending_actions"].append(measurement["type"])
                    if not last_warn_ts or (timestamp - last_warn_ts >= timedelta(minutes=self.notification_cooldown_min)):
                        should_send = True
                        status["last_warning_ts_l"] = now
                    else:
                        logger.info(f"[{plant_id}] ⏳ Notifica luce in cooldown")

            # 📩 Azione finale
            if should_send:
                req_action = "notify_light"

            # 💾 Salva sempre lo stato aggiornato
            plant_updated = dr_factory.update_dr(plant, {
                "metadata": {
                    "management_info": status
                }
            })
            db.update_dr("plant", plant_id, plant_updated)
            return {"action": req_action}

        # Umidità bassa → valuta irrigazione
        humidity = measurement["value"]
        ts = measurement["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
                
        if humidity >= self.humidity_threshold:
            dr_factory = context["DR_FACTORY"]
            plant_updated = dr_factory.update_dr(plant, {
                "metadata": {
                    "management_info": status
                }
            })
            if measurement["type"] in status["pending_actions"]:
                status["pending_actions"].remove(measurement["type"])
            db.update_dr("plant", plant_id, plant_updated)
            return {"action": req_action}

        last_warning_ts_h = status.get("last_warning_ts_h")
        if not isinstance(last_warning_ts_h, datetime):
            last_warning_ts_h = now - timedelta(hours=10)

        # === DECISIONE ===
        if not plant["profile"].get("auto_watering", False):
            if measurement["type"] not in status["pending_actions"]:
                status["pending_actions"].append(measurement["type"])
            if now - last_warning_ts_h >= timedelta(minutes=self.notification_cooldown_min):
                last_warning_ts_h = now
                logger.info(f"[{plant_id}] 🛑 AutoWatering disattivato → invia notifica")
                req_action = "notify_humidity"
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
                status["disable_aw"] = False
                req_action = "water"
            else:
                logger.info(f"[{plant_id}] 🚫 Forecast recente → annaffiatura bloccata")

        # Salva eventuali modifiche
        status["last_warning_ts_h"] = last_warning_ts_h
        metadata["management_info"] = status
        plant_updated = dr_factory.update_dr(plant, {
            "metadata": {
                "management_info": status
            }
        }) 
        db.update_dr("plant", plant_id, plant_updated)


        if req_action=="water":
            MAX_DURATION = 20
            MIN_DURATION = 10
            threshold = self.humidity_threshold
            target = threshold * 1.5

            delta = target - humidity
            full_range = threshold * 0.5

            factor = min(max(delta / full_range, 0), 1)

            # Interpolazione lineare tra MIN e MAX
            duration = int(MIN_DURATION + (MAX_DURATION - MIN_DURATION) * factor)*1000


        return {"action": req_action, "duration": duration}


    def get_forecast(self, now: datetime, location) -> Dict[str, Any]:
        url = (
            f"http://api.weatherapi.com/v1/forecast.json?key={self.api_key}"
            f"&q={location}&days=2&aqi=no&alerts=no"
        )
        response = requests.get(url)
        forecast = response.json()
        now = datetime.strptime(forecast["location"]["localtime"], "%Y-%m-%d %H:%M")
        target_hours = [(now + timedelta(hours=i)).strftime("%Y-%m-%d %H:00") for i in range(1, 4)]
        all_hours = []
        for day in forecast.get("forecast", {}).get("forecastday", []):
            all_hours.extend(day.get("hour", []))

        selected = [hour for hour in all_hours if hour.get("time") in target_hours]
        if not selected:
            logger.warning("⚠️ Nessuna previsione trovata nelle prossime ore")
            return {"status": "error", "reason": "no matching hours"}

        max_prob = max(int(hour.get("chance_of_rain", 0)) for hour in selected)

        # --- AGGIUNTE CONCORDATE ---
        astro = forecast.get("forecast", {}).get("forecastday", [{}])[0].get("astro", {})
        sunrise_h = astro.get("sunrise")  # esempio: "05:35 AM"
        sunset_h = astro.get("sunset")    # esempio: "09:04 PM"

        now_hour = now.strftime("%Y-%m-%d %H:00")
        current = next((h for h in all_hours if h.get("time") == now_hour), None)
        sunny = current.get("is_day") == 1 if current else None

        lat = forecast["location"]["lat"]
        lon = forecast["location"]["lon"]
        sunrise_utc = self.convert_local_hour_to_utc_str(sunrise_h, lat, lon)
        sunset_utc = self.convert_local_hour_to_utc_str(sunset_h, lat, lon)
        # --- FINE AGGIUNTE ---

        return {
            "status": "ok",
            "chance_of_rain": max_prob,
            "hours": [h["time"] for h in selected],
            "sunrise_h": sunrise_utc,
            "sunset_h": sunset_utc,
            "sunny": sunny,
    }

    def convert_local_hour_to_utc_str(self, time_str: str, lat: float, lon: float) -> str:
        """
        Converte un orario locale tipo "06:12 AM" nella sua ora UTC corrispondente come stringa "HH:MM"
        usando il fuso orario geografico calcolato da latitudine e longitudine.
        """

        # 1. Trova il nome del fuso orario (es. 'Europe/Rome') usando lat/lon
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=lat, lng=lon)
        if not timezone_str:
            raise ValueError("Fuso orario non trovato per le coordinate fornite")

        # 2. Parso l’orario ricevuto ("06:12 AM") in oggetto datetime.time
        local_time = datetime.strptime(time_str, "%I:%M %p").time()

        # 3. Combino la data di oggi (UTC) con quell’orario (es. 2025-06-17 + 06:12 AM)
        today = date.today()
        local_dt = datetime.combine(today, local_time)

        # 4. Assegno il fuso orario corretto alla data/ora (timezone-aware datetime)
        tz = pytz.timezone(timezone_str)
        localized_dt = tz.localize(local_dt)

        # 5. Converto il datetime localizzato in UTC
        utc_dt = localized_dt.astimezone(pytz.utc)

        # 6. Estraggo solo l’orario in formato stringa "HH:MM"
        return utc_dt.time()



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

            # ✅ Normalizza i timestamp per evitare TypeError
            valid = []
            for m in measurements:
                ts = m.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except Exception:
                        continue
                if start <= ts <= end:
                    m["timestamp"] = ts  # normalizza per output
                    valid.append(m)

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
                max_l = max(lights, key=lambda m: m['value'])
                min_l = min(lights, key=lambda m: m['value'])
                plant_stats["light"] = {
                    "max": max_l['value'],
                    "max_time": max_l['timestamp'],
                    "min": min_l['value'],
                    "min_time": min_l['timestamp'],
                    "mean": statistics.mean(light_values),
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


