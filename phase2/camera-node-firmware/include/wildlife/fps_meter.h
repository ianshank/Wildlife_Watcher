#pragma once

#include <cstdint>

namespace wildlife {

class FpsMeter {
  public:
    explicit FpsMeter(std::uint32_t window_ms = 1000) : window_ms_(window_ms) {}

    float tick(std::uint32_t now_ms) {
        if (window_start_ms_ == 0) {
            window_start_ms_ = now_ms;
        }
        ++sample_count_;
        const std::uint32_t window_duration = now_ms - window_start_ms_;
        if (window_duration >= window_ms_) {
            const float instant_fps = (sample_count_ * 1000.0F) / static_cast<float>(window_duration);
            smoothed_fps_ = smoothed_fps_ == 0.0F
                ? instant_fps
                : (0.7F * smoothed_fps_) + (0.3F * instant_fps);
            window_start_ms_ = now_ms;
            sample_count_ = 0;
        }
        return smoothed_fps_;
    }

    float current() const { return smoothed_fps_; }

  private:
    std::uint32_t window_ms_;
    std::uint32_t window_start_ms_ = 0;
    std::uint32_t sample_count_ = 0;
    float smoothed_fps_ = 0.0F;
};

}  // namespace wildlife