from flask import current_app
import paho.mqtt.client as mqtt
from datetime import datetime
import json
import logging
import time
from threading import Thread, Event
import uuid
from src.application.utils import handle_measurement


logger = logging.getLogger(__name__)

class SmartPlantMQTTHandler:

    def __init__(self, app):
        self.app = app
        client_id = "SmartPlant_Backend"
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

    def _setup_mqtt(self):
        """Setup MQTT client with configuration from app"""
        config = self.app.config.get('MQTT_CONFIG', {})
        self.broker = config.get('broker')
        self.port = config.get('port', 8883)
        self.topic = config.get('topic', 'smartplant/+/measurements')

        self.client.tls_set()
        self.client.username_pw_set(config.get('username'), config.get('password'))

        print(f"MQTT Setup - Broker: {self.broker}, Port: {self.port}")
        print(f"Topic:  {self.topic}")

    def start(self):
        """Start MQTT client in non-blocking way"""
        try:
            print('Starting MQTT thread')
            self.client.loop_start()
            self._connect()

            self.reconnect_thread = Thread(target=self._reconnection_loop)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()

            logger.info("MQTT handler started")
        except Exception as e:
            logger.error(f"Error starting MQTT handler: {e}")

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
        try:
            self.client.connect(self.broker, self.port, 60)
            logger.info(f"Attempting connection to {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            self.connected = False

    def _reconnection_loop(self):
        while not self.stopping.is_set():
            if not self.connected:
                logger.info("Attempting to reconnect...")
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Reconnection attempt failed: {e}")
            time.sleep(5)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            print("✅ Connected to MQTT broker")
            client.subscribe(self.topic)
            logger.info(f"Subscribed to {self.topic}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")

    @property
    def is_connected(self):
        return self.connected

    def _on_message(self, client, userdata, msg):
        print(f"📥 MQTT ricevuto! Topic: {msg.topic}")
        print(f"🔎 Payload: {msg.payload.decode()}")
        try:
            parts = msg.topic.split('/')
            if len(parts) != 3:
                logger.warning(f"Invalid topic format: {msg.topic}")
                return

            _, plant_id, _ = parts

            try:
                payload = json.loads(msg.payload.decode())
            except Exception as e:
                logger.error(f"Invalid JSON payload: {e}")
                return

            # Supporta sia dict singolo che lista di dict
            measurements = []
            if isinstance(payload, dict):
                measurements = [payload]
            elif isinstance(payload, list):
                measurements = payload
            else:
                logger.error("Payload must be a dict or list of dicts")
                return

            for m in measurements:
                if not all(k in m for k in ("type", "value", "timestamp")):
                    logger.error("Missing measurement fields in one of the items")
                    return

            with self.app.app_context():
                for m in measurements:
                    self._add_measurement(plant_id, m)
            
        except Exception as e:
            logger.error(f"Error processing incoming MQTT message: {e}")

    def _add_measurement(self, plant_id: str, measurement: dict):
        try:
            db_service = current_app.config['DB_SERVICE']

            plant = db_service.get_dr("plant", plant_id)
            if not plant:
                logger.error(f"Plant not found with ID: {plant_id}")
                return

            # 🔁 Converti timestamp se necessario
            if isinstance(measurement.get("timestamp"), str):
                try:
                    measurement["timestamp"] = datetime.fromisoformat(measurement["timestamp"])
                except Exception as e:
                    logger.warning(f"Invalid timestamp format for plant {plant_id}: {e}")
                    return

            # 📥 Aggiungi misura al database
            plant.setdefault("data", {})
            plant["data"].setdefault("measurements", []).append(measurement)
            plant["metadata"]["updated_at"] = datetime.utcnow()
            db_service.update_dr("plant", plant_id, plant)
            logger.info(f"Measurement added to plant {plant_id}")
            handle_measurement(plant_id, measurement, plant)

        except Exception as e:
            logger.error(f"Error updating plant {plant_id}: {e}")
        
        
        



    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False):
        """
        Publish an MQTT message to a specific topic.

        Args:
            topic (str): The MQTT topic to publish to (e.g., 'plant/123/commands')
            payload (dict or str): The message content (either a Python dict or raw string)
            qos (int): Quality of Service level (0 = at most once, 1 = at least once, 2 = exactly once)
            retain (bool): If True, broker will retain this message for new subscribers
        """

        # If the payload is a dictionary, convert it to a JSON-formatted string
        if isinstance(payload, dict):
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)

        # Ensure the MQTT client is connected before publishing
        if self.connected:
            # Attempt to publish the message
            result = self.client.publish(topic, payload_str, qos=qos, retain=retain)

            # Check if the publish was successful
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish message: {mqtt.error_string(result.rc)}")
            else:
                logger.info(f"Published to {topic}: {payload_str}")
        else:
            logger.warning("MQTT client is not connected. Message NOT sent.")

