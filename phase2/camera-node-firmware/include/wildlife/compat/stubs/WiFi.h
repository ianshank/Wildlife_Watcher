#pragma once

#include "wildlife/compat/stubs/Arduino.h"

enum wl_status_t {
    WL_DISCONNECTED = 0,
    WL_CONNECTED = 3,
};

inline constexpr int WIFI_STA = 1;

class IPAddress {
  public:
    String toString() const {
        return String("0.0.0.0");
    }
};

class WiFiClass {
  public:
    void mode(int) {}

    void setSleep(bool) {}

    void begin(const char*, const char*) {}

    wl_status_t status() const {
        return WL_CONNECTED;
    }

    IPAddress localIP() const {
        return IPAddress{};
    }
};

inline WiFiClass WiFi;