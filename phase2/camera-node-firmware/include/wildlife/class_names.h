#pragma once

// class_names.h — inline class-label lookup that carries no Arduino dependency.
// Include this header in both firmware translation units and Unity native tests.

#include <cstddef>
#include <cstdint>
#include <cstdio>

#include "wildlife/config.h"

namespace wildlife {

namespace detail {

/// Compile-time table built from the WILDLIFE_CLASS_NAMES macro.
inline const char* const kClassNameTable[] = {WILDLIFE_CLASS_NAMES};
inline constexpr std::size_t kClassNameCount =
    sizeof(kClassNameTable) / sizeof(kClassNameTable[0]);

}  // namespace detail

inline constexpr std::size_t kClassNameCount = detail::kClassNameCount;
inline constexpr std::size_t kClassNameFallbackBufferSize = 16U;

inline const char* configured_class_name(std::uint8_t class_id) noexcept {
    if (static_cast<std::size_t>(class_id) >= kClassNameCount) {
        return nullptr;
    }
    return detail::kClassNameTable[class_id];
}

/// Returns the semantic label for \p class_id.
/// When \p class_id is out of range, formats "class_<id>" into
/// \p fallback_buf (must be >= kClassNameFallbackBufferSize bytes) and returns it.
inline const char* class_name_for_id(std::uint8_t class_id,
                                     char* fallback_buf,
                                     std::size_t buf_len) noexcept {
    if (const char* configured = configured_class_name(class_id)) {
        return configured;
    }
    std::snprintf(fallback_buf, buf_len, "class_%u",
                  static_cast<unsigned>(class_id));
    return fallback_buf;
}

}  // namespace wildlife
