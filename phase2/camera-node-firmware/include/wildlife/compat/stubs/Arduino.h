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
    void println(const char*) const {}

    void print(char) const {}

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

inline SerialClass Serial;

class EspClass {
  public:
    void restart() const {}
};

inline EspClass ESP;

inline std::uint32_t millis() {
    return 0;
}

inline void delay(unsigned long) {}

inline void pinMode(int, int) {}

inline int digitalRead(int) {
    return 0;
}

inline constexpr int INPUT = 0;
inline constexpr int HIGH = 1;