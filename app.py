from flask import Flask
from flask_cors import CORS
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
from src.services.database_service import DatabaseService
from src.digital_twin.dt_factory import DTFactory
from src.application.api import register_api_blueprints
from config.config_loader import ConfigLoader
from src.application.api import register_api_blueprints 
from src.application.mqtt_handler import SmartPlantMQTTHandler
from src.virtualization.digital_replica.dr_factory import DRFactory
import logging
logging.basicConfig(level=logging.INFO)
from src.application.telegram.telegram_handler import TelegramWebhookHandler


# Classe principale che gestisce il server Flask e tutti i componenti dell'applicazione
class FlaskServer:
    def __init__(self):
        self.app = Flask(__name__) # Crea l'app Flask
        CORS(self.app)
        self._init_components() # Inizializza i componenti principali (DB, registry, MQTT, TelegramBot)
        self._register_blueprints()
        


    def _init_components(self):
        """Inizializza tutti i componenti necessari e li salva nella config di Flask"""
        schema_registry = SchemaRegistry()        
        # Carica lo schema della pianta (validazione, consistenza)
        schema_registry.load_schema(
            'plant',
            'src/virtualization/templates/plant.yaml'
        )
        # Carica lo schema dell'utente (validazione, consistenza)
        schema_registry.load_schema(
            'user',
            'src/virtualization/templates/user.yaml'
        )
        # Configura database
        db_config = ConfigLoader.load_database_config()
        connection_string = ConfigLoader.build_connection_string(db_config)
        db_service = DatabaseService(
            connection_string=connection_string,
            db_name=db_config["settings"]["name"],
            schema_registry=schema_registry,
        )
        db_service.connect()
        # Factory per le Digital Replica
        dr_factory = DRFactory("src/virtualization/templates/plant.yaml")

         # Factory per i Digital Twin
        dt_factory = DTFactory(db_service, schema_registry)

        # Salvataggio in app config
        self.app.config["SCHEMA_REGISTRY"] = schema_registry
        self.app.config["DB_SERVICE"] = db_service
        self.app.config["DT_FACTORY"] = dt_factory
        self.app.config["DR_FACTORY"] = dr_factory
        self.app.config["DR_FACTORY_USER"]=DRFactory("src/virtualization/templates/user.yaml")
        self.app.config['MQTT_CONFIG'] = MQTT_CONFIG             # Salva la configurazione MQTT nei config
        self.telegram_handler = TelegramWebhookHandler(self.app) # Inizializza il gestore Telegram
        self.mqtt_handler = SmartPlantMQTTHandler(self.app)     # Inizializza il gestore MQTT
        self.app.config['MQTT_HANDLER'] = self.mqtt_handler     # Salva il gestore MQTT nelle config


    def _register_blueprints(self):
        """Register all API blueprints"""
        register_api_blueprints(self.app)

    def run(self, host="0.0.0.0", port=5000, debug=False):
        """Run the Flask server"""
        try:
            # Avvia il bot Telegram
            self.telegram_handler.start() 
            # Avvia il gestore MQTT (deve essere avviato prima di Flask)
            self.mqtt_handler.start() 
            # Avvia il server Flask 
            self.app.run(host=host, port=port, debug=debug)
        finally:
            # Alla chiusura, disconnette il database e ferma i servizi
            if "DB_SERVICE" in self.app.config:
                self.app.config["DB_SERVICE"].disconnect()
            self.mqtt_handler.stop()
            self.telegram_handler.stop()


MQTT_CONFIG = {
    "broker": "2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud",
    "port": 8883,
    "username": "smartplant-backend",
    "password": "IoTPlant2025",
    "topic":[
    ("smartplant/+/measurement", 0),
    ("smartplant/+/errors", 1),]
} 
WeatherAPI="05418e63cb684a3a8f2135050250205"


if __name__ == "__main__":
    server = FlaskServer()
    server.run()
