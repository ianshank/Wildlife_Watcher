#include "wildlife/net_mqtt.h"

#include <ArduinoJson.h>
#include <base64.hpp>

namespace wildlife {

void MqttPublisher::begin() {
    client_.setBufferSize(24 * 1024);
    client_.setKeepAlive(45);
    client_.setSocketTimeout(15);
    client_.setServer(credentials_.mqtt_broker, credentials_.mqtt_port);
}

void MqttPublisher::ensure_connected() {
    while (!client_.connected()) {
        Serial.printf("[wildlife][I] MQTT connecting to %s:%u\n", credentials_.mqtt_broker, credentials_.mqtt_port);

        StaticJsonDocument<96> will_doc;
        will_doc["state"] = "offline";
        will_doc["node_id"] = credentials_.node_id;
        char will_buffer[96];
        const std::size_t will_length = serializeJson(will_doc, will_buffer, sizeof(will_buffer));

        const bool ok = client_.connect(
            credentials_.node_id,
            credentials_.mqtt_user,
            credentials_.mqtt_password,
            topics_.status.data(),
            1,
            true,
            will_buffer,
            false,
            will_length);
        if (ok) {
            Serial.println("[wildlife][I] MQTT connected");
        } else {
            Serial.printf("[wildlife][W] MQTT connect failed rc=%d, retrying in 3s\n", client_.state());
            delay(3000);
        }
    }
}

void MqttPublisher::loop() {
    client_.loop();
}

bool MqttPublisher::publish_status(
    const char* state,
    const char* ip,
    std::uint32_t uptime_ms,
    bool retained) {
    StaticJsonDocument<192> doc;
    doc["state"] = state;
    doc["ip"] = ip;
    doc["node_id"] = credentials_.node_id;
    doc["uptime_ms"] = uptime_ms;

    char buffer[192];
    const std::size_t bytes = serializeJson(doc, buffer, sizeof(buffer));
    return client_.publish(
        topics_.status.data(),
        reinterpret_cast<const std::uint8_t*>(buffer),
        bytes,
        retained);
}

bool MqttPublisher::publish_detection(const char* payload, std::size_t payload_len) {
    return client_.publish(
        topics_.detections.data(),
        reinterpret_cast<const std::uint8_t*>(payload),
        payload_len,
        false);
}

bool MqttPublisher::publish_thumb(const char* frame_id, const std::uint8_t* jpeg, std::size_t jpeg_len) {
    if (jpeg == nullptr || jpeg_len == 0 || jpeg_len > kMaxThumbBytes) {
        return false;
    }

    const std::size_t encoded_length = encode_base64_length(jpeg_len);
    static std::uint8_t encoded_buffer[22 * 1024];
    if (encoded_length + 1 > sizeof(encoded_buffer)) {
        Serial.printf("[wildlife][W] thumb too large for buffer (%u bytes)\n", static_cast<unsigned>(encoded_length));
        return false;
    }

    const std::size_t actual_length = encode_base64(jpeg, jpeg_len, encoded_buffer);
    encoded_buffer[actual_length] = 0;

    char topic[96];
    std::snprintf(topic, sizeof(topic), "%s/%s", topics_.thumbs_prefix.data(), frame_id);
    return client_.publish(topic, encoded_buffer, actual_length, true);
}

}  // namespace wildlife