#pragma once

// sscma_decode.h — pure helpers that translate raw SSCMA detection box fields
// into the values the firmware emits over MQTT. Carries no Arduino, Wire, or
// SSCMA dependency so it can be exercised from the Unity native test env.

#include <cstdint>

namespace wildlife {

/// Extracts the low byte of a SSCMA `boxes_t::target` value as the class id.
inline constexpr std::uint8_t class_id_from_target(std::uint16_t target) noexcept {
    return static_cast<std::uint8_t>(target & 0xFFU);
}

/// Maps a raw SSCMA score (carried as uint16_t in `boxes_t::score`, documented
/// range 0..100) to a normalized confidence in [0.0, 1.0]. Accepts the full
/// `uint16_t` so out-of-spec scores do not silently wrap to a different value.
inline constexpr float score_to_confidence(std::uint16_t score) noexcept {
    return static_cast<float>(score) / 100.0F;
}

/// Returns the running maximum of two scores; ties keep the existing maximum.
inline constexpr std::uint16_t track_max_score(std::uint16_t current_max,
                                               std::uint16_t candidate) noexcept {
    return (candidate > current_max) ? candidate : current_max;
}

/// Returns true when the highest observed score crosses the thumbnail-publish
/// threshold (>= threshold), matching the firmware's existing gating policy.
inline constexpr bool should_capture_thumb(std::uint16_t max_score,
                                           std::uint16_t threshold) noexcept {
    return max_score >= threshold;
}

}  // namespace wildlife
