#include "HumiditySensor.h"
#include <EEPROM.h>

static const uint8_t ADDR_DRY  = 0;   // Indirizzo EEPROM per il valore "dry"
static const uint8_t ADDR_WET  = 2;   // Indirizzo EEPROM per il valore "wet"
static const uint8_t ADDR_FLAG = 4;   // Indirizzo EEPROM per il flag di calibrazione
static const uint8_t FLAG_OK   = 0xAB;// Flag che indica che dei valori di calibrazione sono disponibili

// Costruttore: memorizza il pin analogico per misurare l’umidità
HumiditySensor::HumiditySensor(uint8_t pin) : _pin(pin) {}

// Inizializzazione: si assicura che la EEPROM sia pronta (in caso di ESP8266) e
// carica i valori di calibrazione salvati
void HumiditySensor::begin() {
  eepromBeginIfNeeded();
  load();
  pinMode(_pin, INPUT);
}

// Inizializza l’EEPROM solo su ESP8266, su AVR è già pronta 
void HumiditySensor::eepromBeginIfNeeded() {
#ifdef ESP8266
  if (!EEPROM.begin(8)) Serial.println(F("[EEPROM] init error"));
#endif
}

// Carica i valori DRY e WET dalla EEPROM, se il flag è presente;
// altrimenti, usa valori di fallback predefiniti
void HumiditySensor::load() {
  if (EEPROM.read(ADDR_FLAG) == FLAG_OK) {
    _dry = EEPROM.read(ADDR_DRY) | (EEPROM.read(ADDR_DRY + 1) << 8); // Legge i due byte per DRY
    _wet = EEPROM.read(ADDR_WET) | (EEPROM.read(ADDR_WET + 1) << 8); // Legge i due byte per WET
  } else {
    _dry = DRY_DEFAULT;
    _wet = WET_DEFAULT;
  }
}

// Salva i valori DRY e WET in EEPROM e imposta il flag
void HumiditySensor::save() {
  EEPROM.update(ADDR_DRY,      _dry & 0xFF); // salva il byte meno significativo per DRY
  EEPROM.update(ADDR_DRY + 1, (_dry >> 8) & 0xFF); // salva il byte più significativo per DRY
  EEPROM.update(ADDR_WET,      _wet & 0xFF); // salva il byte meno significativo per WET
  EEPROM.update(ADDR_WET + 1, (_wet >> 8) & 0xFF); // salva il byte più significativo per WET
  EEPROM.update(ADDR_FLAG, FLAG_OK); // imposta il flag di calibrazione
#ifdef ESP8266
  EEPROM.commit();
#endif
}

// Legge la misura analogica grezza dal pin
uint16_t HumiditySensor::readRaw() {
  return analogRead(_pin);
}

// Converte la misura in percentuale di umidità, regolando tra WET e DRY
float HumiditySensor::readPercent() {
  uint16_t r = readRaw();
  if (_dry <= _wet) {
    return NAN; // se la calibrazione non è logica
  }
  // Calcola l’umidità percentuale normalizzando la lettura grezza r
  // sulla scala definita da _dry (0%) e _wet (100%):
  //   pct = 100 * ( dry – r ) / ( dry – wet )
  // - r == dry -> pct =   0%
  // - r == wet -> pct = 100%
  float pct = 100.0f * (_dry - r) / (_dry - _wet);
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

// Calibrazione come valore DRY acquisendo la lettura attuale e salvando in EEPROM
void HumiditySensor::calibrateDry() {
  _dry = readRaw();
  save();
}

// Calibrazione come valore WET acquisendo la lettura attuale e salvando in EEPROM
void HumiditySensor::calibrateWet() {
  _wet = readRaw();
  save();
}

// Ripristina la calibrazione ai valori di default
void HumiditySensor::resetCalibration() {
  EEPROM.write(ADDR_FLAG, 0x00);  
#ifdef ESP8266
  EEPROM.commit();
#endif
  _dry = DRY_DEFAULT; 
  _wet = WET_DEFAULT;
}

// Restituisce il valore DRY attuale
uint16_t HumiditySensor::getDry() {
  return _dry;
}

// Restituisce il valore WET attuale
uint16_t HumiditySensor::getWet() {
  return _wet;
}

