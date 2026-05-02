#include <unity.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <string>

#include "wildlife/class_names.h"
#include "wildlife/config.h"
#include "wildlife/debounce.h"
#include "wildlife/fps_meter.h"
#include "wildlife/power_mgmt.h"
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

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    UNITY_BEGIN();
    RUN_TEST(test_topic_names_are_formatted);
    RUN_TEST(test_debouncer_blocks_rapid_repeats);
    RUN_TEST(test_fps_meter_reports_nonzero_after_window);
    RUN_TEST(test_thumb_budget_constants_are_exposed);
    RUN_TEST(test_class_name_returns_semantic_label_for_known_id);
    RUN_TEST(test_class_name_returns_fallback_for_out_of_range_id);
    RUN_TEST(test_power_mgr_pir_disabled_when_mode_zero);
    RUN_TEST(test_power_mgr_maybe_sleep_is_noop_in_native);
    return UNITY_END();
}