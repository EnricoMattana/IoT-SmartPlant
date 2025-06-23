#include <Arduino.h>
#include <SoftwareSerial.h>
#include "HumiditySensor.h"
#include "InitSmartPlant.h"
#include "LightSensor.h"

#define T_READ 10000        // 30 minuti
#define PUMP_PIN 8          // 🧯 pin digitale per attivazione pompa (ex pin 8)
#define PUMP_TIMEOUT 60000 // Timeout pompa 30 s
#define HUM_SETTLE_MS 5000 // Attesa assestamento umidità 5 s
#define HUM_THRESHOLD 1  // Soglia di umidità per considerare pompa funzionante
// SoftwareSerial su pin D2 (RX) e D3 (TX)
SoftwareSerial softSerial(2, 3); // RX, TX

HumiditySensor hum(A0);      // Umidità su A0
LightSensor light(A1);       // Fotoresistore su A1
InitSmartPlant plant;

void setup() {
  Serial.begin(9600);
  softSerial.begin(9600);

  hum.begin();
  light.begin();
  plant.begin();

  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);  // Pompa inizialmente spenta

  if (!plant.hasValidPlantId()) {
    Serial.println(F("🔧 Primo avvio: scrittura plant_id in EEPROM..."));
    plant.writePlantIdOnce("PLANT-9F7C");
  }

  Serial.println(F("🌿 SmartPlant Arduino avviato."));
}

void loop() {
  // ─── GESTIONE COMANDI ───
  if (softSerial.available()) {
    String cmd = softSerial.readStringUntil('\n');
    cmd.trim();
    Serial.print(F("📨 Comando ricevuto: ")); Serial.println(cmd);

    if (cmd == "calDry") {
      hum.calibrateDry();
      Serial.println(F("✅ Calibrazione DRY eseguita"));
    } else if (cmd == "calWet") {
      hum.calibrateWet();
      Serial.println(F("✅ Calibrazione WET eseguita"));
    } // --------------------------------------------------------------
// ► Comando “water <dur_ms>”  oppure  “water:<dur_ms>”
// --------------------------------------------------------------
else if (cmd.startsWith("water")) {
  // — Estraggo la durata —
  int sep = cmd.indexOf(':');
  if (sep == -1) sep = cmd.indexOf(' ');
  uint32_t duration = 15000;                   // default 15 s
  if (sep != -1) {
    duration = cmd.substring(sep + 1).toInt();
    if (duration == 0) duration = 15000;
  }
  if (duration > PUMP_TIMEOUT) duration = PUMP_TIMEOUT; // fail-safe

  // — Misura iniziale —
  float humBefore = hum.readPercent();
  Serial.print(F("🚿 Irrigazione, H0 = "));
  Serial.print(humBefore, 1);
  Serial.print(F("%  per "));
  Serial.print(duration);
  Serial.println(F(" ms"));

  // — Avvio pompa —
  digitalWrite(PUMP_PIN, HIGH);
  delay(duration);
  digitalWrite(PUMP_PIN, LOW);

  // — Attendo assestamento terreno —
  delay(HUM_SETTLE_MS);

  // — Misura finale —
  float humAfter = hum.readPercent();
  float delta = humAfter - humBefore;

  Serial.print(F("🌡  H1 = "));
  Serial.print(humAfter, 1);
  Serial.print(F("%  ΔH = "));
  Serial.print(delta, 1);
  Serial.println(F("%"));

  // — Esito —
  if (isnan(humBefore) || isnan(humAfter)) {
    softSerial.println("err:sensor");               // lettura fallita
  } else if (delta < HUM_THRESHOLD) {
    // malfunzionamento: pompa guasta / serbatoio vuoto / tubo scollegato
    softSerial.print("err:pump:");
    softSerial.println(delta, 1);                   // es. "err:pump:0.7"
  } 
}

 else {
      Serial.println(F("⚠️  Comando non riconosciuto"));
    }
  }

  // ─── LETTURA SENSORI ───
  static uint32_t t0 = 0;
  if (millis() - t0 > T_READ) {
    t0 = millis();

    uint16_t rawHum = hum.readRaw();
    float pctHum = hum.readPercent();
    uint16_t rawLight = light.readRaw();
    float pctLight = light.readPercent();

    Serial.println(F("──────────────"));
    Serial.print(F("📥 Umidità grezza: ")); Serial.println(rawHum);
    Serial.print(F("🌱 Umidità: ")); Serial.print(pctHum, 1); Serial.println(" %");
    Serial.print(F("💡 Luce grezza: ")); Serial.println(rawLight);
    Serial.print(F("🔆 Luce: ")); Serial.print(pctLight, 1); Serial.println(" %");
    Serial.print("dry = "); Serial.println(hum.getDry());
    Serial.print("wet = "); Serial.println(hum.getWet());

    softSerial.print("{\"humidity\":");
    softSerial.print(pctHum, 1);
    softSerial.print(",\"light\":");
    softSerial.print(pctLight, 1);
    softSerial.println("}");
  }
}
