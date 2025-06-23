#ifndef PLANT_TELEMETRY_H
#define PLANT_TELEMETRY_H

#include <Arduino.h>
#include <ArduinoJson.h>

class PlantTelemetry {
public:
    // Parso il JSON raw da Arduino
    bool parse(const String& input);

    // Costruisco un payload JSON con due oggetti (humidity, light)
    String buildPayload();

    // Getters per la FIFO
    float getHumidity() const { return humidity; }
    float getLight()    const { return light;    }

    // Timestamp ISO-8601
    String getTimestamp() const;

private:
    float humidity = NAN;
    float light    = NAN;
};

#endif
