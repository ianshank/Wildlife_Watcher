#pragma once

#include <cstddef>
#include <cstdint>

inline std::size_t encode_base64_length(std::size_t input_length) {
    return ((input_length + 2U) / 3U) * 4U;
}

inline std::size_t encode_base64(const std::uint8_t*, std::size_t, std::uint8_t*) {
    return 0;
}