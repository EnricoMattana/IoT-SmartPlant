from flask import Flask
from flask_cors import CORS
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
from src.services.database_service import DatabaseService
from src.digital_twin.dt_factory import DTFactory
from src.application.api import register_api_blueprints
from config.config_loader import ConfigLoader
import asyncio
from src.application.SmartPlant_apis import register_smartplant_blueprint
from src.application.api import register_api_blueprints 
from src.application.mqtt_handler import SmartPlantMQTTHandler

import logging
logging.basicConfig(level=logging.INFO)

#Nuova parte
from src.application.telegram.telegram_handler import TelegramWebhookHandler



class FlaskServer:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        self._init_components()
        self._register_blueprints()
        self.telegram_handler = TelegramWebhookHandler(self.app)
        #self.telegram_loop = asyncio.new_event_loop()
        #self.app.config["TELEGRAM_LOOP"] = self.telegram_loop
        self.app.config['MQTT_CONFIG'] = MQTT_CONFIG
        self.mqtt_handler = SmartPlantMQTTHandler(self.app)
        self.app.config['MQTT_HANDLER'] = self.mqtt_handler
        


    def _init_components(self):
        """Initialize all required components and store them in app config"""
        schema_registry = SchemaRegistry()
        schema_registry.load_schema(
        'plant',
        'src/virtualization/templates/plant.yaml'
        )
        schema_registry.load_schema(
        'user',
        'src/virtualization/templates/user.yaml'
        )
        # Load database configuration
        db_config = ConfigLoader.load_database_config()
        connection_string = ConfigLoader.build_connection_string(db_config)

        # Initialize DatabaseService with populated schema_registry
        db_service = DatabaseService(
            connection_string=connection_string,
            db_name=db_config["settings"]["name"],
            schema_registry=schema_registry,
        )
        db_service.connect()

        # Initialize DTFactory
        dt_factory = DTFactory(db_service, schema_registry)

        # Store references
        self.app.config["SCHEMA_REGISTRY"] = schema_registry
        self.app.config["DB_SERVICE"] = db_service
        self.app.config["DT_FACTORY"] = dt_factory
    def _register_blueprints(self):
        """Register all API blueprints"""
        register_api_blueprints(self.app)
        register_smartplant_blueprint(self.app)

    def run(self, host="0.0.0.0", port=5000, debug=False):
        """Run the Flask server"""
        try:
            #import threading
            #threading.Thread(target=self.telegram_loop.run_forever, daemon=True).start()
            self.telegram_handler.start() 
            #print(f"🚀 Loop Telegram attivo? {self.telegram_loop.is_running()}")

            self.mqtt_handler.start()  # ← Start MQTT BEFORE app.run()
            #print(f"🚀 Loop Telegram attivo? {self.telegram_loop.is_running()}")

            self.app.run(host=host, port=port, debug=debug)
        finally:
            if "DB_SERVICE" in self.app.config:
                self.app.config["DB_SERVICE"].disconnect()
            self.mqtt_handler.stop()  # ← Clean shutdown
            self.telegram_handler.stop()
            #self.telegram_loop.stop()

MQTT_CONFIG = {
    "broker": "2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud",
    "port": 8883,
    "username": "smartplant-backend",
    "password": "IoTPlant2025",
    "topic": "smartplant/+/measurement"
} 

WeatherAPI="05418e63cb684a3a8f2135050250205"
if __name__ == "__main__":
    server = FlaskServer()
    server.run()
