#ifndef HUMIDITY_SENSOR_H
#define HUMIDITY_SENSOR_H

#include <Arduino.h>

static const uint16_t DRY_DEFAULT = 786;
static const uint16_t WET_DEFAULT = 384;

class HumiditySensor {
  public:
    explicit HumiditySensor(uint8_t pin);

    void begin();               // Inizializza e carica calibrazione
    uint16_t readRaw();         // Valore ADC grezzo
    float readPercent();        // umidità percentuale
    void calibrateDry();        // Fondoscala “secco”
    void calibrateWet();        // Fondoscala “bagnato”
    void resetCalibration();    
    uint16_t getDry();   // restituisce il valore di fondo scala secco
    uint16_t getWet();   // restituisce il valore di fondo scala bagnato


  private:
    const uint8_t _pin;
    uint16_t _dry = DRY_DEFAULT;       // default value
    uint16_t _wet = WET_DEFAULT;       // default value

    // EEPROM helpers
    void load();
    void save();
    void eepromBeginIfNeeded();
};

#endif
