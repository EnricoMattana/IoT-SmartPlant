#include "HumiditySensor.h"
#include <EEPROM.h>

// Global constants variables. Static since they are not used outside this file. Consst since they are not modified. 
static const uint8_t ADDR_DRY  = 0;   // Base address for dry value
static const uint8_t ADDR_WET  = 2;   // Base address for wet value
static const uint8_t  ADDR_FLAG = 4;   // Base address for flag value
static const uint8_t  FLAG_OK   = 0xAB;

HumiditySensor::HumiditySensor(uint8_t pin) : _pin(pin) {}

void HumiditySensor::begin() {
  eepromBeginIfNeeded(); //Initialize EEPROM if needed. Used only on NodeMCU.
  load(); // Load calibration values from EEPROM
  pinMode(_pin, INPUT); // Set pin as input
}

void HumiditySensor::eepromBeginIfNeeded() {
#ifdef ESP8266
  if (!EEPROM.begin(8)) Serial.println(F("[EEPROM] init error"));
#endif
}

void HumiditySensor::load() {
  if (EEPROM.read(ADDR_FLAG) == FLAG_OK) {
    _dry =  EEPROM.read(ADDR_DRY) | (EEPROM.read(ADDR_DRY + 1) << 8);
    _wet =  EEPROM.read(ADDR_WET) | (EEPROM.read(ADDR_WET + 1) << 8);
  } else {
    // valori di fallback sensati
    _dry = DRY_DEFAULT;
    _wet = WET_DEFAULT;
  }
}

void HumiditySensor::save() {
  EEPROM.update(ADDR_DRY,      _dry & 0xFF);
  EEPROM.update(ADDR_DRY + 1, (_dry >> 8) & 0xFF);
  EEPROM.update(ADDR_WET,      _wet & 0xFF);
  EEPROM.update(ADDR_WET + 1, (_wet >> 8) & 0xFF);
  EEPROM.update(ADDR_FLAG, FLAG_OK);
#ifdef ESP8266
  EEPROM.commit();
#endif
}

uint16_t HumiditySensor::readRaw() {
  return analogRead(_pin);
}

float HumiditySensor::readPercent() {
  uint16_t r = readRaw();
  if (_dry <= _wet) {  
    return NAN;
  }
  float pct = 100.0f * (_dry - r) / (_dry - _wet);
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

void HumiditySensor::calibrateDry() {
  _dry = readRaw();
  save();
}

void HumiditySensor::calibrateWet() {
  _wet = readRaw();
  save();
}

void HumiditySensor::resetCalibration() {
  EEPROM.write(ADDR_FLAG, 0x00);  
#ifdef ESP8266
  EEPROM.commit();
#endif
  _dry = DRY_DEFAULT; 
  _wet = WET_DEFAULT;
}

uint16_t HumiditySensor::getDry() {
  return _dry;
}

uint16_t HumiditySensor::getWet() {
  return _wet;
}

