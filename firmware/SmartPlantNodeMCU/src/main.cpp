#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#define MQTT_MAX_PACKET_SIZE 1024
#include <PubSubClient.h>
#include <SoftwareSerial.h>
#include <LittleFS.h>
#include "PlantTelemetry.h"
#include <time.h>

// ——————— FIFO / batch ———————
constexpr uint8_t  FIFO_LEN = 6;
constexpr uint32_t T_UPLOAD = 60 * 1000;  // 1 min per test

// ─── forward declarations ───
void enqueueSample(float hum, float light, const String& ts);
void publishFIFO();

struct Sample {
  float   humidity;
  float   light;
  String  timestamp;
};

Sample   fifo[FIFO_LEN];
uint8_t  fifoHead   = 0;
uint8_t  fifoCount  = 0;
uint32_t lastUpload = 0;

// ———— MQTT topic globals ————
String mqttTopicOut;
String mqttTopicIn;
String mqttTopicBatch;
String mqttTopicErr;    // ← dichiarazione globale

#ifndef RESET_BTN_PIN
#define RESET_BTN_PIN D4 // D0 on NodeMCU
#endif

constexpr uint8_t RX_PIN = D2, TX_PIN = D3;
SoftwareSerial softSerial(RX_PIN, TX_PIN);

const char* MQTT_BROKER = "2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud";
const uint16_t MQTT_PORT = 8883;
const char* MQTT_USER   = "smartplant-users";
const char* MQTT_PASS   = "IoTPlant2025";

WiFiClientSecure net;
PubSubClient mqtt(net);
WiFiManager wm;
PlantTelemetry telemetry;
String plantId;

// —————— LittleFS helpers ——————
String readPlantId() {
  if (!LittleFS.exists("/plant_id.txt")) return "";
  File f = LittleFS.open("/plant_id.txt", "r");
  String id = f.readStringUntil('\n');
  f.close();
  id.trim();
  return id;
}
void writePlantId(const String& id) {
  if (readPlantId().length()) return;
  File f = LittleFS.open("/plant_id.txt", "w");
  f.println(id);
  f.close();
}

// ————— reset Wi-Fi —————
void resetCredentials() {
  Serial.println(F("⚠️  Reset Wi-Fi credenziali"));
  wm.resetSettings();
  ESP.restart();
}

// ————— MQTT reconnect —————
void mqttReconnect() {
  static uint32_t lastTry = 0;
  if (mqtt.connected()) return;
  if (millis() - lastTry < 5000) return;
  lastTry = millis();
  Serial.println(F("🔄 MQTT reconnect attempt..."));
  if (mqtt.connect("SmartPlantNode", MQTT_USER, MQTT_PASS)) {
    Serial.println(F("✅ MQTT connected"));
    mqtt.subscribe(mqttTopicIn.c_str());
    Serial.print(F("📡 Subscribed to: "));
    Serial.println(mqttTopicIn);
  } else {
    Serial.print(F("❌ MQTT connect failed, rc="));
    Serial.println(mqtt.state());
  }
}

// ————— MQTT callback —————
void callback(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; ++i) msg += (char)payload[i];
  msg.trim();
  Serial.printf("📥 MQTT-IN  %s → %s\n", topic, msg.c_str());

  // 1) JSON commands
  StaticJsonDocument<64> doc;
  if (deserializeJson(doc, msg) == DeserializationError::Ok && doc.containsKey("cmd")) {
    const char* cmd = doc["cmd"];
    if (strcmp(cmd, "send_now") == 0) {
      Serial.println(F("⏩ CMD send_now (JSON): invio ultimissime misure"));
      publishFIFO();
      return;
    }
    if (strcmp(cmd, "water") == 0) {
      int dur = doc["duration"] | 15000;
      Serial.print(F("🚿 CMD water: durata "));
      Serial.print(dur);
      Serial.println(F(" ms"));
      softSerial.println("water:" + String(dur));
      return;
    }
    if (strcmp(cmd, "calDry") == 0 || strcmp(cmd, "calWet") == 0) {
      Serial.printf("🔧 CMD %s\n", cmd);
      softSerial.println(cmd);
      return;
    }
  }

  // 2) Plain-text send_now
  if (msg == "send_now") {
    Serial.println(F("⏩ CMD send_now (plain): invio ultimissime misure"));
    publishFIFO();
    return;
  }

  // 3) Fallback → Arduino
  Serial.println(F("📤 Forward plain-text to Arduino"));
  softSerial.println(msg);
}

void setupNTP() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print(F("⏱ NTP sync..."));
  while (time(nullptr) < 1700000000) {
    Serial.print(F("."));
    delay(500);
  }
  Serial.println(F(" done"));
}

void setup() {


  Serial.begin(9600);
  softSerial.begin(9600);
  Serial.println(F("\n🌱 SmartPlant NodeMCU boot"));
    pinMode(D7, INPUT_PULLUP);
  if (!LittleFS.begin()) {
    Serial.println(F("❌ LittleFS init failed"));
    while (1);
  }

  wm.setTimeout(120);
  if (!wm.autoConnect("SmartPlant-Setup")) {
    Serial.println(F("❌ Wi-Fi setup fail"));
    ESP.restart();
  }
  Serial.print(F("📶 Wi-Fi SSID: "));
  Serial.println(WiFi.SSID());

  setupNTP();

  writePlantId("PLANT-9F7C");
  plantId = readPlantId();
  Serial.print(F("📛 Plant ID: "));
  Serial.println(plantId);

  // Costruzione topics
  mqttTopicErr   = "smartplant/" + plantId + "/errors";
  mqttTopicIn    = "smartplant/" + plantId + "/commands";
  mqttTopicBatch = "smartplant/" + plantId + "/measurement";
  lastUpload     = millis();

  Serial.print(F("⚠️  Errors topic: "));
  Serial.println(mqttTopicErr);
  Serial.print(F("📥 Topic in:  "));
  Serial.println(mqttTopicIn);
  Serial.print(F("📦 Batch topic: "));
  Serial.println(mqttTopicBatch);

  net.setInsecure();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setBufferSize(1024);
  mqtt.setCallback(callback);
  mqttReconnect();
}

void loop() {
  mqttReconnect();
  mqtt.loop();
  if (digitalRead(D7) == HIGH) {
    Serial.println(F("🔄 Reset Wi-Fi credentials"));
    delay(50);  // debounce
    if (digitalRead(D7) == HIGH) {
      resetCredentials();
    }
  }
  // Auto-send batch
  if (millis() - lastUpload >= T_UPLOAD) {
    Serial.println(F("⏰ Batch timeout reached"));
    publishFIFO();
  }

  // Read from Arduino
  if (softSerial.available()) {
    String raw = softSerial.readStringUntil('\n');
    raw.trim();

    // Telemetria JSON
    if (raw.length() && telemetry.parse(raw)) {
      float h = telemetry.getHumidity();
      float l = telemetry.getLight();
      String ts = telemetry.getTimestamp();
      Serial.printf("🔢 New sample: H=%.1f L=%.1f @%s\n", h, l, ts.c_str());
      enqueueSample(h, l, ts);
    }
    // Errori / OK da Arduino
    else if (raw.startsWith("err:")) {
      StaticJsonDocument<128> doc;
      
      doc["level"] = "error";
      int p1 = raw.indexOf(':');
      int p2 = raw.indexOf(':', p1 + 1);
      String code = raw.substring(p1 + 1, p2 == -1 ? raw.length() : p2);
      doc["code"] = code;
      if (p2 != -1) {
        float delta = raw.substring(p2 + 1).toFloat();
        doc["delta"] = delta;
      }
      doc["timestamp"] = telemetry.getTimestamp();
      String payload;
      serializeJson(doc, payload);

      // Pubblica errore (QoS 0, retain=false)
      bool ok = mqtt.publish(
        mqttTopicErr.c_str(),
        (const uint8_t*)payload.c_str(),
        payload.length(),
        /*retain=*/false
      );
      Serial.print(F("⚠️  Publish ERR → "));
      Serial.println(ok ? F("OK") : F("FAIL"));
    }
  }
}

// ─── helper functions ───
void enqueueSample(float hum, float light, const String& ts) {
  fifo[fifoHead] = {hum, light, ts};
  fifoHead = (fifoHead + 1) % FIFO_LEN;
  if (fifoCount < FIFO_LEN) {
    fifoCount++;
    Serial.printf("   FIFO count: %u/%u\n", fifoCount, FIFO_LEN);
    // alla prima volta che fifoCount diventa uguale a FIFO_LEN,
    // mando subito il burst:
    if (fifoCount == FIFO_LEN) {
      Serial.println(F("🎯 FIFO piena, invio burst immediato"));
      publishFIFO();
    }
  } else {
    // buffer già pieno, semplicemente sovrascrivo
    Serial.printf("   FIFO count: %u/%u (sovrascrittura)\n", fifoCount, FIFO_LEN);
  }
}

void publishFIFO() {
  if (fifoCount == 0) {
    Serial.println(F("⚠️  FIFO empty, nothing to send"));
    return;
  }
  Serial.printf("📊 Sending batch of %u samples\n", fifoCount);
  StaticJsonDocument<1024> doc;
  JsonArray arr = doc.to<JsonArray>();
  for (uint8_t i = 0; i < fifoCount; ++i) {
    uint8_t idx = (fifoHead + FIFO_LEN - fifoCount + i) % FIFO_LEN;
    JsonObject h = arr.createNestedObject();
    h["type"]      = "humidity";
    h["value"]     = fifo[idx].humidity;
    h["timestamp"] = fifo[idx].timestamp;
    JsonObject l = arr.createNestedObject();
    l["type"]      = "light";
    l["value"]     = fifo[idx].light;
    l["timestamp"] = fifo[idx].timestamp;
  }
  String payload;
  serializeJson(arr, payload);
  Serial.print(F("   Payload: "));
  Serial.println(payload);
  bool ok = mqtt.publish(mqttTopicBatch.c_str(), payload.c_str(), false);
  Serial.print(F("   mqtt.publish() → "));
  Serial.println(ok ? "OK" : "FAIL");
  if (ok) {
    fifoCount  = 0;
    lastUpload = millis();
    Serial.println(F("✅ Batch published, timer reset"));
  } else {
    Serial.print(F("❌ Publish failed, rc="));
    Serial.println(mqtt.state());
  }

}
