from flask import current_app
import paho.mqtt.client as mqtt
from datetime import datetime
import json
import logging
import time
from threading import Thread, Event
from src.application.utils import handle_measurement, handle_notification


logger = logging.getLogger(__name__)

class SmartPlantMQTTHandler:

    def __init__(self, app):
        self.app = app  
        client_id = "SmartPlant_Backend" # Identificativo del client MQTT
        self.client = mqtt.Client(client_id=client_id, clean_session=True)  # Crea il client MQTT

        # Associa le funzioni di callback agli eventi MQTT
        self.client.on_connect = self._on_connect # Connessione
        self.client.on_message = self._on_message # Ricezione Messaggio
        self.client.on_disconnect = self._on_disconnect # Disconnessione

        # Configura ulteriormente il client MQTT (es. TLS, autenticazione, ecc.)
        self._setup_mqtt()

        
        self.connected = False # Stato della connessione
        self.stopping = Event() # Evento per gestire l'arresto del thread di riconnessione
        self.reconnect_thread = None # Thread per la riconnessione automatica, importante in caso di perdita di connessione momentanea
        self.client.enable_logger(logger) # Debug

    def _setup_mqtt(self):
        """Setup MQTT client with configuration from app"""
        # Recupera la configurazione MQTT dall'app Flask
        config = self.app.config.get('MQTT_CONFIG', {})
        self.broker = config.get('broker')  # Indirizzo del broker MQTT
        self.port = config.get('port', 8883)  # Porta del broker (default 8883 per TLS)
        self.topic = config.get('topic')  # Lista di topic a cui iscriversi

        # Abilita la connessione sicura TLS
        self.client.tls_set()
        # Imposta username e password per autenticazione, passati dal main
        self.client.username_pw_set(config.get('username'), config.get('password'))

        logger.info(f"MQTT Setup - Broker: {self.broker}, Port: {self.port}")
        
    def start(self):
        """Avvia la connessione al broker MQTT e inizia ad ascoltare i messaggi in modo NON blocking."""
        try:
            logger.info('Starting MQTT thread') 
            self.client.loop_start()  # Avvia il loop del client MQTT in un thread separato (non blocca il programma principale)
            self._connect() # Connessione al broker MQTT

            # Avvia un thread separato che gestisce la riconnessione automatica in caso di disconnessione
            self.reconnect_thread = Thread(target=self._reconnection_loop)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()

            logger.info("MQTT handler started")
        except Exception as e:
            logger.error(f"Error starting MQTT handler: {e}")

    def stop(self):
        """Stop MQTT client"""
        # Settiamo lo stop event
        self.stopping.set()
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=1.0)
        # Ferma il loop del client MQTT
        self.client.loop_stop()
        # Disconnette il client dal broker MQTT
        if self.connected:
            self.client.disconnect()
        logger.info("MQTT handler stopped")

    def _connect(self):
        """Tenta di connettersi al broker MQTT."""
        # Connessione al client MQTT
        try: 
            self.client.connect(self.broker, self.port, 60) # Prova a connettersi al broker MQTT con un timeout di 60 secondi
            logger.info(f"Attempting connection to {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            self.connected = False # In caso di fallimento imposta lo stato come non connesso

    def _reconnection_loop(self):
        """Thread che tenta di riconnettersi al broker MQTT"""
        while not self.stopping.is_set():
            if not self.connected:
                logger.info("Attempting to reconnect...")
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Reconnection attempt failed: {e}")
            time.sleep(5)   #Tentativo ogni 5 secondi

    def _on_connect(self, client, userdata, flags, rc):
        """Callback chiamata quando il client si connette al broker MQTT."""
        if rc == 0:  # rc == 0 indica che la connessione è avvenuta con successo
            self.connected = True # Imposta lo stato come connesso
            logger.info("Connected to MQTT broker")
             # Iscrizione a tutti i topic specificati nelle config dell'app
            for topic, qos in self.topic:
                client.subscribe(topic, qos)
                logger.info(f"Subscribed to {topic} with QoS {qos}")
        else:
            self.connected = False # Imposta lo stato come disconnesso
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback chiamata quando il client si disconnette dal broker MQTT."""
        self.connected = False # Imposta lo stato come non connesso
        if rc != 0: # Se la disconnessione non è stata volontaria
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")

    @property 
    def is_connected(self):
        """Restituisce True se il client è connesso al broker MQTT, False altrimenti."""
        return self.connected

    def _on_message(self, client, userdata, msg):
        """Callback che gestisce la ricezione di un messaggio"""
        logger.info(f"MQTT ricevuto! Topic: {msg.topic}")
        logger.info(f"Payload: {msg.payload.decode()}")
        try:
            # Estrae plant_id e tipo di messaggio dal topic, la lunghezza del topic è sempre 3.
            parts = msg.topic.split('/')
            if len(parts) != 3: 
                logger.warning(f"Invalid topic format: {msg.topic}")
                return

            _, plant_id, argument = parts
            # Se il topic contiene measurement è una misura di un sensore:
            if argument=="measurement":
                try:
                    # Decodifica il payload JSON
                    payload = json.loads(msg.payload.decode())
                except Exception as e:
                    logger.error(f"Invalid JSON payload: {e}")
                    return

                # Supporta sia dict singolo che lista di dict, per gestire misure in batch
                measurements = []
                if isinstance(payload, dict):
                    measurements = [payload]
                elif isinstance(payload, list):
                    measurements = payload
                else:
                    logger.error("Payload must be a dict or list of dicts")
                    return

                # Aggiunge le misure al database
                with self.app.app_context():
                    self._add_measurements_batch(plant_id, measurements)
            
            elif argument=="errors":
                db_service = self.app.config["DB_SERVICE"]
                # recupera la Digital Replica
                plant = db_service.get_dr("plant", plant_id)
                payload = json.loads(msg.payload.decode())
                # Unico errore gestito per ora è il malfunzionamento della pompa (o una falsa misura del sensore)
                if payload.get("code") == "pump":
                    data = {
                        "delta": payload.get("delta"),
                        "timestamp": payload.get("timestamp")
                    }
                # Gestisce la notifica di errore usando il context Flask
                with self.app.app_context():
                    handle_notification(plant_id, data, plant, db_service, kind="error")
        except Exception as e:
            logger.error(f"Error processing incoming MQTT message: {e}")
    
    def _add_measurements_batch(self, plant_id: str, measurements: list[dict]):
        """Aggiorna il DB con le info della pianta."""
        db_service = current_app.config["DB_SERVICE"]
        dr_factory = current_app.config["DR_FACTORY"]

        # recupera la Digital Replica
        plant = db_service.get_dr("plant", plant_id)
        if not plant:
            logger.error(f"Plant not found with ID: {plant_id}")
            return

        # Normalizza/parsa i timestamp delle misure
        for m in measurements:
            ts = m.get("timestamp")
            if isinstance(ts, str):
                try:
                    m["timestamp"] = datetime.fromisoformat(ts)
                except Exception as e:
                    logger.warning(f"Invalid timestamp format for plant {plant_id}: {e}")
                    return

        # Aggiorna la Digital Replica con le nuove misure
        update_dict = {
            "data": {
                "measurements": plant.get("data", {}).get("measurements", []) + measurements
            }
        }
        # Formatto la nuova pianta con dr_factory
        updated_plant = dr_factory.update_dr(plant, update_dict)
        #  Salva la Digital Replica aggiornata nel database
        db_service.update_dr("plant", plant_id, updated_plant)
        logger.info(f"Insieme di {len(measurements)} misure aggiunte alla pianta {plant_id}")

        # Trova l'ultima misura di umidità e di luce per la pianta
        last_humidity = None
        last_light = None
        for m in reversed(measurements):
            if m["type"] == "humidity" and last_humidity is None:
                last_humidity = m
            elif m["type"] == "light" and last_light is None:
                last_light = m
            if last_humidity and last_light:
                break  # possiamo uscire non appena le abbiamo trovate entrambe

        # Esegue il controllo separato per ciascuna delle ultime misure trovate con il servizio plant manager.
        if last_humidity:
            handle_measurement(plant_id, last_humidity, updated_plant)

        if last_light:
            handle_measurement(plant_id, last_light, updated_plant)
                    
        
    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """
        Publish an MQTT message to a specific topic.
        """

        # Se il payload è un dizionario, lo converte in stringa JSON
        if isinstance(payload, dict):
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)

        # Pubblica solo se il client è connesso
        if self.connected:
            # Tenta di pubblicare il messaggio
            result = self.client.publish(topic, payload_str, qos=qos, retain=retain)

            # Controlla se la pubblicazione è andata a buon fine
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish message: {mqtt.error_string(result.rc)}")
            else:
                logger.info(f"Published to {topic}: {payload_str}")
        else:
            logger.warning("MQTT client is not connected. Message NOT sent.")

