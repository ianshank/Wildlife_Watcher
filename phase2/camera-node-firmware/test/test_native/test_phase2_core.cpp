#include <unity.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <string>

#include "wildlife/class_names.h"
#include "wildlife/config.h"
#include "wildlife/debounce.h"
#include "wildlife/fps_meter.h"
#include "wildlife/net_mqtt_format.h"
#include "wildlife/power_mgmt.h"
#include "wildlife/power_policy.h"
#include "wildlife/sscma_decode.h"
#include "wildlife/topic_names.h"

void setUp() {}

void tearDown() {}

void test_topic_names_are_formatted() {
    constexpr const char kNodeId[] = "feeder-01";
    const auto topics = wildlife::build_topic_names(kNodeId);
    const auto expected_detections = std::string(wildlife::kDetectionTopicRoot) + "/" + kNodeId;
    const auto expected_status = std::string(wildlife::kStatusTopicRoot) + "/" + kNodeId;
    const auto expected_thumbs = std::string(wildlife::kThumbsTopicRoot) + "/" + kNodeId;
    TEST_ASSERT_EQUAL_STRING(expected_detections.c_str(), topics.detections.data());
    TEST_ASSERT_EQUAL_STRING(expected_status.c_str(), topics.status.data());
    TEST_ASSERT_EQUAL_STRING(expected_thumbs.c_str(), topics.thumbs_prefix.data());
}

void test_thumb_payload_budget_matches_base64_limit() {
    constexpr std::size_t kExpectedLimit = ((wildlife::kMaxThumbBytes + 2U) / 3U) * 4U;
    static_assert(wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes) == kExpectedLimit,
                  "Configured thumb budget should map to the expected base64 payload limit");
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(kExpectedLimit),
                             static_cast<unsigned int>(wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes)));
}

void test_thumb_payload_at_budget_is_accepted() {
    constexpr std::size_t kLimit = wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes);
    TEST_ASSERT_TRUE(wildlife::thumb_payload_fits(kLimit, wildlife::kMaxThumbBytes));
}

void test_thumb_payload_above_budget_is_rejected() {
    constexpr std::size_t kLimit = wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes);
    TEST_ASSERT_FALSE(wildlife::thumb_payload_fits(kLimit + 1U, wildlife::kMaxThumbBytes));
}

void test_thumb_topic_is_formatted_with_frame_id() {
    constexpr const char kFrameId[] = "f_000123";
    char topic[96]{};
    const auto written = wildlife::format_thumb_topic(
        topic,
        sizeof(topic),
        wildlife::kThumbsTopicRoot,
        kFrameId);
    const auto expected = std::string(wildlife::kThumbsTopicRoot) + "/" + kFrameId;
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(expected.size()), static_cast<unsigned int>(written));
    TEST_ASSERT_EQUAL_STRING(expected.c_str(), topic);
}

void test_debouncer_blocks_rapid_repeats() {
    wildlife::ClassDebouncer debouncer;
    constexpr std::uint8_t kClassId = 14U;
    constexpr std::uint32_t kFirstTickMs = 100U;
    constexpr std::uint32_t kSecondTickMs = kFirstTickMs + 1U;
    constexpr std::uint32_t kThirdTickMs = kFirstTickMs + wildlife::kClassDebounceMs + 1U;
    TEST_ASSERT_TRUE(debouncer.should_publish(kClassId, kFirstTickMs, wildlife::kClassDebounceMs));
    TEST_ASSERT_FALSE(debouncer.should_publish(kClassId, kSecondTickMs, wildlife::kClassDebounceMs));
    TEST_ASSERT_TRUE(debouncer.should_publish(kClassId, kThirdTickMs, wildlife::kClassDebounceMs));
}

void test_fps_meter_reports_nonzero_after_window() {
    wildlife::FpsMeter meter;
    for (unsigned int tick = 0; tick < 12; ++tick) {
        meter.tick(tick * 100U);
    }
    TEST_ASSERT_GREATER_THAN_FLOAT(0.0F, meter.current());
}

void test_thumb_budget_constants_are_exposed() {
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(WILDLIFE_MAX_THUMB_BYTES),
                             static_cast<unsigned int>(wildlife::kMaxThumbBytes));
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(WILDLIFE_THUMB_PUBLISH_THRESHOLD),
                             static_cast<unsigned int>(wildlife::kThumbPublishThreshold));
}

void test_class_name_returns_semantic_label_for_known_id() {
    constexpr std::uint8_t kFirstClassId = 0U;
    std::array<char, wildlife::kClassNameFallbackBufferSize> buf{};
    const char* name = wildlife::class_name_for_id(kFirstClassId, buf.data(), buf.size());
    TEST_ASSERT_EQUAL_STRING(wildlife::configured_class_name(kFirstClassId), name);
}

void test_class_name_returns_fallback_for_out_of_range_id() {
    static_assert(wildlife::kClassNameCount < 256, "Class count exceeds uint8_t range for out-of-range testing");
    const auto out_of_range_id = static_cast<std::uint8_t>(wildlife::kClassNameCount);
    std::array<char, wildlife::kClassNameFallbackBufferSize> buf{};
    std::array<char, wildlife::kClassNameFallbackBufferSize> expected{};
    std::snprintf(expected.data(), expected.size(), "class_%u", static_cast<unsigned>(out_of_range_id));
    const char* name = wildlife::class_name_for_id(out_of_range_id, buf.data(), buf.size());
    TEST_ASSERT_NULL(wildlife::configured_class_name(out_of_range_id));
    TEST_ASSERT_EQUAL_STRING(expected.data(), name);
}

void test_power_mgr_pir_disabled_when_mode_zero() {
    // WILDLIFE_POWER_MODE defaults to 0 in the native env → PIR wake disabled.
    wildlife::PowerManager pm;
    TEST_ASSERT_FALSE(pm.pir_wake_enabled());
}

void test_power_mgr_maybe_sleep_is_noop_in_native() {
    // Calling maybe_sleep in the native (non-ESP32) environment must not crash
    // regardless of the saw_activity flag.
    wildlife::PowerManager pm;
    pm.maybe_sleep(false);
    pm.maybe_sleep(true);
    TEST_PASS();
}

void test_sleep_decision_pir_disabled_stays_awake() {
    constexpr wildlife::PowerInputs kInputs{
        /*pir_wake_enabled=*/false,
        /*saw_activity=*/false,
        /*pir_pin_high=*/false,
    };
    static_assert(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kStayAwake,
                  "PIR-disabled must always stay awake");
    TEST_ASSERT_TRUE(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kStayAwake);
}

void test_sleep_decision_activity_stays_awake() {
    constexpr wildlife::PowerInputs kInputs{
        /*pir_wake_enabled=*/true,
        /*saw_activity=*/true,
        /*pir_pin_high=*/false,
    };
    TEST_ASSERT_TRUE(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kStayAwake);
}

void test_sleep_decision_pir_pin_high_stays_awake() {
    constexpr wildlife::PowerInputs kInputs{
        /*pir_wake_enabled=*/true,
        /*saw_activity=*/false,
        /*pir_pin_high=*/true,
    };
    TEST_ASSERT_TRUE(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kStayAwake);
}

void test_sleep_decision_idle_with_pir_low_enters_deep_sleep() {
    constexpr wildlife::PowerInputs kInputs{
        /*pir_wake_enabled=*/true,
        /*saw_activity=*/false,
        /*pir_pin_high=*/false,
    };
    static_assert(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kEnterDeepSleep,
                  "Idle with PIR low must enter deep sleep");
    TEST_ASSERT_TRUE(wildlife::evaluate_sleep_decision(kInputs) == wildlife::SleepDecision::kEnterDeepSleep);
}

void test_class_id_from_target_extracts_low_byte() {
    static_assert(wildlife::class_id_from_target(0x0142U) == 0x42U,
                  "class_id should be the low byte of target");
    TEST_ASSERT_EQUAL_UINT8(0x42U, wildlife::class_id_from_target(0x0142U));
}

void test_class_id_from_target_handles_byte_boundaries() {
    TEST_ASSERT_EQUAL_UINT8(0x00U, wildlife::class_id_from_target(0x0000U));
    TEST_ASSERT_EQUAL_UINT8(0xFFU, wildlife::class_id_from_target(0x00FFU));
    TEST_ASSERT_EQUAL_UINT8(0xFFU, wildlife::class_id_from_target(0xFFFFU));
}

void test_score_to_confidence_maps_zero_and_full_range() {
    TEST_ASSERT_FLOAT_WITHIN(1e-6F, 0.0F, wildlife::score_to_confidence(0U));
    TEST_ASSERT_FLOAT_WITHIN(1e-6F, 1.0F, wildlife::score_to_confidence(100U));
    TEST_ASSERT_FLOAT_WITHIN(1e-6F, 0.5F, wildlife::score_to_confidence(50U));
}

void test_track_max_score_keeps_running_maximum() {
    std::uint16_t running = 0U;
    running = wildlife::track_max_score(running, 30U);
    running = wildlife::track_max_score(running, 80U);
    running = wildlife::track_max_score(running, 50U);
    TEST_ASSERT_EQUAL_UINT16(80U, running);
    // Tie keeps existing maximum.
    TEST_ASSERT_EQUAL_UINT16(80U, wildlife::track_max_score(80U, 80U));
}

void test_should_capture_thumb_respects_threshold() {
    constexpr std::uint16_t kThreshold = wildlife::kThumbPublishThreshold;
    TEST_ASSERT_TRUE(wildlife::should_capture_thumb(kThreshold, kThreshold));
    TEST_ASSERT_FALSE(wildlife::should_capture_thumb(
        static_cast<std::uint16_t>(kThreshold - 1U), kThreshold));
    TEST_ASSERT_TRUE(wildlife::should_capture_thumb(
        static_cast<std::uint16_t>(kThreshold + 25U), kThreshold));
}

void test_format_thumb_topic_rejects_null_arguments() {
    char buf[32]{};
    TEST_ASSERT_EQUAL_UINT32(0U, static_cast<unsigned int>(
        wildlife::format_thumb_topic(nullptr, sizeof(buf), "prefix", "frame")));
    TEST_ASSERT_EQUAL_UINT32(0U, static_cast<unsigned int>(
        wildlife::format_thumb_topic(buf, 0U, "prefix", "frame")));
    TEST_ASSERT_EQUAL_UINT32(0U, static_cast<unsigned int>(
        wildlife::format_thumb_topic(buf, sizeof(buf), nullptr, "frame")));
    TEST_ASSERT_EQUAL_UINT32(0U, static_cast<unsigned int>(
        wildlife::format_thumb_topic(buf, sizeof(buf), "prefix", nullptr)));
}

void test_format_thumb_topic_reports_truncation_via_written_length() {
    // snprintf returns the number of chars that *would* have been written;
    // a value >= buffer_size signals truncation. Our caller treats that as failure.
    char buf[8]{};
    const auto written = wildlife::format_thumb_topic(
        buf, sizeof(buf), "wildlife/thumbs", "f_000123");
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(static_cast<unsigned int>(sizeof(buf)),
                                        static_cast<unsigned int>(written));
}

void test_thumb_payload_zero_budget_rejects_any_payload() {
    static_assert(wildlife::max_thumb_payload_bytes(0U) == 0U,
                  "Zero raw budget must produce a zero base64 budget");
    TEST_ASSERT_TRUE(wildlife::thumb_payload_fits(0U, 0U));
    TEST_ASSERT_FALSE(wildlife::thumb_payload_fits(1U, 0U));
}

void test_base64_encoded_length_rounds_up_to_quartet() {
    static_assert(wildlife::base64_encoded_length(0U) == 0U, "empty -> 0");
    static_assert(wildlife::base64_encoded_length(1U) == 4U, "1 byte -> 4");
    static_assert(wildlife::base64_encoded_length(2U) == 4U, "2 bytes -> 4");
    static_assert(wildlife::base64_encoded_length(3U) == 4U, "3 bytes -> 4");
    static_assert(wildlife::base64_encoded_length(4U) == 8U, "4 bytes -> 8");
    TEST_ASSERT_EQUAL_UINT32(4U, static_cast<unsigned int>(wildlife::base64_encoded_length(3U)));
    TEST_ASSERT_EQUAL_UINT32(8U, static_cast<unsigned int>(wildlife::base64_encoded_length(4U)));
}

void test_runtime_config_constants_are_consistent() {
    // The native env should expose every new tunable so that platformio.ini
    // overrides flow through to firmware code paths and tests alike.
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kSerialBaud));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kBootDelayMs));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kDetectionPayloadBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kFrameIdBufferBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttBufferBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttKeepAliveSeconds));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttSocketTimeoutSeconds));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttReconnectBackoffMs));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttStatusBufferBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttWillBufferBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kMqttTopicBufferBytes));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kWifiConnectTimeoutMs));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kWifiPollIntervalMs));
    TEST_ASSERT_NOT_NULL(wildlife::kModelId);
    // The MQTT buffer must comfortably hold a base64-encoded thumb plus headers.
    TEST_ASSERT_GREATER_THAN_UINT32(
        static_cast<unsigned int>(wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes)),
        static_cast<unsigned int>(wildlife::kMqttBufferBytes));
}

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    UNITY_BEGIN();
    RUN_TEST(test_topic_names_are_formatted);
    RUN_TEST(test_thumb_payload_budget_matches_base64_limit);
    RUN_TEST(test_thumb_payload_at_budget_is_accepted);
    RUN_TEST(test_thumb_payload_above_budget_is_rejected);
    RUN_TEST(test_thumb_topic_is_formatted_with_frame_id);
    RUN_TEST(test_debouncer_blocks_rapid_repeats);
    RUN_TEST(test_fps_meter_reports_nonzero_after_window);
    RUN_TEST(test_thumb_budget_constants_are_exposed);
    RUN_TEST(test_class_name_returns_semantic_label_for_known_id);
    RUN_TEST(test_class_name_returns_fallback_for_out_of_range_id);
    RUN_TEST(test_power_mgr_pir_disabled_when_mode_zero);
    RUN_TEST(test_power_mgr_maybe_sleep_is_noop_in_native);
    RUN_TEST(test_sleep_decision_pir_disabled_stays_awake);
    RUN_TEST(test_sleep_decision_activity_stays_awake);
    RUN_TEST(test_sleep_decision_pir_pin_high_stays_awake);
    RUN_TEST(test_sleep_decision_idle_with_pir_low_enters_deep_sleep);
    RUN_TEST(test_class_id_from_target_extracts_low_byte);
    RUN_TEST(test_class_id_from_target_handles_byte_boundaries);
    RUN_TEST(test_score_to_confidence_maps_zero_and_full_range);
    RUN_TEST(test_track_max_score_keeps_running_maximum);
    RUN_TEST(test_should_capture_thumb_respects_threshold);
    RUN_TEST(test_format_thumb_topic_rejects_null_arguments);
    RUN_TEST(test_format_thumb_topic_reports_truncation_via_written_length);
    RUN_TEST(test_thumb_payload_zero_budget_rejects_any_payload);
    RUN_TEST(test_base64_encoded_length_rounds_up_to_quartet);
    RUN_TEST(test_runtime_config_constants_are_consistent);
    return UNITY_END();
}