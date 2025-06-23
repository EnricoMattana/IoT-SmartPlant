#ifndef INIT_SMART_PLANT_H
#define INIT_SMART_PLANT_H

#include <Arduino.h>
#include <EEPROM.h>

// Classe per la gestione dell'inizializzazione e identificazione della SmartPlant tramite EEPROM
class InitSmartPlant {
  public:
    // Costruttore: permette di specificare l'indirizzo EEPROM (default 0)
    InitSmartPlant(uint16_t eeprom_addr = 0);

    // Inizializza eventuali risorse necessarie
    void begin();

    // Restituisce il plant_id salvato in EEPROM
    String getPlantId();

    // Verifica se esiste un plant_id valido in EEPROM (permette di evitare scritture non necessarie)
    bool hasValidPlantId();

    // Scrive il plant_id in EEPROM solo se non già presente 
    void writePlantIdOnce(const String& plant_id);

  private:
    const uint8_t FLAG = 0xA5; // Flag per identificare la presenza del plant_id
    uint16_t _addr;            // Indirizzo di partenza in EEPROM

    // Controlla se il flag è presente in EEPROM
    bool checkFlag();

    // Imposta il flag in EEPROM
    void setFlag();
};

#endif
