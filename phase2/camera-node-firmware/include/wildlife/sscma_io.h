#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include <Seeed_Arduino_SSCMA.h>

#include "wildlife/debounce.h"

namespace wildlife {

struct DetectionFrame {
    std::vector<boxes_t> boxes;
    const std::uint8_t* jpeg_ptr = nullptr;
    std::size_t jpeg_len = 0;
};

class SscmaSensor {
  public:
    bool begin();
    bool poll(DetectionFrame* frame);
    bool should_publish(std::uint8_t class_id, std::uint32_t now_ms, std::uint32_t debounce_ms);
    const char* class_name(std::uint8_t class_id) const;

  private:
    SSCMA ai_;
    ClassDebouncer debouncer_;
};

}  // namespace wildlife