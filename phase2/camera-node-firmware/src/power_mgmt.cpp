#include "wildlife/power_mgmt.h"

#include <Arduino.h>

#include "wildlife/config.h"

#if defined(ARDUINO_ARCH_ESP32)
#include <esp_sleep.h>
#endif

namespace wildlife {

void PowerManager::begin() {
    if (kPirWakeEnabled) {
        pinMode(kPirPin, INPUT);
    }
}

void PowerManager::maybe_sleep(bool saw_activity) {
#if defined(ARDUINO_ARCH_ESP32)
    if (!kPirWakeEnabled || saw_activity) {
        return;
    }
    if (digitalRead(kPirPin) == HIGH) {
        return;
    }

    esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(kPirPin), 1);
    esp_sleep_enable_timer_wakeup(static_cast<std::uint64_t>(kDeepSleepSeconds) * 1000000ULL);
    delay(20);
    esp_deep_sleep_start();
#else
    (void)saw_activity;
#endif
}

bool PowerManager::pir_wake_enabled() const {
    return kPirWakeEnabled;
}

}  // namespace wildlife