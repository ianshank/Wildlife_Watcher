#pragma once

#include <cstdint>

namespace wildlife {

// ---------------------------------------------------------------------------
// PIR debounce helper
// ---------------------------------------------------------------------------
// All arithmetic is performed on std::uint32_t to match the range of the
// ESP32 micros() timer.  Wrap-around is handled correctly: (uint32_t)(now -
// last) overflows in the same direction as the hardware counter, so the
// comparison `elapsed >= debounce_us` is always valid within any half-period
// of the 32-bit clock (~35 minutes).
//
// Pure function: no Arduino dependency, safe for native unit tests.

// Returns true when the PIR edge at `now_us` microseconds should be accepted,
// i.e. at least `debounce_us` microseconds have elapsed since `last_edge_us`.
//
// The first call after reset can pass last_edge_us == 0 and now_us == 0; the
// function still returns true because elapsed == 0 == debounce_us when
// debounce_us is also 0, and a caller with debounce_us == 0 explicitly opts
// out of debouncing.  For all real debounce periods, pass last_edge_us with
// a sentinel value (e.g. std::numeric_limits<uint32_t>::max()) to guarantee
// the first edge is always accepted.
constexpr bool should_accept_pir_edge(
    std::uint32_t last_edge_us,
    std::uint32_t now_us,
    std::uint32_t debounce_us) noexcept {
    const std::uint32_t elapsed = now_us - last_edge_us;  // wraps correctly on overflow
    return elapsed >= debounce_us;
}

}  // namespace wildlife
