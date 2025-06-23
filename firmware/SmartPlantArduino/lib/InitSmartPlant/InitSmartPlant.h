// InitSmartPlant.h
#ifndef INIT_SMART_PLANT_H
#define INIT_SMART_PLANT_H

#include <Arduino.h>
#include <EEPROM.h>

class InitSmartPlant {
  public:
    InitSmartPlant(uint16_t eeprom_addr = 0);

    void begin();
    String getPlantId();
    bool hasValidPlantId();
    void writePlantIdOnce(const String& plant_id);

  private:
    const uint8_t FLAG = 0xA5;
    uint16_t _addr;

    bool checkFlag();
    void setFlag();
};

#endif
