#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

struct boxes_t {
    std::uint16_t target = 0;
    std::uint16_t score = 0;
    int x = 0;
    int y = 0;
    int w = 0;
    int h = 0;
};

class SSCMA {
  public:
    void begin() {}
    int invoke() { return 0; }
    const std::vector<boxes_t>& boxes() const { return boxes_; }
    std::uint8_t* last_image() { return nullptr; }
    std::size_t last_image_size() const { return 0; }
    const std::vector<const char*>& classes() const { return classes_; }

  private:
    std::vector<boxes_t> boxes_{};
    std::vector<const char*> classes_{"unknown"};
};