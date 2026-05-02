#pragma once

namespace wildlife {

class PowerManager {
  public:
    void begin();
    void maybe_sleep(bool saw_activity);
    bool pir_wake_enabled() const;
};

}  // namespace wildlife