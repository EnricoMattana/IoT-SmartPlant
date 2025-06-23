#ifndef PLANT_TELEMETRY_H
#define PLANT_TELEMETRY_H

#include <Arduino.h>
#include <ArduinoJson.h>

class PlantTelemetry {
public:
    bool parse(const String& input);

    String buildPayload();

    float getHumidity() const { return humidity; }
    float getLight()    const { return light;    }

    String getTimestamp() const;

private:
    float humidity = NAN;
    float light    = NAN;
};

#endif
