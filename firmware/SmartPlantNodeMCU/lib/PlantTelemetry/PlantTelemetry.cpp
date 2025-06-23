#include "PlantTelemetry.h"
#include <ArduinoJson.h>
#include <time.h>

bool PlantTelemetry::parse(const String& input) {
    StaticJsonDocument<64> doc;              // Buffer per il parsing di piccoli JSON
    DeserializationError err = deserializeJson(doc, input);
    if (err) return false;      // Se c’è un errore, non procede oltre
    if (!doc.containsKey("humidity") || !doc.containsKey("light")) return false;
    humidity = doc["humidity"].as<float>();
    light    = doc["light"].as<float>();
    return true;
}

String PlantTelemetry::getTimestamp() const {
    time_t now = time(nullptr);
    struct tm* t = gmtime(&now);
    char buf[25];
    // Esempio di formato: 2025-06-23T15:23:01Z
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", t);
    return String(buf);
}

String PlantTelemetry::buildPayload() {
    StaticJsonDocument<256> doc;             // Buffer per contenere l’array di oggetti JSON
    JsonArray arr = doc.to<JsonArray>();

    JsonObject h = arr.createNestedObject();
    h["type"]      = "humidity";
    h["value"]     = humidity;
    h["timestamp"] = getTimestamp();

    JsonObject l = arr.createNestedObject();
    l["type"]      = "light";
    l["value"]     = light;
    l["timestamp"] = getTimestamp();

    String output;
    serializeJson(arr, output);
    return output;
}
