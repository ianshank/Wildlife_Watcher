#pragma once

#include <cstdint>

#include "wildlife/power_policy.h"

namespace wildlife {

class PowerManager {
  public:
    void begin();
    void maybe_sleep(bool saw_activity);
    bool pir_wake_enabled() const;

    // Returns the wakeup source classified during begin().  Always kColdBoot
    // in the native (non-ESP32) test environment.
    WakeSource last_wake_source() const;

  private:
    WakeSource wake_source_ = WakeSource::kColdBoot;
    std::uint32_t boot_grace_until_ms_ = 0U;
};

}  // namespace wildlife