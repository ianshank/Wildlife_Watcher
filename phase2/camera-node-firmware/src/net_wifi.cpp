#include "wildlife/net_wifi.h"

#include "wildlife/config.h"

namespace wildlife {

void WifiLink::connect_with_timeout() {
    Serial.printf("[wildlife][I] WiFi connecting to %s\n", credentials_.wifi_ssid);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(credentials_.wifi_ssid, credentials_.wifi_password);

    const std::uint32_t started_at = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - started_at > kWifiConnectTimeoutMs) {
            Serial.println("[wildlife][E] WiFi timeout, restarting");
            ESP.restart();
        }
        delay(kWifiPollIntervalMs);
        Serial.print('.');
    }
    Serial.printf("\n[wildlife][I] WiFi connected: %s\n", WiFi.localIP().toString().c_str());
}

void WifiLink::begin() {
    connect_with_timeout();
}

void WifiLink::ensure_connected() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[wildlife][W] WiFi lost, reconnecting");
        connect_with_timeout();
    }
}

String WifiLink::local_ip() const {
    return WiFi.localIP().toString();
}

}  // namespace wildlife