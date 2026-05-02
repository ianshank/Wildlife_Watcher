#include "wildlife/net_mqtt.h"

#include <ArduinoJson.h>
#include <base64.hpp>

namespace wildlife {

namespace {

std::size_t max_thumb_payload_bytes() {
    return encode_base64_length(kMaxThumbBytes);
}

}  // namespace

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
            false);
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

bool MqttPublisher::publish_thumb(const char* frame_id, const char* encoded_jpeg, std::size_t encoded_len) {
    if (encoded_jpeg == nullptr || encoded_len == 0) {
        return false;
    }

    const std::size_t max_payload = max_thumb_payload_bytes();
    if (encoded_len > max_payload) {
        Serial.printf(
            "[wildlife][W] thumb too large for MQTT (%u b64 bytes > %u)\n",
            static_cast<unsigned>(encoded_len),
            static_cast<unsigned>(max_payload));
        return false;
    }

    char topic[96];
    std::snprintf(topic, sizeof(topic), "%s/%s", topics_.thumbs_prefix.data(), frame_id);
    return client_.publish(
        topic,
        reinterpret_cast<const std::uint8_t*>(encoded_jpeg),
        encoded_len,
        true);
}

}  // namespace wildlife