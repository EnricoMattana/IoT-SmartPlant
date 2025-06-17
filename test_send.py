import paho.mqtt.client as mqtt
import ssl
import json
from datetime import datetime, timedelta
import random
import time

PLANT_ID = "PL3"
NUM_GIORNI = 1
MISURE_AL_GIORNO = 2
PAUSA = 0.1

client = mqtt.Client()
client.tls_set()
client.username_pw_set("smartplant-users", "IoTPlant2025")

def publish_fake_data():
    now = datetime.utcnow()
    for day_offset in reversed(range(NUM_GIORNI)):  # 🔁 dal più vecchio al più recente
        for i in range(MISURE_AL_GIORNO):
            ts = now - timedelta(days=day_offset, hours=i * (24 // MISURE_AL_GIORNO))
            timestamp = ts.isoformat()

            payload = [
                {
                    "type": "humidity",
                    "value": round(random.uniform(0.0, 100.0), 1),
                    "timestamp": timestamp
                },
                {
                    "type": "light",
                    "value": round(random.uniform(0.0, 100.0), 1),
                    "timestamp": timestamp,

                }
            ]
            topic = f"smartplant/{PLANT_ID}/measurement"
            client.publish(topic, payload=json.dumps(payload), retain=False)
            print(f"📤 Inviato: {timestamp}")
            time.sleep(PAUSA)

def on_connect(client, userdata, flags, rc):
    print("✅ Connected with result code", rc)
    client.loop_start()
    publish_fake_data()
    client.loop_stop()
    client.disconnect()

client.on_connect = on_connect
client.connect("2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud", 8883)
client.loop_forever()
