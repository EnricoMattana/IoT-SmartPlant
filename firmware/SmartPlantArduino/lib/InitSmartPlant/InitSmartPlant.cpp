// InitSmartPlant.cpp
#include "InitSmartPlant.h"

InitSmartPlant::InitSmartPlant(uint16_t eeprom_addr) : _addr(eeprom_addr) {}

void InitSmartPlant::begin() {
#ifdef ESP8266
  EEPROM.begin(64);  // solo per ESP8266/ESP32
#endif
}

bool InitSmartPlant::checkFlag() {
  return EEPROM.read(_addr + 12) == FLAG;
}

void InitSmartPlant::setFlag() {
  EEPROM.write(_addr + 12, FLAG);
#ifdef ESP8266
  EEPROM.commit();
#endif
}

bool InitSmartPlant::hasValidPlantId() {
  return checkFlag();
}

String InitSmartPlant::getPlantId() {
  String id = "";
  for (int i = 0; i < 12; ++i) {
    char c = EEPROM.read(_addr + i);
    if (c == '\0') break;
    id += c;
  }
  return id;
}

void InitSmartPlant::writePlantIdOnce(const String& plant_id) {
  if (checkFlag()) return;  // già scritto

  int len = min(12, plant_id.length());
  for (int i = 0; i < len; ++i) {
    EEPROM.write(_addr + i, plant_id[i]);
  }
  if (len < 12) EEPROM.write(_addr + len, '\0');
  setFlag();
#ifdef ESP8266
  EEPROM.commit();
#endif
}