import paho.mqtt.client as mqtt
import ssl
import json
from datetime import datetime

client = mqtt.Client()
client.tls_set()  # Usa CA di sistema per TLS
client.username_pw_set("smartplant-broker", "IoTPlant2025")

def on_connect(client, userdata, flags, rc):
    print("✅ Connected with result code", rc)
    payload = {
        "type": "light",
        "value": 420,
        "timestamp": datetime.utcnow().isoformat()
    }
    client.publish("smartplant/74157967-9d88-4231-8f8f-fd529d702ed4/0283837227633993/measurements", json.dumps(payload))
    print("📤 Message published")

client.on_connect = on_connect

client.connect("c665848c823e452eb211da0178af23f2.s1.eu.hivemq.cloud", 8883)
client.loop_forever()
