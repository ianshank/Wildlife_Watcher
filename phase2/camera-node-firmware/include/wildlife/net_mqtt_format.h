#pragma once

#include <cstddef>
#include <cstdio>

namespace wildlife {

constexpr std::size_t base64_encoded_length(std::size_t raw_bytes) noexcept {
    return ((raw_bytes + 2U) / 3U) * 4U;
}

constexpr std::size_t max_thumb_payload_bytes(std::size_t max_thumb_bytes) noexcept {
    return base64_encoded_length(max_thumb_bytes);
}

constexpr bool thumb_payload_fits(std::size_t encoded_len, std::size_t max_thumb_bytes) noexcept {
    return encoded_len <= max_thumb_payload_bytes(max_thumb_bytes);
}

inline std::size_t format_thumb_topic(
    char* buffer,
    std::size_t buffer_size,
    const char* thumbs_prefix,
    const char* frame_id) noexcept {
    if (buffer == nullptr || buffer_size == 0 || thumbs_prefix == nullptr || frame_id == nullptr) {
        return 0;
    }

    const int written = std::snprintf(buffer, buffer_size, "%s/%s", thumbs_prefix, frame_id);
    if (written < 0) {
        buffer[0] = '\0';
        return 0;
    }

    return static_cast<std::size_t>(written);
}

}  // namespace wildlife