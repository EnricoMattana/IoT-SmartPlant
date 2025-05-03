from flask import current_app
import paho.mqtt.client as mqtt
from datetime import datetime
import json
import logging
import time
from threading import Thread, Event
import uuid
logger = logging.getLogger(__name__)

class SmartPlantMQTTHandler:

    def __init__(self, app):
        self.app = app
        #client_id = f"smartplant_{uuid.uuid4()}"
        client_id=f"SmartPlant_Backend"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)

        # Bind MQTT events
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self._setup_mqtt()
        self.connected = False
        self.stopping = Event()
        self.reconnect_thread = None
        self.client.enable_logger(logger)
    'BISOGNA MODIFICARE SETUP_MQTT'

    def _setup_mqtt(self):
        """Setup MQTT client with configuration from app"""
        config = self.app.config.get('MQTT_CONFIG', {})
        self.broker = config.get('broker')
        self.port = config.get('port', 8883)
        self.topic = config.get('topic', 'smartplant/+/+/measurements')

        # Sicurezza: TLS + autenticazione
        self.client.tls_set()  # Usa certificati di sistema
        self.client.username_pw_set(config.get('username'), config.get('password'))

        print(f"MQTT Setup - Broker: {self.broker}, Port: {self.port}")
        print(f"Topic:  {self.topic}")





    def start(self):
        """Start MQTT client in non-blocking way"""
        try:
            print('Starting MQTT thread')
            # Start MQTT loop in background thread
            self.client.loop_start()
            # Try to connect
            self._connect()

            # Start reconnection thread
            self.reconnect_thread = Thread(target=self._reconnection_loop)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()

            logger.info("MQTT handler started")
        except Exception as e:
            logger.error(f"Error starting MQTT handler: {e}")
            # Don't raise the exception - allow the application to continue

    def stop(self):
        """Stop MQTT client"""
        self.stopping.set()
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=1.0)

        self.client.loop_stop()

        if self.connected:
            self.client.disconnect()

        logger.info("MQTT handler stopped")

    def _connect(self):
        """Attempt to connect to the broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            logger.info(f"Attempting connection to {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            self.connected = False

    def _reconnection_loop(self):
        """Background thread that handles reconnection"""
        while not self.stopping.is_set():
            if not self.connected:
                logger.info("Attempting to reconnect...")
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Reconnection attempt failed: {e}")
            time.sleep(5)  # Wait 5 seconds between reconnection attempts

    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection to broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            print("Connected to MQTT broker")
            # Subscribe to topic
            client.subscribe(self.topic)
            logger.info(f"Subscribed to {self.topic}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")

    @property
    def is_connected(self):
        """Check if client is currently connected"""
        return self.connected

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT measurement messages"""
        print(f"📥 MQTT ricevuto! Topic: {msg.topic}")
        print(f"🔎 Payload: {msg.payload.decode()}")
        try:
            # Esempio topic: smartplant/<user_id>/<plant_id>/measurements
            parts = msg.topic.split('/')
            if len(parts) != 4:
                logger.warning(f"Invalid topic format: {msg.topic}")
                return

            _, user_id, plant_id, measure_type = parts

            try:
                payload = json.loads(msg.payload.decode())
            except Exception as e:
                logger.error(f"Invalid JSON payload: {e}")
                return

            # Verifica campi essenziali
            if 'type' not in payload or 'value' not in payload or 'timestamp' not in payload:
                logger.error("Missing measurement fields in payload")
                return

            with self.app.app_context():
                self._add_measurement(user_id, plant_id, payload)

        except Exception as e:
            logger.error(f"Error processing incoming MQTT message: {e}")

    def _add_measurement(self, user_id: str, plant_id: str, measurement: dict):
        """Add measurement to the correct plant document"""
        try:
            db_service = current_app.config['DB_SERVICE']
            plant = db_service.get_dr("plant", plant_id)

            if not plant:
                logger.error(f"Plant not found with ID: {plant_id}")
                return

            # (Opzionale) controllo che appartenga all'utente
            # if plant.get("owner_id") != user_id:
            #     logger.warning(f"User {user_id} not authorized to update plant {plant_id}")
            #     return

            # Inizializza se mancano
            if "data" not in plant:
                plant["data"] = {}
            if "measurements" not in plant["data"]:
                plant["data"]["measurements"] = []

            plant["data"]["measurements"].append(measurement)
            plant["metadata"]["updated_at"] = datetime.utcnow()

            # Aggiorna su MongoDB
            db_service.update_dr("plant", plant_id, {
                "data": {
                    "measurements": plant["data"]["measurements"]
                },
                "metadata": {
                    "updated_at": plant["metadata"]["updated_at"]
                }
            })

            logger.info(f"Measurement added to plant {plant_id}")

        except Exception as e:
            logger.error(f"Error updating plant {plant_id}: {e}")

