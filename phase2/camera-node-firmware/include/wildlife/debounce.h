#pragma once

#include <array>
#include <cstdint>

namespace wildlife {

class ClassDebouncer {
  public:
    bool should_publish(std::uint8_t class_id, std::uint32_t now_ms, std::uint32_t debounce_ms) {
        const std::uint32_t last_seen = last_seen_ms_[class_id];
        if (last_seen != 0 && (now_ms - last_seen) < debounce_ms) {
            return false;
        }
        last_seen_ms_[class_id] = now_ms;
        return true;
    }

  private:
    std::array<std::uint32_t, 256> last_seen_ms_{};
};

}  // namespace wildlife