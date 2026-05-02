# 01 — Pi Zero 2 W Base Setup

Goal: a Pi Zero 2 W on your WiFi, with the Waveshare 7" touchscreen working,
running Mosquitto and the kiosk UI on boot.

## 1. Flash the SD card

Use Raspberry Pi Imager (>= v1.8). Pick:

- **Device**: Raspberry Pi Zero 2 W
- **OS**: Raspberry Pi OS Lite (64-bit, Bookworm). Do *not* use the Desktop
  variant — we don't need X11/Wayland and the Pi Zero 2 W will be much happier.

Click the gear icon and pre-configure:

- Hostname: `wildlife-display`
- SSH: enabled, public-key authentication
- Username/password: your choice (referred to below as `pi`)
- WiFi: your 2.4 GHz SSID + password (the Pi Zero 2 W only does 2.4 GHz anyway)
- Locale: your timezone

Boot the Pi, find it on the network (`ping wildlife-display.local` or check
your router), then SSH in.

## 2. Update and install base packages

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y \
    git python3-pip python3-venv \
    mosquitto mosquitto-clients \
    python3-pyqt5 python3-pyqt5.qtsvg \
    python3-paho-mqtt python3-yaml python3-pil \
    sqlite3 \
    xserver-xorg xinit x11-xserver-utils \
    matchbox-window-manager unclutter
sudo systemctl enable mosquitto
```

Why a minimal X server with matchbox? PyQt5 is by far the easiest way to build a
touch UI, and on the Pi Zero 2 W, X11 + matchbox + a single fullscreen window is
lighter than Wayland or a full desktop. We disable the cursor with `unclutter`
and run no compositor.

## 3. Configure the Waveshare 7" touchscreen

Follow Waveshare's wiki for the specific kit you have ("7inch DSI LCD (C)" or
similar) — most kits these days are plug-and-play on Bookworm via the DSI
ribbon, but a few still need a `dtoverlay` line in `/boot/firmware/config.txt`.
Edit the config file and add at the end if needed:

```
# /boot/firmware/config.txt
dtoverlay=vc4-kms-v3d
display_auto_detect=1
```

For the touch screen calibration, with Bookworm the DSI capacitive touch
panels generally Just Work. Validate with:

```bash
sudo apt install -y evtest
sudo evtest
# pick the touchscreen device, tap the screen, watch events
```

## 4. Drop this package onto the Pi

From your workstation:

```bash
scp -r wildlife-watcher-phase1 pi@wildlife-display.local:/home/pi/
```

Then on the Pi:

```bash
cd ~/wildlife-watcher-phase1/pi-display-node
chmod +x install.sh
sudo ./install.sh
```

The installer will:

1. Copy Mosquitto config + create the broker user.
2. Install Python deps for the kiosk into a venv at `/opt/wildlife/venv`.
3. Copy the kiosk app to `/opt/wildlife/`.
4. Initialize the SQLite database at `/var/lib/wildlife/observations.db`.
5. Install and enable the `wildlife-kiosk.service` systemd unit.
6. Set the kiosk to auto-start on boot via X.

It will prompt for:

- Mosquitto broker username
- Mosquitto broker password
- WiFi SSID (recorded for the camera node config — not used by the Pi itself)

## 5. Verify the broker is reachable

From the Pi:

```bash
mosquitto_sub -h localhost -u <broker_user> -P <broker_pass> \
  -t 'wildlife/#' -v
```

From another machine on the LAN:

```bash
mosquitto_pub -h wildlife-display.local -u <broker_user> -P <broker_pass> \
  -t 'wildlife/detections/test' \
  -m '{"ts":"2026-05-01T00:00:00Z","node_id":"test","detections":[]}'
```

You should see the message arrive on the subscriber. If not, see
`05-troubleshooting.md` § "MQTT not reachable from LAN".

## 6. Reboot and confirm kiosk starts

```bash
sudo reboot
```

After reboot, the touchscreen should show the kiosk UI with an empty event
feed and a status banner reading `Broker: connected · No camera nodes online`.

Next step: `02-grove-flashing.md`.
