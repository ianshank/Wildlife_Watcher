#pragma once

#include <cstddef>
#include <cstdint>

#include "wildlife/compat/stubs/WiFi.h"

class PubSubClient {
  public:
    explicit PubSubClient(WiFiClient&) {}

    void setBufferSize(std::size_t) {}
    void setKeepAlive(std::uint16_t) {}
    void setSocketTimeout(std::uint16_t) {}
    void setServer(const char*, std::uint16_t) {}
    bool connected() const { return true; }
    int state() const { return 0; }
    void loop() {}

    bool connect(
        const char*,
        const char*,
        const char*,
        const char*,
        int,
        bool,
        const char*) {
        return true;
    }

    bool publish(const char*, const std::uint8_t*, std::size_t, bool) {
        return true;
    }
};