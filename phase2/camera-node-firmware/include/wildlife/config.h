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

}  // namespace wildlife