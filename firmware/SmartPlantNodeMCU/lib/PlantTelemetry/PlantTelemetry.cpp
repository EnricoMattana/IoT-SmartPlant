#include "PlantTelemetry.h"
#include <ArduinoJson.h>
#include <time.h>

// --- parse() ---
bool PlantTelemetry::parse(const String& input) {
    StaticJsonDocument<64> doc;              // 64 B bastano per {"humidity":x,"light":y}
    DeserializationError err = deserializeJson(doc, input);
    if (err) return false;
    if (!doc.containsKey("humidity") || !doc.containsKey("light")) return false;
    humidity = doc["humidity"].as<float>();
    light    = doc["light"].as<float>();
    return true;
}

// --- timestamp ISO8601 ---
String PlantTelemetry::getTimestamp() const {
    time_t now = time(nullptr);
    struct tm* t = gmtime(&now);
    char buf[25];
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", t);
    return String(buf);
}

// --- buildPayload() ---
String PlantTelemetry::buildPayload() {
    StaticJsonDocument<256> doc;             // 256 B per 2 oggetti JSON
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
