#pragma once

#include <cstdarg>
#include <cstdio>
#include <cstdint>
#include <string>

class String {
  public:
    String() = default;
    String(const char* value) : value_(value == nullptr ? "" : value) {}

    const char* c_str() const {
        return value_.c_str();
    }

  private:
    std::string value_;
};

class SerialClass {
  public:
    void begin(unsigned long) const {}

    void println() const {}

  template <typename T>
  void println(const T&) const {}

  template <typename T>
  void print(const T&) const {}

    void printf(const char* format, ...) const {
        if (format == nullptr) {
            return;
        }
        va_list args;
        va_start(args, format);
        std::vfprintf(stdout, format, args);
        va_end(args);
    }
};

static SerialClass Serial;

class EspClass {
  public:
    void restart() const {}
};

static EspClass ESP;

inline std::uint32_t millis() {
    return 0;
}

inline void delay(unsigned long) {}