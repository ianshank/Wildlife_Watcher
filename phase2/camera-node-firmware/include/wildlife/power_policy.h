#pragma once

#include <cstdint>

namespace wildlife {

// Inputs that drive the deep-sleep decision. Grouped so future signals
// (battery voltage, last-wake-cause, etc.) can be added without breaking
// callers.
struct PowerInputs {
    bool pir_wake_enabled;
    bool saw_activity;
    bool pir_pin_high;
};

enum class SleepDecision : std::uint8_t {
    kStayAwake,
    kEnterDeepSleep,
};

// Pure decision policy: no Arduino dependency, safe for native unit tests.
// The node enters deep sleep only when PIR wake is enabled, no activity was
// seen this cycle, and the PIR pin is currently low (motion-quiet).
constexpr SleepDecision evaluate_sleep_decision(const PowerInputs& inputs) noexcept {
    if (!inputs.pir_wake_enabled) {
        return SleepDecision::kStayAwake;
    }
    if (inputs.saw_activity) {
        return SleepDecision::kStayAwake;
    }
    if (inputs.pir_pin_high) {
        return SleepDecision::kStayAwake;
    }
    return SleepDecision::kEnterDeepSleep;
}

}  // namespace wildlife
