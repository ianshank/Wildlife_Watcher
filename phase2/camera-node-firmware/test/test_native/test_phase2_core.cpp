#include <unity.h>

#include "wildlife/class_names.h"
#include "wildlife/config.h"
#include "wildlife/debounce.h"
#include "wildlife/fps_meter.h"
#include "wildlife/power_mgmt.h"
#include "wildlife/topic_names.h"

void setUp() {}

void tearDown() {}

void test_topic_names_are_formatted() {
    const auto topics = wildlife::build_topic_names("feeder-01");
    TEST_ASSERT_EQUAL_STRING("wildlife/detections/feeder-01", topics.detections.data());
    TEST_ASSERT_EQUAL_STRING("wildlife/status/feeder-01", topics.status.data());
    TEST_ASSERT_EQUAL_STRING("wildlife/thumbs/feeder-01", topics.thumbs_prefix.data());
}

void test_debouncer_blocks_rapid_repeats() {
    wildlife::ClassDebouncer debouncer;
    TEST_ASSERT_TRUE(debouncer.should_publish(14, 100U, 2000U));
    TEST_ASSERT_FALSE(debouncer.should_publish(14, 500U, 2000U));
    TEST_ASSERT_TRUE(debouncer.should_publish(14, 2505U, 2000U));
}

void test_fps_meter_reports_nonzero_after_window() {
    wildlife::FpsMeter meter;
    for (unsigned int tick = 0; tick < 12; ++tick) {
        meter.tick(tick * 100U);
    }
    TEST_ASSERT_GREATER_THAN_FLOAT(0.0F, meter.current());
}

void test_thumb_budget_constants_are_exposed() {
    TEST_ASSERT_EQUAL_UINT32(16384U, static_cast<unsigned int>(wildlife::kMaxThumbBytes));
    TEST_ASSERT_EQUAL_UINT32(50U, wildlife::kThumbPublishThreshold);
}

void test_class_name_returns_semantic_label_for_known_id() {
    // Class ID 0 maps to the first entry in the WILDLIFE_CLASS_NAMES table.
    char buf[16];
    const char* name = wildlife::class_name_for_id(0, buf, sizeof(buf));
    TEST_ASSERT_EQUAL_STRING(wildlife::detail::kClassNameTable[0], name);
}

void test_class_name_returns_fallback_for_out_of_range_id() {
    // ID 255 always exceeds any realistic class table.
    char buf[16];
    const char* name = wildlife::class_name_for_id(255, buf, sizeof(buf));
    TEST_ASSERT_EQUAL_STRING("class_255", name);
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