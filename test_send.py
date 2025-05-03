import paho.mqtt.client as mqtt
import ssl
import json
from datetime import datetime

timestamp = datetime.utcnow().isoformat() + "Z"
print(timestamp)