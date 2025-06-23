#ifndef LIGHT_SENSOR_H
#define LIGHT_SENSOR_H

#include <Arduino.h>

class LightSensor {
  uint8_t _pin;

public:
  LightSensor(uint8_t pin);

  void begin();
  uint16_t readRaw();       // Lettura grezza (0–1023)
  float readPercent();      // Percentuale 0–100%
};

#endif
