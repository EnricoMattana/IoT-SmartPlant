import paho.mqtt.client as mqtt
import ssl
import json
from datetime import datetime

client = mqtt.Client()
client.tls_set()  # Usa CA di sistema per TLS
client.username_pw_set("smartplant-users", "IoTPlant2025")

def on_connect(client, userdata, flags, rc):
    print("✅ Connected with result code", rc)
    payload2 = {
        "type": "light",
        "value": 420,
        "timestamp": datetime.utcnow().isoformat()
    }

    timestamp = datetime.utcnow().isoformat()
    payload1 = [
        {
            "type": "humidity",
            "value": 10,
            "timestamp": timestamp
        },
        {
            "type": "light",
            "value": 78.3,
            "timestamp": timestamp
        }
    ]

    client.publish("smartplant/PL2/measurement", payload= json.dumps(payload1), retain=False)
    print("📤 Message published")

client.on_connect = on_connect

client.connect("2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud", 8883)
client.loop_forever()
