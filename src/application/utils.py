# utils.py
from src.application.telegram.handlers.command_handlers import send_alert_to_user
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
import logging
import asyncio
from src.services.plant_service import PlantManagement
from flask import current_app
from asyncio import run_coroutine_threadsafe


logger = logging.getLogger(__name__)





def handle_notification(plant_id, value, plant, db_service, kind="humidity"):
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
        if kind == "humidity":
            coro = send_alert_to_user(telegram_id, plant_name, value, kind)
        elif kind == "light":
            coro = send_alert_to_user(telegram_id, plant_name, value, kind)
        elif kind== "error":
            coro = send_alert_to_user(telegram_id, plant_name, value, kind)
        else:
            logger.warning(f"Tipo notifica non gestito: {kind}")
            return

        run_coroutine_threadsafe(coro, loop)
        logger.info(f"🌱 ALERT inviato per {plant_id} → {kind}: {value}")


def handle_measurement(plant_id: str, measurement: dict, plant: dict = None):
    db_service = current_app.config['DB_SERVICE']
    dt_factory = current_app.config['DT_FACTORY']
    dt_data = dt_factory.get_dt_by_plant_id(plant_id)
    if not dt_data:
        logger.warning(f"No DT found for plant {plant_id}")
        return

    dt_instance = dt_factory.get_dt_instance(dt_data["_id"])
    if not dt_instance:
        logger.warning(f"Failed to create DT instance for {dt_data['_id']}")
        return

    if "PlantManagement" not in dt_instance.list_services():
        logger.warning(f"PlantManagement service not found for DT {dt_data['_id']}")
        return

    context = {
        "DB_SERVICE": db_service,
        "DT_FACTORY": dt_factory,
        "DR_FACTORY": current_app.config['DR_FACTORY']
    }

    decision = dt_instance.execute_service(
        service_name="PlantManagement",
        plant_id=plant_id,
        measurement=measurement,
        context=context
    )

    if decision["action"] == "0":
        logger.info(f"PlantManagement decision: {decision} → No action taken")
    elif decision["action"] == "notify_humidity":
        handle_notification(plant_id, measurement["value"], plant, db_service, kind="humidity")
        logger.info(f"PlantManagement decision: {decision} → Notification sent")
    elif decision["action"] == "notify_light":
        handle_notification(plant_id, measurement["value"], plant, db_service, kind="light")
    elif decision["action"] == "water":
        logger.info(f"PlantManagement decision: {decision}")
        mqtt_handler = current_app.config['MQTT_HANDLER']
        topic = f"smartplant/{plant_id}/commands"
        payload = "water " + str(decision["duration"])
        mqtt_handler.publish(topic, payload)
