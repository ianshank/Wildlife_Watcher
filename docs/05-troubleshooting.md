# 05 — Troubleshooting

## MQTT not reachable from LAN

**Symptom**: `mosquitto_pub` from another machine times out or returns
`Connection refused`.

**Causes & fixes**:

1. Mosquitto is bound to localhost only. Check `/etc/mosquitto/conf.d/wildlife.conf`
   has `listener 1883 0.0.0.0` (the installer sets this, but verify after
   any manual edit). Restart: `sudo systemctl restart mosquitto`.
2. Pi firewall (ufw) blocks 1883. Default Raspberry Pi OS has no firewall,
   but if you enabled one: `sudo ufw allow 1883/tcp`.
3. The Pi is on a different subnet from your laptop (e.g., guest WiFi vs.
   main WiFi). Put both on the same SSID.
4. Auth failure looks like a connection failure on some clients. Confirm
   the user/password by running `mosquitto_sub` *on the Pi itself* first.

## Camera node never publishes `online`

**Symptom**: `wildlife/status/feeder-01` is empty, no detections arrive.

**Causes & fixes**:

1. **Wrong WiFi band.** XIAO ESP32S3 only supports 2.4 GHz. Confirm your
   `WIFI_SSID` in `secrets.h` is the 2.4 GHz network, not the 5 GHz one.
   On many routers the 5 GHz network has a different SSID (like
   `MyNetwork-5G`).
2. **Wrong broker IP.** From the Pi, run `hostname -I` to get its current
   IP, paste that into `MQTT_BROKER`. mDNS `.local` names sometimes don't
   resolve on ESP32 — use the bare IP.
3. **Bad MQTT credentials.** Check the XIAO serial monitor for
   `MQTT connection failed, rc=-2` or similar. `rc=4` or `rc=5` means auth
   failed; verify the user/password match the Mosquitto passwd file.
4. **WiFi signal too weak.** Move the camera node closer to the AP for
   bring-up; tune location after Phase 1 works.

## XIAO connects to MQTT but no detections ever publish

**Symptom**: `online` status appears, but `wildlife/detections/...` stays
empty even when waving a target in front of the camera.

**Causes & fixes**:

1. **SenseCraft preview is still active.** This is the #1 issue. The Grove
   Vision AI V2 will not stream inference results to the I2C/UART output if
   SenseCraft has the preview running. Reconnect the Grove to your laptop
   in SenseCraft, click **Stop** then **Disconnect**, unplug.
2. **No model deployed.** The Grove must have a model flashed. Reflash via
   SenseCraft (`02-grove-flashing.md`).
3. **I2C wiring backwards.** Swap SDA/SCL. Verify with `i2cdetect -y 1` on
   any host that can speak I2C — Grove Vision AI V2 should appear at `0x62`.
4. **Confidence threshold too high.** In SenseCraft, the per-model confidence
   threshold may be set above what your scene produces. Lower to 0.4 and
   redeploy.

## Kiosk UI shows nothing / black screen

1. Confirm the Waveshare display works: `sudo systemctl stop wildlife-kiosk`
   then run `xinit /usr/bin/matchbox-window-manager &` and open `xeyes`.
2. Check the kiosk service log: `journalctl -u wildlife-kiosk -n 100`.
3. Common Python errors:
   - `Could not connect to display`: the X session isn't up yet. The
     systemd unit waits for `graphical.target` — confirm it's reached with
     `systemctl get-default`.
   - `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`: install
     `libxcb-xinerama0 libxkbcommon-x11-0`.

## Thumbnails don't render

1. Open the SQLite DB: are thumbnails being recorded?
   `SELECT frame_id, length(thumb_jpeg) FROM observations LIMIT 5;`
   Should show non-zero byte counts.
2. Confidence below `THUMB_PUBLISH_THRESHOLD` (default 0.5) means the
   firmware skips publishing the thumbnail to save bandwidth. Lower it in
   `main.cpp` or use a stronger detection.
3. Mosquitto's `message_size_limit` may be too low. The installer sets it
   to 65536 bytes which is plenty for 160×160 JPEGs at quality 70.

## Pi Zero 2 W feels sluggish

This is a 1 GHz quad-core A53 with 512 MB RAM running an X server. It is
inherently sluggish for GUI work. Mitigations the kiosk app already uses:

- No compositor (raw matchbox WM).
- Thumbnails downsampled and cached.
- Event feed virtualized — only renders visible rows.
- SQLite uses `PRAGMA synchronous=NORMAL` and WAL mode.

If you still hit issues, lower `MAX_FEED_ROWS` in `config.yaml` from 200 to
50, and lower `THUMB_GRID_COLS` from 4 to 3.

## I2C address conflict / Grove not detected at 0x62

If you've added other Grove I2C peripherals to the chain, scan for conflicts:

```cpp
// In Arduino sketch:
#include <Wire.h>
void setup() { Wire.begin(); Serial.begin(115200); }
void loop() {
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf("Found 0x%02X\n", a);
  }
  delay(2000);
}
```

Grove Vision AI V2 default address is `0x62`. If something else uses that,
either remove it or move it via its config.
