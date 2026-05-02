#pragma once

#include <array>
#include <cstdio>

#include "wildlife/config.h"

namespace wildlife {

struct TopicNames {
    std::array<char, 64> detections{};
    std::array<char, 64> status{};
    std::array<char, 80> thumbs_prefix{};
};

inline TopicNames build_topic_names(const char* node_id) {
    TopicNames topics;
    std::snprintf(topics.detections.data(), topics.detections.size(), "%s/%s", kDetectionTopicRoot, node_id);
    std::snprintf(topics.status.data(), topics.status.size(), "%s/%s", kStatusTopicRoot, node_id);
    std::snprintf(topics.thumbs_prefix.data(), topics.thumbs_prefix.size(), "%s/%s", kThumbsTopicRoot, node_id);
    return topics;
}

}  // namespace wildlife