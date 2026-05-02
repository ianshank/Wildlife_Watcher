#include "wildlife/sscma_io.h"

#include <Wire.h>

namespace wildlife {

bool SscmaSensor::begin() {
    Wire.begin();
    Wire.setClock(400000);
    ai_.begin();
    return true;
}

bool SscmaSensor::poll(DetectionFrame* frame) {
    if (frame == nullptr) {
        return false;
    }

    const int rc = ai_.invoke();
    if (rc != 0) {
        return false;
    }

    frame->boxes = ai_.boxes();
    frame->jpeg_ptr = ai_.last_image();
    frame->jpeg_len = ai_.last_image_size();
    return true;
}

bool SscmaSensor::should_publish(std::uint8_t class_id, std::uint32_t now_ms, std::uint32_t debounce_ms) {
    return debouncer_.should_publish(class_id, now_ms, debounce_ms);
}

const char* SscmaSensor::class_name(std::uint8_t class_id) const {
    const auto classes = ai_.classes();
    if (class_id < classes.size()) {
        return classes[class_id];
    }
    return "unknown";
}

}  // namespace wildlife