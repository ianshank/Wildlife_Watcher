#pragma once

#include "wildlife/compat/stubs/Arduino.h"

using wl_status_t = int;

inline constexpr wl_status_t WL_DISCONNECTED = 0;
inline constexpr wl_status_t WL_CONNECTED = 3;

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
    int status() const;
    IPAddress localIP() const { return IPAddress{}; }
};

class WiFiClient {};

static WiFiClass WiFi;

inline int WiFiClass::status() const {
  return WL_CONNECTED;
}