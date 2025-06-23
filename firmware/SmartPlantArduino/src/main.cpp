// Questo codice fa parte del firmware SmartPlant per Arduino.
// Legge i livelli di umidità e luce, controlla una pompa per l'irrigazione,
// e comunica con un NodeMCU tramite SoftwareSerial.
#include <Arduino.h>
#include <SoftwareSerial.h>
#include "HumiditySensor.h"
#include "InitSmartPlant.h"
#include "LightSensor.h"

#define T_READ 10000        // Intervallo di lettura
#define PUMP_PIN 8          // Pin digitale della pompa
#define PUMP_TIMEOUT 60000  // Tempo massimo di attivazione della pompa 60 s
#define HUM_SETTLE_MS 5000  // Tempo di assestamento dopo irrigazione 5 s
#define HUM_THRESHOLD 1     // Differenza di umidità per considerare pompa funzionante

// SoftwareSerial su pin D2 (RX) e D3 (TX)
SoftwareSerial softSerial(2, 3); // RX, TX

HumiditySensor hum(A0);      // Umidità sul pin analogico A0
LightSensor light(A1);       // Fotoresistore sul pin analogico A1
InitSmartPlant plant;        // Inizializzazione SmartPlant  

void setup() {
  Serial.begin(9600); // Serial Monitor
  softSerial.begin(9600); // Comunicazione seriale con NodeMCU 

  hum.begin();   // Inizializza classe sensore umidità
  light.begin(); // Inizializza classe sensore luce
  plant.begin(); // Inizializza classe SmartPlant

  pinMode(PUMP_PIN, OUTPUT); // Imposta il pin digitale della pompa come output
  digitalWrite(PUMP_PIN, LOW);  // Pompa inizialmente spenta

  if (!plant.hasValidPlantId()) {
    // Serial.println(F("scrittura plant_id in EEPROM..."));
    plant.writePlantIdOnce("PLANT-9F7C");
  }

  // Serial.println(F("SmartPlant Arduino avviato."));
}

void loop() {
  if (softSerial.available()) {
    String cmd = softSerial.readStringUntil('\n'); // Legge il comando fino a newline
    cmd.trim(); 
    // Serial.print(F("Comando ricevuto: ")); 
    // Serial.println(cmd);

    if (cmd == "calDry") { // Comando di calibrazione secco
      hum.calibrateDry();
      // Serial.println(F("Calibrazione DRY eseguita"));
    } else if (cmd == "calWet") { // Comando di calibrazione bagnato
      hum.calibrateWet();
      // Serial.println(F("Calibrazione WET eseguita"));
    } 

else if (cmd.startsWith("water")) {
  int sep = cmd.indexOf(':'); // Trova il separatore tra comando e durata dell'irrigazione
  if (sep == -1) sep = cmd.indexOf(' '); // Prova anche con spazio
  uint32_t duration = 15000;                   // default 15 s
  if (sep != -1) { // Se c'è un separatore, leggi la durata
    duration = cmd.substring(sep + 1).toInt(); // Converte la parte dopo il separatore in intero
    if (duration == 0) duration = 15000; // Se la conversione fallisce, usa il default
  }
  if (duration > PUMP_TIMEOUT) duration = PUMP_TIMEOUT; // fail-safe

  float humBefore = hum.readPercent();
  // Serial.print(F("Irrigazione, H0 = "));
  // Serial.print(humBefore, 1);
  // Serial.print(F("%  per "));
  // Serial.print(duration);
  // Serial.println(F(" ms"));

  digitalWrite(PUMP_PIN, HIGH); // Accende la pompa
  delay(duration); // Irriga per la durata specificata
  digitalWrite(PUMP_PIN, LOW); // Spegne la pompa

  delay(HUM_SETTLE_MS); // Attende che il terreno si stabilizzi dopo l'irrigazione

  float humAfter = hum.readPercent(); // Legge l'umidità dopo l'irrigazione
  float delta = humAfter - humBefore; // Calcola la differenza

  // Serial.print(F("H1 = "));
  // Serial.print(humAfter, 1);
  // Serial.print(F("ΔH = "));
  // Serial.print(delta, 1);
  // Serial.println(F("%"));

  if (isnan(humBefore) || isnan(humAfter)) { // Controlla se le letture sono valide
    softSerial.println("err:sensor");               // lettura fallita
  } else if (delta < HUM_THRESHOLD) { 
    // malfunzionamento: pompa guasta / serbatoio vuoto / tubo scollegato
    softSerial.print("err:pump:");
    softSerial.println(delta, 1);                   // es. "err:pump:0.7"
  } 
  }
  else {
      //Serial.println(F("Comando non riconosciuto"));
    }
  }

  static uint32_t t0 = 0;
  if (millis() - t0 > T_READ) {
    t0 = millis(); 

    uint16_t rawHum = hum.readRaw(); // Lettura grezza dell'umidità
    float pctHum = hum.readPercent(); // Lettura percentuale dell'umidità
    uint16_t rawLight = light.readRaw(); // Lettura grezza della luce
    float pctLight = light.readPercent(); // Lettura percentuale della luce

    // Serial.print(F("Umidità grezza: ")); Serial.println(rawHum);
    // Serial.print(F("Umidità: ")); Serial.print(pctHum, 1); Serial.println(" %");
    // Serial.print(F("Luce grezza: ")); Serial.println(rawLight);
    // Serial.print(F("Luce: ")); Serial.print(pctLight, 1); Serial.println(" %");
    // Serial.print("dry = "); Serial.println(hum.getDry());
    // Serial.print("wet = "); Serial.println(hum.getWet());

    softSerial.print("{\"humidity\":");
    softSerial.print(pctHum, 1);
    softSerial.print(",\"light\":");
    softSerial.print(pctLight, 1);
    softSerial.println("}");
  }
}
