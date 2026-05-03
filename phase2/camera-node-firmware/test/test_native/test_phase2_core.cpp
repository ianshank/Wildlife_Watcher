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
#include "wildlife/pir_event.h"
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

void test_thumb_topic_round_trip_full_path() {
    // Mirrors the Python firmware-format round-trip in
    // pi-display-node/tests/test_integration_firmware_format.py which builds
    // the topic as f"{thumbs_root}/{node_id}/{frame_id}". Pinning the literal
    // byte sequence here means a change to either side surfaces as a paired
    // failure on both the Python and Unity surfaces.
    constexpr const char kCompositeKey[] = "phase2-node/f_000123";
    constexpr const char kExpected[] = "wildlife/thumbs/phase2-node/f_000123";
    char topic[96]{};
    const auto written = wildlife::format_thumb_topic(
        topic,
        sizeof(topic),
        wildlife::kThumbsTopicRoot,
        kCompositeKey);
    TEST_ASSERT_EQUAL_STRING(kExpected, topic);
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(sizeof(kExpected) - 1U),
                             static_cast<unsigned int>(written));
}

void test_thumb_payload_budget_matches_python_round_trip() {
    // Pins the base64 budget literal that the Python parity test computes from
    // WILDLIFE_MAX_THUMB_BYTES (16384 -> ((16384+2)/3)*4 = 21848). Any drift in
    // either kMaxThumbBytes or the base64 formula must fail here.
    constexpr std::size_t kExpectedBudget = 21848U;
    static_assert(wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes) == kExpectedBudget,
                  "Thumb base64 budget must remain pinned to the Python parity literal");
    TEST_ASSERT_EQUAL_UINT32(static_cast<unsigned int>(kExpectedBudget),
                             static_cast<unsigned int>(
                                 wildlife::max_thumb_payload_bytes(wildlife::kMaxThumbBytes)));
}

void test_thumbs_topic_root_matches_kiosk_contract() {
    // Pins the topic root the kiosk subscribes to (wildlife/thumbs/+/+ in
    // pi-display-node/kiosk/config.yaml) and the Python parity test parses out
    // of WILDLIFE_THUMBS_TOPIC_ROOT.
    TEST_ASSERT_EQUAL_STRING("wildlife/thumbs", wildlife::kThumbsTopicRoot);
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

// ---------------------------------------------------------------------------
// Wake-source classification tests
// ---------------------------------------------------------------------------

void test_classify_wake_source_cold_boot() {
    static_assert(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseUndefined) ==
            wildlife::WakeSource::kColdBoot,
        "Undefined/reset cause must classify as kColdBoot");
    TEST_ASSERT_TRUE(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseUndefined) ==
        wildlife::WakeSource::kColdBoot);
}

void test_classify_wake_source_ext0_pir() {
    static_assert(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseExt0) ==
            wildlife::WakeSource::kPirExt0,
        "EXT0 cause must classify as kPirExt0");
    TEST_ASSERT_TRUE(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseExt0) ==
        wildlife::WakeSource::kPirExt0);
}

void test_classify_wake_source_timer() {
    static_assert(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseTimer) ==
            wildlife::WakeSource::kTimer,
        "Timer cause must classify as kTimer");
    TEST_ASSERT_TRUE(
        wildlife::classify_wake_source(wildlife::kEspWakeCauseTimer) ==
        wildlife::WakeSource::kTimer);
}

void test_classify_wake_source_unknown_fallback() {
    // Cause 99 is not assigned to any known wakeup type; must fall back to kUnknown.
    TEST_ASSERT_TRUE(
        wildlife::classify_wake_source(99U) == wildlife::WakeSource::kUnknown);
    // Cause 1 (ESP_SLEEP_WAKEUP_ALL) is likewise unrecognised.
    TEST_ASSERT_TRUE(
        wildlife::classify_wake_source(1U) == wildlife::WakeSource::kUnknown);
}

void test_power_mgr_last_wake_source_is_cold_boot_in_native() {
    // In the native (non-ESP32) environment begin() always sets kColdBoot.
    wildlife::PowerManager pm;
    pm.begin();
    TEST_ASSERT_TRUE(pm.last_wake_source() == wildlife::WakeSource::kColdBoot);
}

// ---------------------------------------------------------------------------
// PIR edge debounce tests
// ---------------------------------------------------------------------------

void test_pir_edge_first_call_accepted() {
    // Sentinel last_edge == max value means "never fired"; elapsed wraps to
    // a large number >= any real debounce period.
    constexpr std::uint32_t kNever = 0xFFFFFFFFU;
    constexpr std::uint32_t kNow   = 1000000U;  // 1 s after boot
    constexpr std::uint32_t kDebounceUs = static_cast<std::uint32_t>(WILDLIFE_PIR_DEBOUNCE_MS) * 1000U;
    TEST_ASSERT_TRUE(wildlife::should_accept_pir_edge(kNever, kNow, kDebounceUs));
}

void test_pir_edge_within_debounce_rejected() {
    constexpr std::uint32_t kLastUs = 1000000U;
    constexpr std::uint32_t kDebounceUs = static_cast<std::uint32_t>(WILDLIFE_PIR_DEBOUNCE_MS) * 1000U;
    // Edge arrives 1 µs before the debounce window expires.
    const std::uint32_t kTooSoon = kLastUs + kDebounceUs - 1U;
    TEST_ASSERT_FALSE(wildlife::should_accept_pir_edge(kLastUs, kTooSoon, kDebounceUs));
}

void test_pir_edge_at_exact_debounce_boundary_accepted() {
    constexpr std::uint32_t kLastUs = 1000000U;
    constexpr std::uint32_t kDebounceUs = static_cast<std::uint32_t>(WILDLIFE_PIR_DEBOUNCE_MS) * 1000U;
    // elapsed == debounce_us: boundary must be accepted (>=).
    const std::uint32_t kExact = kLastUs + kDebounceUs;
    TEST_ASSERT_TRUE(wildlife::should_accept_pir_edge(kLastUs, kExact, kDebounceUs));
}

void test_pir_edge_wrap_around_safe() {
    // last_edge_us near uint32_t max; now_us wraps past zero.
    constexpr std::uint32_t kDebounceUs = 250000U;  // 250 ms
    constexpr std::uint32_t kLastUs = 0xFFFFFF00U;  // close to wrap
    // Wrap: 0xFFFFFF00 + 0x00060000 = 0x000600FF (wraps past max)
    constexpr std::uint32_t kNow = kLastUs + 0x00060000U;  // >> debounce
    static_assert(kNow < kLastUs, "kNow must have wrapped for this test to be meaningful");
    TEST_ASSERT_TRUE(wildlife::should_accept_pir_edge(kLastUs, kNow, kDebounceUs));
}

// ---------------------------------------------------------------------------
// PIR tunable constants
// ---------------------------------------------------------------------------

void test_pir_tunable_constants_are_nonzero() {
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kPirDebounceMs));
    TEST_ASSERT_GREATER_THAN_UINT32(0U, static_cast<unsigned int>(wildlife::kWakeBootGraceMs));
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
    RUN_TEST(test_thumb_topic_round_trip_full_path);
    RUN_TEST(test_thumb_payload_budget_matches_python_round_trip);
    RUN_TEST(test_thumbs_topic_root_matches_kiosk_contract);
    RUN_TEST(test_runtime_config_constants_are_consistent);
    // Wake-source classification
    RUN_TEST(test_classify_wake_source_cold_boot);
    RUN_TEST(test_classify_wake_source_ext0_pir);
    RUN_TEST(test_classify_wake_source_timer);
    RUN_TEST(test_classify_wake_source_unknown_fallback);
    RUN_TEST(test_power_mgr_last_wake_source_is_cold_boot_in_native);
    // PIR edge debounce
    RUN_TEST(test_pir_edge_first_call_accepted);
    RUN_TEST(test_pir_edge_within_debounce_rejected);
    RUN_TEST(test_pir_edge_at_exact_debounce_boundary_accepted);
    RUN_TEST(test_pir_edge_wrap_around_safe);
    // PIR tunable constants
    RUN_TEST(test_pir_tunable_constants_are_nonzero);
    return UNITY_END();
}