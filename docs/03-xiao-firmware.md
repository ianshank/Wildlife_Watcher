# 03 — XIAO ESP32S3 Sense Firmware

The XIAO ESP32S3 Sense in this build does two jobs:

1. Talks to the Grove Vision AI V2 over I2C using the **SSCMA protocol** to
   pull inference results.
2. Connects to your 2.4 GHz WiFi and publishes those results to the Pi's
   Mosquitto broker as MQTT messages.

## 1. Install PlatformIO

The cleanest path is PlatformIO under VS Code. From a workstation:

- Install VS Code → install the "PlatformIO IDE" extension.
- Open `wildlife-watcher-phase1/camera-node-firmware/` as a folder.

(Arduino IDE works too if you prefer — install the ESP32 board package, then
install the `Seeed_Arduino_SSCMA`, `PubSubClient`, and `ArduinoJson` libraries
via Library Manager. Copy `src/main.cpp` content into a sketch.)

## 2. Fill in `secrets.h`

```bash
cd camera-node-firmware/include
cp secrets.h.example secrets.h
```

Edit `secrets.h`:

```cpp
#define WIFI_SSID       "YourNetwork"        // 2.4 GHz only
#define WIFI_PASSWORD   "your-wifi-password"

#define MQTT_BROKER     "192.168.1.42"       // IP of wildlife-display Pi
#define MQTT_PORT       1883
#define MQTT_USER       "wildlife"           // matches Mosquitto passwd
#define MQTT_PASSWORD   "your-broker-pass"

#define NODE_ID         "feeder-01"          // unique per camera node
```

> **2.4 GHz only.** The XIAO ESP32S3's WiFi radio does not support 5 GHz.
> If your home network is 5 GHz only, enable a 2.4 GHz SSID on your router.

## 3. Build and flash

In PlatformIO:

1. Plug the **XIAO ESP32S3 Sense** into USB-C (NOT the Grove module yet).
2. Click the **Upload** button (→ icon) in the PlatformIO toolbar.
3. If upload fails with "no device found", hold the BOOT button on the XIAO,
   tap RESET, release BOOT, then retry.

Watch the serial monitor at 115200 baud. You should see:

```
[wildlife] booting node feeder-01
[wildlife] WiFi connecting to YourNetwork...
[wildlife] WiFi connected: 192.168.1.83
[wildlife] MQTT connecting to 192.168.1.42:1883...
[wildlife] MQTT connected
[wildlife] SSCMA: waiting for Grove Vision AI V2...
[wildlife] SSCMA: not responding (expected — Grove not connected yet)
```

## 4. Physically connect XIAO to Grove

Power off both devices. Connect the XIAO ESP32S3 Sense to the Grove Vision AI
V2 using the **Grove I2C connector** (4-pin JST):

| Grove Vision AI V2 | XIAO ESP32S3 Sense       |
|--------------------|--------------------------|
| GND                | GND                      |
| 3V3 (or 5V)        | 3V3 (5V also OK)         |
| SDA                | SDA (D4 / GPIO5)         |
| SCL                | SCL (D5 / GPIO6)         |

Easiest path: use a Seeed Studio "Grove to XIAO" adapter cable, which is just
a Grove 4-pin JST to female Dupont breakout that lines up directly with the
XIAO's pinout.

Power both devices via USB-C. Either device can power the pair if connected
via the I2C/Grove cable, but for a clean Phase 1 setup I recommend powering
each via its own USB-C cable to a 5V/3A supply or USB hub.

## 5. Verify end-to-end

Open the serial monitor on the XIAO again:

```
[wildlife] SSCMA: device responding, model="yolo_world_bird", classes=1
[wildlife] inference: 0 detections (5.2 fps)
[wildlife] inference: 0 detections (5.0 fps)
```

Wave a printed picture of a bird in front of the camera (or point it at a
phone showing one). You should see:

```
[wildlife] inference: 1 detection: bird @ 0.81 [142,88,168,152]
[wildlife] published wildlife/detections/feeder-01
[wildlife] published wildlife/thumbs/feeder-01/f_018472 (8.3 KB)
```

Simultaneously, on the Pi's kiosk UI, a new event appears in the feed with
the thumbnail. If both happen, Phase 1 is working.

## What the firmware does, briefly

- `setup()`: connect WiFi, connect MQTT, init SSCMA over I2C (Wire), publish
  retained `wildlife/status/<node_id>` = `online` with the device IP.
- `loop()`:
  1. Call `AI.invoke()` — non-blocking inference fetch from the Grove module.
  2. If detections are present, build the JSON event and publish to
     `wildlife/detections/<node_id>` with QoS 1.
  3. If a detection's confidence ≥ `THUMB_PUBLISH_THRESHOLD`, base64-encode
     the JPEG that the SSCMA library exposes and publish it as a retained
     message on `wildlife/thumbs/<node_id>/<frame_id>`.
  4. Heartbeat: every 30 s, refresh the retained `status` topic.
  5. LWT (Last Will and Testament): broker auto-publishes `offline` to the
     status topic if the XIAO loses WiFi or power.

Detection events are throttled with a per-class debounce (default 2 seconds)
so a single bird sitting on the feeder doesn't generate 50 events/second.

Next step: `04-bring-up.md`.
