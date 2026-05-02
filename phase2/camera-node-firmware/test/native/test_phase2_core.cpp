#include <unity.h>

#include "wildlife/config.h"
#include "wildlife/debounce.h"
#include "wildlife/fps_meter.h"
#include "wildlife/topic_names.h"

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

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    UNITY_BEGIN();
    RUN_TEST(test_topic_names_are_formatted);
    RUN_TEST(test_debouncer_blocks_rapid_repeats);
    RUN_TEST(test_fps_meter_reports_nonzero_after_window);
    RUN_TEST(test_thumb_budget_constants_are_exposed);
    return UNITY_END();
}