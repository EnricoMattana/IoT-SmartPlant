#include "LightSensor.h"
#include <Arduino.h>

LightSensor::LightSensor(uint8_t pin) : _pin(pin) {}

void LightSensor::begin() {
  // Nessuna inizializzazione necessaria per ora
}

uint16_t LightSensor::readRaw() {
  return analogRead(_pin);
}

float LightSensor::readPercent() {
  uint16_t value = analogRead(_pin);

  // Inverti la logica: luce forte = valore analogico bassa: percentuale alta
  float pct = 100.0f - (100.0f * value / 1023.0f);

  // Clamp tra 0 e 100%
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;

  return pct;
}

