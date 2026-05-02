#pragma once

#include <cstddef>
#include <cstdint>

#if __has_include("secrets.h")
#include "secrets.h"
#elif __has_include("secrets.h.example")
#include "secrets.h.example"
#else
#error "Add secrets.h or secrets.h.example before building the Phase 2 firmware."
#endif

#ifndef WILDLIFE_CLASS_DEBOUNCE_MS
#define WILDLIFE_CLASS_DEBOUNCE_MS 2000UL
#endif

#ifndef WILDLIFE_HEARTBEAT_MS
#define WILDLIFE_HEARTBEAT_MS 30000UL
#endif

#ifndef WILDLIFE_THUMB_PUBLISH_THRESHOLD
#define WILDLIFE_THUMB_PUBLISH_THRESHOLD 50U
#endif

#ifndef WILDLIFE_MAX_THUMB_BYTES
#define WILDLIFE_MAX_THUMB_BYTES 16384U
#endif

#ifndef WILDLIFE_POWER_MODE
#define WILDLIFE_POWER_MODE 0
#endif

#ifndef WILDLIFE_PIR_PIN
#define WILDLIFE_PIR_PIN 2
#endif

#ifndef WILDLIFE_DEEP_SLEEP_S
#define WILDLIFE_DEEP_SLEEP_S 120UL
#endif

#ifndef WILDLIFE_DETECTION_TOPIC_ROOT
#define WILDLIFE_DETECTION_TOPIC_ROOT "wildlife/detections"
#endif

#ifndef WILDLIFE_STATUS_TOPIC_ROOT
#define WILDLIFE_STATUS_TOPIC_ROOT "wildlife/status"
#endif

#ifndef WILDLIFE_THUMBS_TOPIC_ROOT
#define WILDLIFE_THUMBS_TOPIC_ROOT "wildlife/thumbs"
#endif

#ifndef WILDLIFE_MODEL_ID
#define WILDLIFE_MODEL_ID "grove_vision_ai_v2"
#endif

#ifndef WILDLIFE_SERIAL_BAUD
#define WILDLIFE_SERIAL_BAUD 115200UL
#endif

#ifndef WILDLIFE_BOOT_DELAY_MS
#define WILDLIFE_BOOT_DELAY_MS 500UL
#endif

#ifndef WILDLIFE_POLL_IDLE_DELAY_MS
#define WILDLIFE_POLL_IDLE_DELAY_MS 20UL
#endif

#ifndef WILDLIFE_DEEP_SLEEP_SETTLE_MS
#define WILDLIFE_DEEP_SLEEP_SETTLE_MS 20UL
#endif

#ifndef WILDLIFE_DETECTION_PAYLOAD_BYTES
#define WILDLIFE_DETECTION_PAYLOAD_BYTES 2048U
#endif

#ifndef WILDLIFE_FRAME_ID_BUFFER_BYTES
#define WILDLIFE_FRAME_ID_BUFFER_BYTES 24U
#endif

#ifndef WILDLIFE_MQTT_BUFFER_BYTES
#define WILDLIFE_MQTT_BUFFER_BYTES (24U * 1024U)
#endif

#ifndef WILDLIFE_MQTT_KEEPALIVE_S
#define WILDLIFE_MQTT_KEEPALIVE_S 45U
#endif

#ifndef WILDLIFE_MQTT_SOCKET_TIMEOUT_S
#define WILDLIFE_MQTT_SOCKET_TIMEOUT_S 15U
#endif

#ifndef WILDLIFE_MQTT_RECONNECT_BACKOFF_MS
#define WILDLIFE_MQTT_RECONNECT_BACKOFF_MS 3000UL
#endif

#ifndef WILDLIFE_MQTT_STATUS_BUFFER_BYTES
#define WILDLIFE_MQTT_STATUS_BUFFER_BYTES 192U
#endif

#ifndef WILDLIFE_MQTT_WILL_BUFFER_BYTES
#define WILDLIFE_MQTT_WILL_BUFFER_BYTES 96U
#endif

#ifndef WILDLIFE_MQTT_TOPIC_BUFFER_BYTES
#define WILDLIFE_MQTT_TOPIC_BUFFER_BYTES 96U
#endif

#ifndef WILDLIFE_MQTT_STATUS_QOS
#define WILDLIFE_MQTT_STATUS_QOS 1U
#endif

#ifndef WILDLIFE_WIFI_CONNECT_TIMEOUT_MS
#define WILDLIFE_WIFI_CONNECT_TIMEOUT_MS 30000UL
#endif

#ifndef WILDLIFE_WIFI_POLL_INTERVAL_MS
#define WILDLIFE_WIFI_POLL_INTERVAL_MS 250UL
#endif

// Class name table — override in secrets.h to match the deployed model.
// The fallback for out-of-range IDs is "class_<id>".
#ifndef WILDLIFE_CLASS_NAMES
#define WILDLIFE_CLASS_NAMES \
    "bird", "cat", "dog", "squirrel", "fox", "deer", "rabbit", "hedgehog"
#endif

namespace wildlife {

struct Credentials {
    const char* wifi_ssid;
    const char* wifi_password;
    const char* mqtt_broker;
    std::uint16_t mqtt_port;
    const char* mqtt_user;
    const char* mqtt_password;
    const char* node_id;
};

inline constexpr Credentials kCredentials{
    WIFI_SSID,
    WIFI_PASSWORD,
    MQTT_BROKER,
    static_cast<std::uint16_t>(MQTT_PORT),
    MQTT_USER,
    MQTT_PASSWORD,
    NODE_ID,
};

inline constexpr std::uint32_t kClassDebounceMs =
    static_cast<std::uint32_t>(WILDLIFE_CLASS_DEBOUNCE_MS);
inline constexpr std::uint32_t kHeartbeatMs =
    static_cast<std::uint32_t>(WILDLIFE_HEARTBEAT_MS);
inline constexpr std::uint16_t kThumbPublishThreshold =
    static_cast<std::uint16_t>(WILDLIFE_THUMB_PUBLISH_THRESHOLD);
inline constexpr std::size_t kMaxThumbBytes =
    static_cast<std::size_t>(WILDLIFE_MAX_THUMB_BYTES);
inline constexpr bool kPirWakeEnabled = WILDLIFE_POWER_MODE == 1;
inline constexpr std::uint8_t kPirPin = static_cast<std::uint8_t>(WILDLIFE_PIR_PIN);
inline constexpr std::uint32_t kDeepSleepSeconds =
    static_cast<std::uint32_t>(WILDLIFE_DEEP_SLEEP_S);
inline constexpr const char* kDetectionTopicRoot = WILDLIFE_DETECTION_TOPIC_ROOT;
inline constexpr const char* kStatusTopicRoot = WILDLIFE_STATUS_TOPIC_ROOT;
inline constexpr const char* kThumbsTopicRoot = WILDLIFE_THUMBS_TOPIC_ROOT;
inline constexpr const char* kModelId = WILDLIFE_MODEL_ID;
inline constexpr std::uint32_t kSerialBaud =
    static_cast<std::uint32_t>(WILDLIFE_SERIAL_BAUD);
inline constexpr std::uint32_t kBootDelayMs =
    static_cast<std::uint32_t>(WILDLIFE_BOOT_DELAY_MS);
inline constexpr std::uint32_t kPollIdleDelayMs =
    static_cast<std::uint32_t>(WILDLIFE_POLL_IDLE_DELAY_MS);
inline constexpr std::uint32_t kDeepSleepSettleMs =
    static_cast<std::uint32_t>(WILDLIFE_DEEP_SLEEP_SETTLE_MS);
inline constexpr std::size_t kDetectionPayloadBytes =
    static_cast<std::size_t>(WILDLIFE_DETECTION_PAYLOAD_BYTES);
inline constexpr std::size_t kFrameIdBufferBytes =
    static_cast<std::size_t>(WILDLIFE_FRAME_ID_BUFFER_BYTES);
inline constexpr std::size_t kMqttBufferBytes =
    static_cast<std::size_t>(WILDLIFE_MQTT_BUFFER_BYTES);
static_assert(kMqttBufferBytes <= 65535U,
              "WILDLIFE_MQTT_BUFFER_BYTES must fit in uint16_t (PubSubClient::setBufferSize)");
inline constexpr std::uint16_t kMqttKeepAliveSeconds =
    static_cast<std::uint16_t>(WILDLIFE_MQTT_KEEPALIVE_S);
inline constexpr std::uint16_t kMqttSocketTimeoutSeconds =
    static_cast<std::uint16_t>(WILDLIFE_MQTT_SOCKET_TIMEOUT_S);
inline constexpr std::uint32_t kMqttReconnectBackoffMs =
    static_cast<std::uint32_t>(WILDLIFE_MQTT_RECONNECT_BACKOFF_MS);
inline constexpr std::size_t kMqttStatusBufferBytes =
    static_cast<std::size_t>(WILDLIFE_MQTT_STATUS_BUFFER_BYTES);
inline constexpr std::size_t kMqttWillBufferBytes =
    static_cast<std::size_t>(WILDLIFE_MQTT_WILL_BUFFER_BYTES);
inline constexpr std::size_t kMqttTopicBufferBytes =
    static_cast<std::size_t>(WILDLIFE_MQTT_TOPIC_BUFFER_BYTES);
inline constexpr std::uint8_t kMqttStatusQos =
    static_cast<std::uint8_t>(WILDLIFE_MQTT_STATUS_QOS);
static_assert(kMqttStatusQos <= 2U,
              "WILDLIFE_MQTT_STATUS_QOS must be 0, 1, or 2 (MQTT spec)");
inline constexpr std::uint32_t kWifiConnectTimeoutMs =
    static_cast<std::uint32_t>(WILDLIFE_WIFI_CONNECT_TIMEOUT_MS);
inline constexpr std::uint32_t kWifiPollIntervalMs =
    static_cast<std::uint32_t>(WILDLIFE_WIFI_POLL_INTERVAL_MS);

}  // namespace wildlife