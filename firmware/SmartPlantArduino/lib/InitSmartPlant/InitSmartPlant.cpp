#include "InitSmartPlant.h"
// Il plant_id è memorizzato in EEPROM a partire dall'indirizzo specificato e occupa 12 byte.
// Il flag di presenza è memorizzato al byte successivo (13° byte) per indicare se il plant_id è stato già scritto e evitare così scritture non necessarie.

// Costruttore: inizializza l'indirizzo di partenza in EEPROM
InitSmartPlant::InitSmartPlant(uint16_t eeprom_addr) : _addr(eeprom_addr) {}

// Inizializza eventuali risorse necessarie per EEPROM (solo per ESP8266/ESP32 in caso di porting futuro su NodeMCU)
void InitSmartPlant::begin() {
#ifdef ESP8266
  EEPROM.begin(64);  // solo per ESP8266/ESP32
#endif
}

// Controlla se il flag di presenza plant_id era stato già impostato in EEPROM (True in caso positivo)
bool InitSmartPlant::checkFlag() {
  return EEPROM.read(_addr + 12) == FLAG;
}

// Imposta il flag di presenza plant_id in EEPROM
void InitSmartPlant::setFlag() {
  EEPROM.write(_addr + 12, FLAG);
#ifdef ESP8266
  EEPROM.commit();
#endif
}

// Verifica se esiste un plant_id valido in EEPROM
bool InitSmartPlant::hasValidPlantId() {
  return checkFlag();
}

// Restituisce il plant_id salvato in EEPROM come stringa
String InitSmartPlant::getPlantId() {
  String id = "";
  for (int i = 0; i < 12; ++i) {
    char c = EEPROM.read(_addr + i);
    if (c == '\0') break; // termina se trova il carattere di fine stringa
    id += c;
  }
  return id;
}

// Scrive il plant_id in EEPROM solo se non già presente
void InitSmartPlant::writePlantIdOnce(const String& plant_id) {
  if (checkFlag()) return;  // già scritto

  int len = min(12, plant_id.length()); // massimo 12 caratteri
  // scrittura del plant_id in EEPROM
  for (int i = 0; i < len; ++i) {
    EEPROM.write(_addr + i, plant_id[i]);
  }
  if (len < 12) EEPROM.write(_addr + len, '\0'); // aggiunge terminatore se necessario
  setFlag(); // imposta il flag di presenza plant_id
#ifdef ESP8266
  EEPROM.commit();
#endif
}