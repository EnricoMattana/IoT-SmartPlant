# utils.py

from src.application.telegram.handlers.command_handlers import send_humidity_alert_to_user
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
import logging
import asyncio
from src.services.plant_service import WateringManagement
from flask import current_app
from asyncio import run_coroutine_threadsafe


logger = logging.getLogger(__name__)





def handle_notification(plant_id, humidity, plant, db_service):
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
    logger.info(f"🌱 ALERT inviato per {plant_id} → humidity {humidity}%")


def handle_measurement(plant_id: str, measurement: dict, plant: dict = None):
    dt_factory = current_app.config['DT_FACTORY']
    db_service = current_app.config['DB_SERVICE']
    dt_data = dt_factory.get_dt_by_plant_id(plant_id)
    if not dt_data:
        logger.warning(f"No DT found for plant {plant_id}")
        return

    # Cerca il servizio come dizionario nella lista dei servizi
    services = dt_data.get("services", [])
    service_entry = next((s for s in services if s["name"] == "WateringManagement"), None)

    if not service_entry:
        logger.warning(f"WateringManagement service not found for plant {plant_id}")
        return

    # Importa dinamicamente e istanzia il servizio
    
    service = WateringManagement()
    service.configure(service_entry.get("config", {}))

    # Esegui
    context = {
        "DB_SERVICE": db_service,
        "DT_FACTORY": dt_factory
    }
    decision = service.execute(plant_id=plant_id, data=measurement, context=context)
    if decision["action"] == "0":
        logger.info(f"WateringManagement decision: {decision} → No action taken")
    elif decision["action"] == "notify":
        handle_notification(plant_id, measurement["value"], plant, db_service)
        logger.info(f"WateringManagement decision: {decision} → Notification sent")
    elif decision["action"] == "water":
        logger.info(f"WateringManagement decision: {decision}")
        mqtt_handler = current_app.config['MQTT_HANDLER']
        topic = f"smartplant/{plant_id}/commands"
        payload = "water"
        mqtt_handler.publish(topic, payload)