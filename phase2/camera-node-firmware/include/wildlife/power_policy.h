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

// ---------------------------------------------------------------------------
// Wake-source classification
// ---------------------------------------------------------------------------

// Logical wake source from an ESP32 deep-sleep cycle.
enum class WakeSource : std::uint8_t {
    kColdBoot,   // Power-on reset or watchdog; not woken from deep sleep.
    kPirExt0,    // External single-pin wakeup (PIR sensor on EXT0).
    kTimer,      // Timer-based periodic wakeup.
    kUnknown,    // Any other esp_sleep_source_t value.
};

// ESP32 esp_sleep_source_t numeric values (mirrors <esp_sleep.h>).
// Defined here so this pure function can be tested in the native host
// environment without pulling in Arduino/ESP-IDF headers.
inline constexpr std::uint32_t kEspWakeCauseUndefined = 0U;  // not a deep-sleep wakeup
inline constexpr std::uint32_t kEspWakeCauseExt0      = 2U;  // single-pin external
inline constexpr std::uint32_t kEspWakeCauseTimer     = 4U;  // RTC timer

// Pure mapping from esp_sleep_get_wakeup_cause() to WakeSource.
// No Arduino dependency; safe for native unit tests.
constexpr WakeSource classify_wake_source(std::uint32_t esp_cause) noexcept {
    if (esp_cause == kEspWakeCauseUndefined) {
        return WakeSource::kColdBoot;
    }
    if (esp_cause == kEspWakeCauseExt0) {
        return WakeSource::kPirExt0;
    }
    if (esp_cause == kEspWakeCauseTimer) {
        return WakeSource::kTimer;
    }
    return WakeSource::kUnknown;
}

}  // namespace wildlife
