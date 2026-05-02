# 04 — End-to-End Bring-Up

This is the smoke test that proves Phase 1 is done. Run it after `01`, `02`,
and `03` are all complete.

## Test 1: Broker is up

On the Pi:

```bash
systemctl status mosquitto         # should be active (running)
systemctl status wildlife-kiosk    # should be active (running)
ss -tlnp | grep 1883               # should show mosquitto listening
```

## Test 2: Camera node connects

Power the camera node (Grove + XIAO). On any machine on the LAN:

```bash
mosquitto_sub -h wildlife-display.local -u wildlife -P <password> \
  -t 'wildlife/status/#' -v
```

Within 10 seconds you should see:

```
wildlife/status/feeder-01 {"state":"online","ip":"192.168.1.83","ts":"..."}
```

If the camera node is unplugged or loses WiFi, within ~30 seconds the LWT
fires and you'll see:

```
wildlife/status/feeder-01 {"state":"offline"}
```

## Test 3: Detections flow

Subscribe to detections:

```bash
mosquitto_sub -h wildlife-display.local -u wildlife -P <password> \
  -t 'wildlife/detections/#' -v
```

Aim the camera at something the deployed model recognizes (a person if you
flashed Person Detection; a printed bird image / phone screen with a bird
if you flashed YOLO-World-bird). You should see JSON events stream in.

## Test 4: Kiosk UI

Look at the Waveshare 7" screen on the Pi. The UI should show:

- **Header**: `Broker: connected · 1 node online: feeder-01`
- **Event feed (left)**: scrolling list of detections, newest at top, each
  with timestamp, class, confidence, and node name.
- **Thumbnail grid (right)**: most recent thumbnails, tap to expand.
- **Footer**: total observations today, event rate (events/min).

Tapping a thumbnail opens it full-screen with the bounding box overlaid.
Tapping again returns to the feed.

## Test 5: Persistence

Stop the kiosk, restart it, and confirm prior observations are still there:

```bash
sudo systemctl restart wildlife-kiosk
```

The event feed will repopulate from SQLite (last 200 events shown by default,
configurable in `config.yaml`).

Inspect the database:

```bash
sqlite3 /var/lib/wildlife/observations.db \
  "SELECT ts, node_id, class_name, confidence FROM observations \
   ORDER BY ts DESC LIMIT 20;"
```

## Test 6: Reboot survives

```bash
sudo reboot
```

After the Pi comes back, Mosquitto and the kiosk should auto-start. The
camera node should reconnect to WiFi and the broker. Detections should
resume without manual intervention.

## You're done with Phase 1 when

- [ ] Camera node publishes `online` status on boot.
- [ ] Camera node publishes `offline` status (via LWT) when powered off.
- [ ] Detections appear in the kiosk UI within ~500 ms of the camera seeing
      a target.
- [ ] Thumbnails display correctly in the kiosk grid.
- [ ] SQLite log retains observations across reboots.
- [ ] System recovers automatically from Pi reboot, camera node reboot, and
      transient WiFi outages.

## What's next

Phase 2 adds:

- HC-SR501 PIR sensor wired to a XIAO GPIO for wake-on-motion.
- XIAO deep sleep between PIR triggers.
- Battery + solar power option for the camera node.

Phase 3 adds:

- Custom YOLOv8n training on Caltech-UCSD Birds-200-2011 on an external workstation or cloud GPU.
- Vela compiler workflow for Ethos-U55 deployment.
- Species-level confusion matrix view in the kiosk UI.
- "Confirm species" touch interaction for crowdsourced labeling of new data.
