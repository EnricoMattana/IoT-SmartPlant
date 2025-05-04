import paho.mqtt.client as mqtt
import ssl

# === CONFIGURAZIONE MQTT ===
MQTT_BROKER = "2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "smartplant-users"
MQTT_PASSWORD = "IoTPlant2025"
MQTT_TOPIC = "smartplant/+/commands"

# === CALLBACK: connessione riuscita ===
def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"📡 Subscribed to: {MQTT_TOPIC}")

# === CALLBACK: messaggio ricevuto ===
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    print(f"\n📥 Message received!")
    print(f"🔗 Topic: {topic}")
    print(f"📦 Payload: {payload}")

# === SETUP CLIENT MQTT ===
client = mqtt.Client()
client.tls_set()  # TLS con certificati CA di sistema
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT)
client.loop_forever()
