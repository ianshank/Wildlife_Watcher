#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#define CMD_OK 0

struct boxes_t {
    std::uint16_t target = 0;
    std::uint16_t score = 0;
    int x = 0;
    int y = 0;
    int w = 0;
    int h = 0;
};

struct classes_t {
    std::uint8_t target = 0;
    std::uint8_t score = 0;
};

class SSCMA {
  public:
    void begin() {}
    int invoke() { return 0; }
    int save_jpeg() { return CMD_OK; }
    const std::vector<boxes_t>& boxes() const { return boxes_; }
    String last_image() const { return String(); }
    const std::vector<classes_t>& classes() const { return classes_; }

  private:
    std::vector<boxes_t> boxes_{};
    std::vector<classes_t> classes_{};
};