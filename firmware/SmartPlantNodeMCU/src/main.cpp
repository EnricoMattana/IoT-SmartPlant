#include <Arduino.h>           // Libreria di base Arduino
#include <ESP8266WiFi.h>       // Gestione Wi-Fi per il NodeMCU ESP8266
#include <WiFiClientSecure.h>  
#include <WiFiManager.h>       // Interfaccia utente per configurazione Wi-Fi
#define MQTT_MAX_PACKET_SIZE 1024
#include <PubSubClient.h>      // Libreria MQTT
#include <SoftwareSerial.h>    // Porta seriale software (usata per comunicare con Arduino)
#include <LittleFS.h>          // File system interno all’ESP8266
#include "PlantTelemetry.h"    // Classe per decodificare messaggi telemetrici dal firmware Arduino
#include <time.h>              // Funzioni e strutture per gestione ora e data (NTP)

// Impostazioni per FIFO: archiviazione di un certo numero di campioni prima di spedirli
constexpr uint8_t  FIFO_LEN = 6;          // Dimensione massima del buffer
constexpr uint32_t T_UPLOAD = 60 * 1000;  // Invio batch ogni 60 secondi

// Dichiarazioni di funzione
void enqueueSample(float hum, float light, const String& ts); 
void publishFIFO();

// Struttura dati per un singolo campione
struct Sample {
  float   humidity;   // Umidità letta
  float   light;      // Luminosità letta
  String  timestamp;  // Timestamp relativo al campione
};

// Array circolare per memorizzare i campioni
Sample   fifo[FIFO_LEN];
uint8_t  fifoHead   = 0;       // Indice successivo in cui salvare
uint8_t  fifoCount  = 0;       // Numero di elementi nella FIFO
uint32_t lastUpload = 0;       // Tempo dell’ultimo invio batch

// Variabili globali per definire i topic MQTT (inviati e ricevuti)
String mqttTopicOut;
String mqttTopicIn;
String mqttTopicBatch;
String mqttTopicErr;  //Topic per eventuali errori

#ifndef RESET_BTN_PIN
#define RESET_BTN_PIN D4 // Pin per resettare la configurazione Wi-Fi
#endif

// Porta seriale software collegata ad Arduino
constexpr uint8_t RX_PIN = D2, TX_PIN = D3;
SoftwareSerial softSerial(RX_PIN, TX_PIN);

// Parametri connessione MQTT (broker, porta, credenziali)
const char* MQTT_BROKER = "2cf8c9d8d17f48c3a7c23442276b3ce4.s1.eu.hivemq.cloud";
const uint16_t MQTT_PORT = 8883;
const char* MQTT_USER   = "smartplant-users";
const char* MQTT_PASS   = "IoTPlant2025";

// Oggetti per la connessione Wi-Fi e MQTT
WiFiClientSecure net;
PubSubClient mqtt(net);
WiFiManager wm;         // Gestione user-friendly delle credenziali Wi-Fi
PlantTelemetry telemetry; 
String plantId;         // ID pianta letto/salvato su LittleFS

// —————— Funzioni LittleFS ——————
// Legge l’ID pianta dal file system interno (se presente)
String readPlantId() {
  if (!LittleFS.exists("/plant_id.txt")) return "";
  File f = LittleFS.open("/plant_id.txt", "r");
  String id = f.readStringUntil('\n');
  f.close();
  id.trim();
  return id;
}

// Scrive il plant id solo nel caso non sia già presente
void writePlantId(const String& id) {
  if (readPlantId().length()) return;
  File f = LittleFS.open("/plant_id.txt", "w");
  f.println(id);
  f.close();
}

//Funzione per resettare le credenziali Wi-Fi, usata se il pulsante è premuto
void resetCredentials() {
  // Serial.println(F("Reset Wi-Fi credenziali"));
  wm.resetSettings();  // Elimina le impostazioni salvate
  ESP.restart();       // Riavvia il modulo
}

//Funzione per riconnettersi al broker MQTT
void mqttReconnect() {
  static uint32_t lastTry = 0;
  if (mqtt.connected()) return;             // Se già connesso, non fare nulla
  if (millis() - lastTry < 5000) return;    // Evita loop infiniti di riconnessione
  lastTry = millis();

  // Serial.println(F("MQTT reconnect attempt..."));
  if (mqtt.connect("SmartPlantNode", MQTT_USER, MQTT_PASS)) {
    // Se la connessione va a buon fine
    // Serial.println(F("MQTT connected"));
    mqtt.subscribe(mqttTopicIn.c_str());    // Iscrizione al topic di input
    // Serial.print(F("Subscribed to: "));
    // Serial.println(mqttTopicIn);
  } else {
    // Se la connessione fallisce
    // Serial.print(F("MQTT connect failed, rc="));
    // Serial.println(mqtt.state());
  }
}

// Callback quando arriva un pacchetto MQTT
void callback(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; ++i) msg += (char)payload[i];
  msg.trim();
  //Serial.printf("MQTT-IN  %s → %s\n", topic, msg.c_str());

  // 2) Plain-text send_now
  if (msg == "send_now") {
    //Serial.println(F("CMD send_now (plain): invio ultimissime misure"));
    publishFIFO();
    return;
  }
  else { 
  // 3) Fallback → Arduino
  //Serial.println(F("Forward plain-text to Arduino"));
  softSerial.println(msg);
  }
}

// Sincronizzazione oraria via NTP 
void setupNTP() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");  // Impostazione server NTP
  // Serial.print(F("NTP sync..."));
  while (time(nullptr) < 1700000000) {
    // Serial.print(F("."));
    delay(500);
  }
  // Serial.println(F(" done"));
}

void setup() {
  Serial.begin(9600);          // Porta seriale hardware
  softSerial.begin(9600);      // Porta seriale software per comunicare con Arduino
  // Serial.println(F("\nSmartPlant NodeMCU boot"));

  pinMode(D7, INPUT_PULLUP);   // Pulsante reset Wi-Fi se necessario

  // Inizializza il file system LittleFS
  if (!LittleFS.begin()) {
    // Serial.println(F("LittleFS init failed"));
    while (1);
  }

  // Configurazione Wi-Fi manager con timeout di 120 secondi
  wm.setTimeout(120);
  if (!wm.autoConnect("SmartPlant-Setup")) {
    // Serial.println(F("Wi-Fi setup fail"));
    ESP.restart();
    }
  // Serial.println(WiFi.SSID());

  // Sincronizzazione oraria
  setupNTP();

  writePlantId("PLANT-9F7C");
  plantId = readPlantId();
  // Serial.print(F("Plant ID: "));
  // Serial.println(plantId);

  // Costruisci i topic MQTT
  mqttTopicErr   = "smartplant/" + plantId + "/errors";
  mqttTopicIn    = "smartplant/" + plantId + "/commands";
  mqttTopicBatch = "smartplant/" + plantId + "/measurement";
  lastUpload     = millis();

  /* 
  Serial.print(F("Errors topic: "));
  Serial.println(mqttTopicErr);
  Serial.print(F("Topic in:  "));
  Serial.println(mqttTopicIn);
  Serial.print(F("Batch topic: "));
  Serial.println(mqttTopicBatch);
  */
  // Configura connessione sicura
  net.setInsecure();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setBufferSize(1024);
  mqtt.setCallback(callback);
  mqttReconnect();
}

void loop() {
  // Tenta di riconnetterci a MQTT se serve
  mqttReconnect();
  mqtt.loop();

  // Se il pulsante su pin D7 viene premuto, resetta Wi-Fi
  if (digitalRead(D7) == HIGH) {
    // Serial.println(F("Reset Wi-Fi credentials"));
    delay(50);  
    if (digitalRead(D7) == HIGH) {
      resetCredentials();
    }
  }

  // Se è ora di inviare un batch (superato T_UPLOAD)
  if (millis() - lastUpload >= T_UPLOAD) {
    // Serial.println(F("Batch timeout reached"));
    publishFIFO();
  }

  // Controlla se sono arrivati dati dalla seriale software (Arduino)
  if (softSerial.available()) {
    String raw = softSerial.readStringUntil('\n');
    raw.trim();

    // Tenta di fare parsing dei dati come telemetria JSON
    if (raw.length() && telemetry.parse(raw)) {
      float h = telemetry.getHumidity();
      float l = telemetry.getLight();
      String ts = telemetry.getTimestamp();
      // Serial.printf("New sample: H=%.1f L=%.1f @%s\n", h, l, ts.c_str());
      enqueueSample(h, l, ts);
    }
    // Se inizia con "err:" lo consideriamo un messaggio di errore da Arduino
    else if (raw.startsWith("err:")) {
      StaticJsonDocument<128> doc;
      doc["level"] = "error";

      // Estrae codice e valore dall’errore
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

      // Pubblica l’errore sul topic dedicato
      bool ok = mqtt.publish(
        mqttTopicErr.c_str(),
        (const uint8_t*)payload.c_str(),
        payload.length(),
        false
      );
      Serial.print(F("⚠️  Publish ERR → "));
      Serial.println(ok ? F("OK") : F("FAIL"));
    }
  }
}

// Enqueue: aggiunge un campione al FIFO circolare
void enqueueSample(float hum, float light, const String& ts) {
  fifo[fifoHead] = {hum, light, ts};
  fifoHead = (fifoHead + 1) % FIFO_LEN;
  if (fifoCount < FIFO_LEN) {
    fifoCount++;
    // Serial.printf("FIFO count: %u/%u\n", fifoCount, FIFO_LEN);
    // Se la FIFO arriva a dimensione massima, invio immediato
    if (fifoCount == FIFO_LEN) {
      // Serial.println(F("FIFO piena, invio burst immediato"));
      publishFIFO();
    }
  } else {
    // Se già pieno, sovrascrive i campioni meno recenti
    // Serial.printf("   FIFO count: %u/%u (sovrascrittura)\n", fifoCount, FIFO_LEN);
  }
}

// publishFIFO: invia via MQTT tutti i campioni raccolti, quindi resetta buffer
void publishFIFO() {
  if (fifoCount == 0) {
    // Serial.println(F("FIFO empty, nothing to send"));
    return;
  }
  // Serial.printf("Sending batch of %u samples\n", fifoCount);

  // Crea un array JSON con coppie di misure (umidità e luce)
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

  // Converte l’array JSON in stringa
  String payload;
  serializeJson(arr, payload);
  Serial.print(F("   Payload: "));
  Serial.println(payload);

  // Pubblica su MQTT e stampa l’esito
  bool ok = mqtt.publish(mqttTopicBatch.c_str(), payload.c_str(), false);
  Serial.print(F("   mqtt.publish() → "));
  Serial.println(ok ? "OK" : "FAIL");
  if (ok) {
    fifoCount  = 0;                // Svuota la FIFO
    lastUpload = millis();         // Reset del timer
    // Serial.println(F("Batch published, timer reset"));
  } else {
    // Serial.print(F("Publish failed, rc="));
    // Serial.println(mqtt.state());
  }

}
