#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "wildlife/config.h"
#include "wildlife/fps_meter.h"
#include "wildlife/net_mqtt.h"
#include "wildlife/net_wifi.h"
#include "wildlife/power_mgmt.h"
#include "wildlife/sscma_decode.h"
#include "wildlife/sscma_io.h"
#include "wildlife/topic_names.h"

namespace {

WiFiClient wifi_client;
PubSubClient mqtt_client(wifi_client);
wildlife::WifiLink wifi_link(wildlife::kCredentials);
wildlife::MqttPublisher mqtt_publisher(
    mqtt_client,
    wildlife::kCredentials,
    wildlife::build_topic_names(wildlife::kCredentials.node_id));
wildlife::SscmaSensor sensor;
wildlife::PowerManager power_manager;
wildlife::FpsMeter fps_meter;
std::uint32_t last_heartbeat_ms = 0;
std::uint32_t frame_counter = 0;

void publish_frame(const wildlife::DetectionFrame& frame, std::uint32_t now_ms, float fps) {
    StaticJsonDocument<2048> doc;
    char timestamp[32];
    std::snprintf(timestamp, sizeof(timestamp), "%lu", static_cast<unsigned long>(now_ms));
    doc["ts"] = timestamp;
    doc["node_id"] = wildlife::kCredentials.node_id;

    const std::uint32_t current_frame = ++frame_counter;
    char frame_id[24];
    std::snprintf(frame_id, sizeof(frame_id), "f_%06lu", static_cast<unsigned long>(current_frame));
    doc["frame_id"] = frame_id;
    doc["model"] = "grove_vision_ai_v2";
    doc["fps"] = fps;

    JsonArray detections = doc.createNestedArray("detections");
    bool published_any = false;
    std::uint16_t max_confidence = 0;

    for (const auto& box : frame.boxes) {
        const auto class_id = wildlife::class_id_from_target(box.target);
        if (!sensor.should_publish(class_id, now_ms, wildlife::kClassDebounceMs)) {
            continue;
        }

        published_any = true;
        JsonObject detection = detections.createNestedObject();
        detection["class_id"] = box.target;
        detection["class_name"] = sensor.class_name(class_id);
        detection["confidence"] = wildlife::score_to_confidence(box.score);
        JsonArray bbox = detection.createNestedArray("bbox");
        bbox.add(box.x);
        bbox.add(box.y);
        bbox.add(box.w);
        bbox.add(box.h);

        max_confidence = wildlife::track_max_score(max_confidence, box.score);
    }

    if (!published_any) {
        power_manager.maybe_sleep(false);
        return;
    }

    char payload[2048];
    const std::size_t payload_len = serializeJson(doc, payload, sizeof(payload));
    mqtt_publisher.publish_detection(payload, payload_len);
    if (wildlife::should_capture_thumb(max_confidence, wildlife::kThumbPublishThreshold)) {
        String encoded_thumb;
        if (sensor.capture_thumb(&encoded_thumb)) {
            mqtt_publisher.publish_thumb(frame_id, encoded_thumb.c_str(), encoded_thumb.length());
        }
    }
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println();
    Serial.printf("[wildlife][I] booting node %s\n", wildlife::kCredentials.node_id);

    sensor.begin();
    wifi_link.begin();
    mqtt_publisher.begin();
    mqtt_publisher.ensure_connected();
    power_manager.begin();

    last_heartbeat_ms = millis();
    const String ip = wifi_link.local_ip();
    mqtt_publisher.publish_status("online", ip.c_str(), last_heartbeat_ms, true);
    Serial.println("[wildlife][I] ready");
}

void loop() {
    wifi_link.ensure_connected();
    mqtt_publisher.ensure_connected();
    mqtt_publisher.loop();

    const std::uint32_t now_ms = millis();
    if (now_ms - last_heartbeat_ms >= wildlife::kHeartbeatMs) {
        last_heartbeat_ms = now_ms;
        const String ip = wifi_link.local_ip();
        mqtt_publisher.publish_status("online", ip.c_str(), now_ms, true);
    }

    wildlife::DetectionFrame frame;
    if (!sensor.poll(&frame)) {
        delay(20);
        power_manager.maybe_sleep(false);
        return;
    }

    const float fps = fps_meter.tick(now_ms);
    if (frame.boxes.empty()) {
        power_manager.maybe_sleep(false);
        return;
    }

    publish_frame(frame, now_ms, fps);
}