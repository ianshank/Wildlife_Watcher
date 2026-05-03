#pragma once

#include <cstdint>

#include "wildlife/compat/arduino_wifi.h"

#include "wildlife/config.h"

namespace wildlife {

// ---------------------------------------------------------------------------
// WiFi reconnect backoff
// ---------------------------------------------------------------------------
//
// Pure capped exponential backoff: returns base * 2^attempt, saturating at
// max_ms. attempt is the 0-based reconnect attempt count.
//
// Implemented with overflow-safe shift using a 64-bit intermediate to avoid
// undefined behaviour when (attempt >= 32). No Arduino dependency, safe for
// native unit tests.
constexpr std::uint32_t next_wifi_backoff_ms(
    std::uint32_t attempt,
    std::uint32_t base_ms = kWifiBackoffBaseMs,
    std::uint32_t max_ms = kWifiBackoffMaxMs) noexcept {
    if (base_ms == 0U) {
        return 0U;
    }
    if (attempt >= 32U) {
        return max_ms;
    }
    const std::uint64_t scaled =
        static_cast<std::uint64_t>(base_ms) << attempt;
    if (scaled >= static_cast<std::uint64_t>(max_ms)) {
        return max_ms;
    }
    return static_cast<std::uint32_t>(scaled);
}

class WifiLink {
  public:
    explicit WifiLink(const Credentials& credentials) : credentials_(credentials) {}

    void begin();
    void ensure_connected();
    String local_ip() const;

  private:
    void connect_with_timeout();

    const Credentials& credentials_;
};

}  // namespace wildlife