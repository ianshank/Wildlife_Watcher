#include "wildlife/sscma_io.h"

#include <cstdio>

#include <Wire.h>

namespace wildlife {

namespace {

String format_class_name(std::uint8_t class_id) {
    char class_name[16];
    std::snprintf(class_name, sizeof(class_name), "class_%u", static_cast<unsigned>(class_id));
    return String(class_name);
}

}  // namespace

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
    return true;
}

bool SscmaSensor::capture_thumb(String* jpeg_base64) {
    if (jpeg_base64 == nullptr) {
        return false;
    }

    if (ai_.save_jpeg() != CMD_OK) {
        Serial.println("[wildlife][W] save_jpeg failed");
        return false;
    }

    *jpeg_base64 = ai_.last_image();
    if (jpeg_base64->length() == 0) {
        Serial.println("[wildlife][W] SSCMA returned an empty thumbnail");
        return false;
    }
    return true;
}

bool SscmaSensor::should_publish(std::uint8_t class_id, std::uint32_t now_ms, std::uint32_t debounce_ms) {
    return debouncer_.should_publish(class_id, now_ms, debounce_ms);
}

String SscmaSensor::class_name(std::uint8_t class_id) const {
    return format_class_name(class_id);
}

}  // namespace wildlife