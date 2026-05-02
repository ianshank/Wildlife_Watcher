#pragma once

#include <cstddef>
#include <cstdint>

#include <PubSubClient.h>

#include "wildlife/config.h"
#include "wildlife/topic_names.h"

namespace wildlife {

class MqttPublisher {
  public:
    MqttPublisher(PubSubClient& client, const Credentials& credentials, TopicNames topics)
        : client_(client), credentials_(credentials), topics_(topics) {}

    void begin();
    void ensure_connected();
    void loop();
    bool publish_status(const char* state, const char* ip, std::uint32_t uptime_ms, bool retained = true);
    bool publish_detection(const char* payload, std::size_t payload_len);
    bool publish_thumb(const char* frame_id, const char* encoded_jpeg, std::size_t encoded_len);

    const TopicNames& topics() const { return topics_; }

  private:
    PubSubClient& client_;
    const Credentials& credentials_;
    TopicNames topics_;
};

}  // namespace wildlife