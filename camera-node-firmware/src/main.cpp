// main.cpp — Wildlife Watcher camera node firmware.
//
// Hardware: Seeed Studio XIAO ESP32S3 Sense, connected to a Grove Vision AI V2
// over I2C (SDA=GPIO5, SCL=GPIO6 on XIAO; default 0x62 address on Grove).
//
// Behavior:
//   1. Connects to 2.4 GHz WiFi (XIAO ESP32S3 does not support 5 GHz).
//   2. Connects to the Mosquitto broker on the Pi.
//   3. Sets a Last Will message so the broker auto-publishes "offline" if
//      this node drops off the network.
//   4. In loop(): asks the Grove Vision AI V2 for the latest inference, parses
//      it, debounces per-class events, and publishes:
//        wildlife/detections/<NODE_ID>            QoS 1, JSON event
//        wildlife/thumbs/<NODE_ID>/<frame_id>     QoS 0, retained, base64 JPEG
//        wildlife/status/<NODE_ID>                QoS 1, retained, online/offline
//
// Throttling:
//   - Per-class debounce: a class can only re-fire after CLASS_DEBOUNCE_MS.
//   - Heartbeat: the status topic is refreshed every HEARTBEAT_MS.
//
// Notes on the SSCMA library:
//   The Seeed_Arduino_SSCMA library wraps the protocol the Grove Vision AI V2
//   exposes over I2C. After AI.invoke(), AI.boxes() returns the bounding boxes
//   from the most recent inference, and AI.last_image() returns a JPEG buffer
//   of the cropped region (used for thumbnails).

#include "wildlife/compat/firmware_deps.h"

#if __has_include("secrets.h")
#include "secrets.h"
#elif __has_include("secrets.h.example")
#include "secrets.h.example"
#else
#error "Provide secrets.h or keep secrets.h.example available for editor compatibility."
#endif

// ---------------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------------

static const uint32_t CLASS_DEBOUNCE_MS       = 2000;   // 2 s per class
static const uint32_t HEARTBEAT_MS            = 30000;  // 30 s status refresh
static const uint16_t THUMB_PUBLISH_THRESHOLD = 50;     // confidence (0-100)
static const size_t   MAX_THUMB_BYTES         = 16384;  // skip if larger

// Topic templates (filled in setup())
static char topic_detections[64];
static char topic_status[64];
static char topic_thumbs_prefix[80];

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------

SSCMA AI;
WiFiClient   wifi;
PubSubClient mqtt(wifi);

static uint32_t last_class_seen_ms[256] = {0};
static uint32_t frame_counter = 0;
static uint32_t last_heartbeat_ms = 0;
static uint32_t fps_accum_count   = 0;
static uint32_t fps_window_start  = 0;
static float    fps_smoothed      = 0.0f;

// ---------------------------------------------------------------------------
// WiFi
// ---------------------------------------------------------------------------

static void wifiConnect() {
  Serial.printf("[wildlife] WiFi connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // keep responsive at the cost of ~10 mA
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > 30000) {
      Serial.println("[wildlife] WiFi timeout, restarting");
      ESP.restart();
    }
    delay(250);
    Serial.print(".");
  }
  Serial.printf("\n[wildlife] WiFi connected: %s\n",
                WiFi.localIP().toString().c_str());
}

// ---------------------------------------------------------------------------
// MQTT
// ---------------------------------------------------------------------------

static void publishStatus(const char* state, bool retained = true) {
  StaticJsonDocument<192> doc;
  doc["state"]   = state;
  doc["ip"]      = WiFi.localIP().toString();
  doc["node_id"] = NODE_ID;
  // ms uptime is enough for ordering; the Pi has a real clock and timestamps
  // observations on its end as well.
  doc["uptime_ms"] = millis();

  char buf[192];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(topic_status, (const uint8_t*)buf, n, retained);
}

static void mqttConnect() {
  // Buffer must be big enough to hold a base64 JPEG thumbnail
  mqtt.setBufferSize(24 * 1024);
  mqtt.setKeepAlive(45);
  mqtt.setSocketTimeout(15);
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);

  while (!mqtt.connected()) {
    Serial.printf("[wildlife] MQTT connecting to %s:%d\n", MQTT_BROKER, MQTT_PORT);

    // Last Will: broker publishes this when our keepalive lapses.
    StaticJsonDocument<96> willDoc;
    willDoc["state"] = "offline";
    willDoc["node_id"] = NODE_ID;
    char willBuf[96];
    size_t willLen = serializeJson(willDoc, willBuf, sizeof(willBuf));

    bool ok = mqtt.connect(
        NODE_ID,                // client id
        MQTT_USER, MQTT_PASSWORD,
        topic_status,           // will topic
        1,                      // will QoS
        true,                   // will retained
        willBuf                 // will payload
    );
    if (ok) {
      Serial.println("[wildlife] MQTT connected");
      publishStatus("online", true);
    } else {
      Serial.printf("[wildlife] MQTT connect failed rc=%d, retrying in 3s\n",
                    mqtt.state());
      delay(3000);
    }
  }
}

// ---------------------------------------------------------------------------
// Detection publishing
// ---------------------------------------------------------------------------

static void publishThumbIfAvailable(const char* frame_id) {
  // SSCMA library exposes the most recent JPEG via last_image(). Length 0
  // means no image (some models don't emit one). On the Sense variant this
  // ends up around 5-15 KB at default settings.
  size_t   jpegLen = AI.last_image_size();
  uint8_t* jpegPtr = AI.last_image();
  if (!jpegPtr || jpegLen == 0 || jpegLen > MAX_THUMB_BYTES) {
    return;
  }

  // Encode to base64 to keep the MQTT payload ASCII-safe (Mosquitto handles
  // binary fine, but base64 is much easier to inspect with mosquitto_sub).
  size_t b64Len = encode_base64_length(jpegLen);
  // Stack allocate up to ~22 KB; PSRAM-backed heap also works but adds latency.
  static uint8_t b64Buf[22 * 1024];
  if (b64Len + 1 > sizeof(b64Buf)) {
    Serial.printf("[wildlife] thumb too big for buffer (%u bytes)\n",
                  (unsigned)b64Len);
    return;
  }
  size_t actual = encode_base64(jpegPtr, jpegLen, b64Buf);
  b64Buf[actual] = 0;

  char topic[96];
  snprintf(topic, sizeof(topic), "%s/%s", topic_thumbs_prefix, frame_id);
  mqtt.publish(topic, b64Buf, actual, /*retained=*/true);
  Serial.printf("[wildlife] published %s (%u JPEG bytes, %u b64)\n",
                topic, (unsigned)jpegLen, (unsigned)actual);
}

static void publishDetections(const std::vector<boxes_t>& boxes) {
  // Build the detection event JSON.
  StaticJsonDocument<2048> doc;
  char ts[32];
  // We don't have NTP here in Phase 1; the Pi assigns its own timestamp on
  // arrival. We send millis() so the firmware's relative ordering is clear.
  snprintf(ts, sizeof(ts), "%lu", (unsigned long)millis());
  doc["ts"]       = ts;
  doc["node_id"]  = NODE_ID;
  uint32_t this_frame = ++frame_counter;
  char frame_id[24];
  snprintf(frame_id, sizeof(frame_id), "f_%06lu", (unsigned long)this_frame);
  doc["frame_id"] = frame_id;
  doc["model"]    = "grove_vision_ai_v2";
  doc["fps"]      = fps_smoothed;

  JsonArray dets = doc.createNestedArray("detections");
  uint32_t now_ms = millis();
  bool any_to_publish = false;
  uint16_t max_conf = 0;

  for (const auto& b : boxes) {
    // Apply per-class debounce
    uint32_t last_seen = last_class_seen_ms[b.target & 0xFF];
    if (last_seen != 0 && (now_ms - last_seen) < CLASS_DEBOUNCE_MS) {
      continue;
    }
    last_class_seen_ms[b.target & 0xFF] = now_ms;
    any_to_publish = true;

    JsonObject d = dets.createNestedObject();
    d["class_id"]   = b.target;
    d["class_name"] = AI.classes()[b.target];   // SSCMA exposes class names
    d["confidence"] = b.score / 100.0f;
    JsonArray bbox = d.createNestedArray("bbox");
    bbox.add(b.x);
    bbox.add(b.y);
    bbox.add(b.w);
    bbox.add(b.h);
    if (b.score > max_conf) max_conf = b.score;
  }

  if (!any_to_publish) return;

  char buf[2048];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  bool ok = mqtt.publish(topic_detections, (const uint8_t*)buf, n,
                         /*retained=*/false);
  Serial.printf("[wildlife] published %s (%d detections, ok=%d)\n",
                topic_detections, (int)dets.size(), (int)ok);

  if (max_conf >= THUMB_PUBLISH_THRESHOLD) {
    publishThumbIfAvailable(frame_id);
  }
}

// ---------------------------------------------------------------------------
// Setup / loop
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.printf("[wildlife] booting node %s\n", NODE_ID);

  // Build topic strings once
  snprintf(topic_detections, sizeof(topic_detections),
           "wildlife/detections/%s", NODE_ID);
  snprintf(topic_status, sizeof(topic_status),
           "wildlife/status/%s", NODE_ID);
  snprintf(topic_thumbs_prefix, sizeof(topic_thumbs_prefix),
           "wildlife/thumbs/%s", NODE_ID);

  Wire.begin();          // SDA=GPIO5, SCL=GPIO6 on XIAO ESP32S3
  Wire.setClock(400000); // Fast I2C
  AI.begin();            // SSCMA auto-detects the Grove Vision AI V2

  wifiConnect();
  mqttConnect();

  fps_window_start = millis();

  Serial.println("[wildlife] ready");
}

void loop() {
  // Keep WiFi/MQTT alive
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[wildlife] WiFi lost, reconnecting");
    wifiConnect();
  }
  if (!mqtt.connected()) {
    mqttConnect();
  }
  mqtt.loop();

  // Heartbeat
  uint32_t now = millis();
  if (now - last_heartbeat_ms >= HEARTBEAT_MS) {
    last_heartbeat_ms = now;
    publishStatus("online", true);
  }

  // Pull latest inference from the Grove Vision AI V2.
  // AI.invoke() returns 0 on success; nonzero typically means the device is
  // busy or not connected. We just retry next loop.
  int rc = AI.invoke();
  if (rc != 0) {
    delay(20);
    return;
  }

  // FPS bookkeeping (rolling 1-second window)
  fps_accum_count++;
  uint32_t window_dur = now - fps_window_start;
  if (window_dur >= 1000) {
    float instant_fps = (fps_accum_count * 1000.0f) / window_dur;
    fps_smoothed = (fps_smoothed == 0.0f)
        ? instant_fps
        : (0.7f * fps_smoothed + 0.3f * instant_fps);
    fps_window_start = now;
    fps_accum_count = 0;
  }

  const auto& boxes = AI.boxes();
  if (!boxes.empty()) {
    publishDetections(boxes);
  }
}
