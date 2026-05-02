#pragma once

#include <Arduino.h>

#include <cstddef>
#include <cstdint>
#include <vector>

#include <Seeed_Arduino_SSCMA.h>

#include "wildlife/debounce.h"

namespace wildlife {

struct DetectionFrame {
    std::vector<boxes_t> boxes;
};

class SscmaSensor {
  public:
    bool begin();
    bool poll(DetectionFrame* frame);
    bool capture_thumb(String* jpeg_base64);
    bool should_publish(std::uint8_t class_id, std::uint32_t now_ms, std::uint32_t debounce_ms);
    String class_name(std::uint8_t class_id) const;

  private:
    SSCMA ai_;
    ClassDebouncer debouncer_;
};

}  // namespace wildlife