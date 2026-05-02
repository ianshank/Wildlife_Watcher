#pragma once

#include "wildlife/compat/arduino_wifi.h"

#include "wildlife/config.h"

namespace wildlife {

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