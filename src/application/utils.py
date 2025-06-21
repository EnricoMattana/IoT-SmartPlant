# utils.py
from src.application.telegram.handlers.command_handlers import send_alert_to_user
from src.application.telegram.handlers.login_handlers import is_authenticated
import logging
from flask import current_app
from asyncio import run_coroutine_threadsafe


logger = logging.getLogger(__name__)





def handle_notification(plant_id, value, plant, db_service, kind="humidity"):
    '''Funzione che gestisce l'invio di notifiche all'utente!'''
    # Recupera l'ID del proprietario della pianta
    owner_id = plant.get("profile", {}).get("owner_id")
    if not owner_id:
        logger.warning(f"Nessun owner_id associato a {plant_id}")
        return
    
    # Recupera l'utente proprietario dal database
    user = db_service.get_dr("user", owner_id)
    if not user:
        logger.warning(f"Utente non trovato per owner_id {owner_id}")
        return

    # Recupera l'ID Telegram dell'utente
    telegram_id = user.get("profile", {}).get("telegram_id")
    # Verifica che l'utente sia autenticato su Telegram
    if not telegram_id or not is_authenticated(telegram_id):
        logger.info(f"Utente {owner_id} non autenticato, niente notifica Telegram")
        return

    # Recupera il nome della pianta
    plant_name = plant.get("profile", {}).get("name")
    # Recupera l'event loop di Telegram per le notifiche
    loop = current_app.config.get("TELEGRAM_LOOP")
    
    # Se l'event loop è attivo, invia la notifica, il loop viene attivato all'inizializzazione del telegram handler se andato a buon fine
    if loop and loop.is_running():
        # Solo 3 tipologie di notifiche son abilitate per ora!
        if kind in ("humidity", "light", "error"):
            coro = send_alert_to_user(telegram_id, plant_name, value, kind)
        else:
            logger.warning(f"Tipo notifica non gestito: {kind}")
            return
        # Invio effettivo della notifica
        run_coroutine_threadsafe(coro, loop)
        logger.info(f"ALERT inviato per {plant_id} → {kind}: {value}")


def handle_measurement(plant_id: str, measurement: dict, plant: dict = None):
    '''Management intelligente della pianta'''
    # Recupera il servizio database e la factory dei Digital Twin dal context Flask
    db_service = current_app.config['DB_SERVICE']
    dt_factory = current_app.config['DT_FACTORY']
    # Recupera i dati del Digital Twin associato alla pianta
    dt_data = dt_factory.get_dt_by_plant_id(plant_id)
    if not dt_data:
        logger.warning(f"Nessun DT trovato per {plant_id}")
        return
    # Ottiene l'istanza del Digital Twin
    dt_instance = dt_factory.get_dt_instance(dt_data["_id"])
    if not dt_instance:
        logger.warning(f"Fallimento nella creazione del dt {dt_data['_id']}")
        return

    # Verifica che il servizio PlantManagement sia disponibile
    if "PlantManagement" not in dt_instance.list_services():
        logger.warning(f"Il servizio PlantManagement non è abilitato {dt_data['_id']}")
        return
    # Prepara il contesto per l'esecuzione del servizio
    context = {
        "DB_SERVICE": db_service,
        "DT_FACTORY": dt_factory,
        "DR_FACTORY": current_app.config['DR_FACTORY']
    }
    # Esegue il servizio PlantManagement sul Digital Twin
    decision = dt_instance.execute_service(
        service_name="PlantManagement",
        plant_id=plant_id,
        measurement=measurement,
        context=context
    )

    # Gestisce la decisione presa dal servizio PlantManagement!
    if decision["action"] == "0":
        logger.info(f"Decisione PlantManagement: {decision} -> Nessuna azione presa")
    elif decision["action"] == "notify_humidity":
        handle_notification(plant_id, measurement["value"], plant, db_service, kind="humidity")
        logger.info(f"Decisione PlantManagement: {decision} -> Notifica inviata")
    elif decision["action"] == "notify_light":
        handle_notification(plant_id, measurement["value"], plant, db_service, kind="light")
    elif decision["action"] == "water":
        # Se la decisione è "water", pubblichiamo un messaggio nel topic appropriato per avviare la pompa
        logger.info(f"Decisione PlantManagement: {decision}")
        mqtt_handler = current_app.config['MQTT_HANDLER']
        topic = f"smartplant/{plant_id}/commands"
        payload = "water " + str(decision["duration"])
        mqtt_handler.publish(topic, payload)
