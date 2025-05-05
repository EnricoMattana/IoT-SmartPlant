# utils.py

from src.application.telegram.handlers.command_handlers import send_humidity_alert_to_user
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
import logging
import asyncio
from flask import current_app
from asyncio import run_coroutine_threadsafe


logger = logging.getLogger(__name__)


def get_last_warning_ts(plant: dict) -> Optional[str]:
    return plant.get("metadata", {}).get("last_warning_ts")


def update_last_warning_ts(db_service, plant_id: str):
    now_iso = datetime.utcnow().isoformat()

    plant = db_service.get_dr("plant", plant_id)
    if not plant:
        logger.warning(f"⚠️ update_last_warning_ts: plant {plant_id} non trovata")
        return

    # 🔁 Merge safe dei metadata
    metadata = plant.get("metadata", {})
    metadata["last_warning_ts"] = now_iso
    plant["metadata"] = metadata

    db_service.update_dr("plant", plant_id, plant)
    logger.info(f"Updated last_warning_ts for plant {plant_id} to {now_iso}")


def is_cooldown_passed(last_ts: Optional[str], cooldown_minutes: int = 10) -> bool:
    if not last_ts:
        return True
    try:
        last = datetime.fromisoformat(last_ts)
        return datetime.utcnow() - last > timedelta(minutes=cooldown_minutes)
    except Exception as e:
        logger.warning(f"Invalid last_warning_ts format: {e}")
        return True


def check_humidity_threshold(plant_id: str, measurement: dict, plant: dict, db_service):
    if measurement["type"] != "humidity":
        return

    humidity = measurement["value"]
    threshold = 20.0
    if humidity >= threshold:
        return

    last_ts = get_last_warning_ts(plant)
    if not is_cooldown_passed(last_ts, cooldown_minutes=5):
        logger.info(f"No alert for {plant_id}: cooldown not passed")
        return

    dt_factory = current_app.config["DT_FACTORY"]
    dt = dt_factory.get_dt_by_plant_id(plant_id)

    if not dt:
        logger.warning(f"DT non trovato per {plant_id}")
        return

    services = [s["name"] for s in dt.get("services", [])]

    if "AutoWateringService" not in services:
        _handle_no_autowatering(plant_id, humidity, plant, db_service)
    else:
        _handle_autowatering(plant_id, humidity, plant, dt, db_service)


def _handle_no_autowatering(plant_id, humidity, plant, db_service):
    owner_id = plant.get("profile", {}).get("owner_id")
    if not owner_id:
        logger.warning(f"Nessun owner_id associato a {plant_id}")
        return

    user = db_service.get_dr("user", owner_id)
    if not user:
        logger.warning(f"Utente non trovato per owner_id {owner_id}")
        return

    telegram_id = user.get("profile", {}).get("telegram_id")
    if not telegram_id or not is_authenticated(telegram_id):
        logger.info(f"Utente {owner_id} non autenticato → niente notifica Telegram")
        return

    plant_name = plant.get("profile", {}).get("name", plant_id)
    loop = current_app.config.get("TELEGRAM_LOOP")
    if loop and loop.is_running():
        run_coroutine_threadsafe(
            send_humidity_alert_to_user(telegram_id, plant_name, humidity),
            loop
        )

    update_last_warning_ts(db_service, plant_id)
    logger.info(f"🌱 ALERT inviato per {plant_id} → humidity {humidity}%")


def _handle_autowatering(plant_id, humidity, plant, dt, db_service):
    location = plant.get("profile", {}).get("location", "").lower()

    if location == "indoor":
        # 🌊 Invia comando MQTT diretto
        mqtt_handler = current_app.config["MQTT_HANDLER"]
        topic = f"smartplant/{plant_id}/commands"
        mqtt_handler.publish(topic, "water")

        logger.info(f"💧 AutoWatering (indoor): comando water inviato per {plant_id}")
        update_last_warning_ts(db_service, plant_id)
    else:
        # ☁️ Outdoor: demandiamo a WeatherForecast (seconda parte)
        logger.info(f"🌦️ Outdoor + AutoWatering: gestione demandata a WeatherForecastService per {plant_id}")

