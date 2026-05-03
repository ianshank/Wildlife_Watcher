#include "wildlife/power_mgmt.h"

#include <Arduino.h>

#include "wildlife/config.h"
#include "wildlife/power_policy.h"

#if defined(ARDUINO_ARCH_ESP32)
#include <esp_sleep.h>
#endif

namespace wildlife {

void PowerManager::begin() {
    // Classify the wakeup cause before any other initialisation so that
    // callers can query last_wake_source() at any point after begin().
#if defined(ARDUINO_ARCH_ESP32)
    wake_source_ = classify_wake_source(
        static_cast<std::uint32_t>(esp_sleep_get_wakeup_cause()));
#else
    wake_source_ = WakeSource::kColdBoot;
#endif

    if (kPirWakeEnabled) {
        pinMode(kPirPin, INPUT);
    }
}

void PowerManager::maybe_sleep(bool saw_activity) {
#if defined(ARDUINO_ARCH_ESP32)
    const PowerInputs inputs{
        kPirWakeEnabled,
        saw_activity,
        kPirWakeEnabled && (digitalRead(kPirPin) == HIGH),
    };
    if (evaluate_sleep_decision(inputs) == SleepDecision::kStayAwake) {
        return;
    }

    esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(kPirPin), 1);
    esp_sleep_enable_timer_wakeup(static_cast<std::uint64_t>(kDeepSleepSeconds) * 1000000ULL);
    delay(kDeepSleepSettleMs);
    esp_deep_sleep_start();
#else
    (void)saw_activity;
#endif
}

bool PowerManager::pir_wake_enabled() const {
    return kPirWakeEnabled;
}

WakeSource PowerManager::last_wake_source() const {
    return wake_source_;
}

}  // namespace wildlife