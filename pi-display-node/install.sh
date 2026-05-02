#!/usr/bin/env bash
# install.sh — one-shot installer for the wildlife-watcher display node.
# Run as root on a fresh Raspberry Pi OS Lite (Bookworm, 64-bit).

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_USER="${SUDO_USER:-pi}"

echo "==> wildlife-watcher installer (target user: $INSTALL_USER)"

# ---------------------------------------------------------------------------
# Prompt for broker credentials and WiFi info
# ---------------------------------------------------------------------------
read -rp "Mosquitto broker username [wildlife]: " BROKER_USER
BROKER_USER="${BROKER_USER:-wildlife}"
read -rsp "Mosquitto broker password: " BROKER_PASS
echo
if [[ -z "$BROKER_PASS" ]]; then
    echo "Password cannot be empty." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
echo "==> Creating directories"
install -d -m 755 /opt/wildlife
install -d -m 755 /opt/wildlife/kiosk
install -d -m 755 -o "$INSTALL_USER" -g "$INSTALL_USER" /var/lib/wildlife
install -d -m 755 -o "$INSTALL_USER" -g "$INSTALL_USER" /var/lib/wildlife/thumbs
install -d -m 755 /etc/wildlife

# ---------------------------------------------------------------------------
# Mosquitto
# ---------------------------------------------------------------------------
echo "==> Configuring Mosquitto"
install -m 644 "$SCRIPT_DIR/mosquitto/wildlife.conf" /etc/mosquitto/conf.d/wildlife.conf

# Create passwd file
PASSWD_FILE=/etc/mosquitto/wildlife.passwd
mosquitto_passwd -c -b "$PASSWD_FILE" "$BROKER_USER" "$BROKER_PASS"
chown mosquitto:mosquitto "$PASSWD_FILE"
chmod 600 "$PASSWD_FILE"

systemctl enable mosquitto
systemctl restart mosquitto
sleep 1
systemctl is-active --quiet mosquitto || {
    echo "Mosquitto failed to start. Check: journalctl -u mosquitto" >&2
    exit 1
}
echo "    Mosquitto active on port 1883"

# ---------------------------------------------------------------------------
# Python venv + kiosk app
# ---------------------------------------------------------------------------
echo "==> Setting up Python environment"
python3 -m venv --system-site-packages /opt/wildlife/venv
# --system-site-packages so we use the apt-installed PyQt5 (much faster on
# Pi Zero 2 W than building it in pip)
/opt/wildlife/venv/bin/pip install --upgrade pip wheel >/dev/null
/opt/wildlife/venv/bin/pip install -r "$SCRIPT_DIR/kiosk/requirements.txt"

install -m 644 "$SCRIPT_DIR/kiosk/wildlife_kiosk.py" /opt/wildlife/kiosk/
install -m 644 "$SCRIPT_DIR/kiosk/config.yaml" /etc/wildlife/config.yaml

# Substitute broker credentials into the config
sed -i "s|__BROKER_USER__|$BROKER_USER|g" /etc/wildlife/config.yaml
sed -i "s|__BROKER_PASS__|$BROKER_PASS|g" /etc/wildlife/config.yaml

chown -R "$INSTALL_USER:$INSTALL_USER" /opt/wildlife
chmod 600 /etc/wildlife/config.yaml
chown "$INSTALL_USER:$INSTALL_USER" /etc/wildlife/config.yaml

# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------
echo "==> Initializing SQLite database"
DB=/var/lib/wildlife/observations.db
if [[ ! -f "$DB" ]]; then
    sudo -u "$INSTALL_USER" sqlite3 "$DB" < "$SCRIPT_DIR/../schema/observations.sql"
    echo "    Created $DB"
else
    echo "    $DB already exists, skipping"
fi

# ---------------------------------------------------------------------------
# systemd: kiosk service
# ---------------------------------------------------------------------------
echo "==> Installing systemd unit"
install -m 644 "$SCRIPT_DIR/systemd/wildlife-kiosk.service" \
    /etc/systemd/system/wildlife-kiosk.service
sed -i "s|__INSTALL_USER__|$INSTALL_USER|g" /etc/systemd/system/wildlife-kiosk.service

systemctl daemon-reload
systemctl enable wildlife-kiosk.service

# ---------------------------------------------------------------------------
# Auto-login to console + start X with kiosk on boot
# ---------------------------------------------------------------------------
echo "==> Configuring auto-login + X startup for kiosk"
raspi-config nonint do_boot_behaviour B2  # console autologin

# .xinitrc launches matchbox + kiosk
cat > "/home/$INSTALL_USER/.xinitrc" <<'EOF'
#!/bin/sh
xset -dpms
xset s off
xset s noblank
unclutter -idle 0.1 -root &
matchbox-window-manager -use_titlebar no &
exec /opt/wildlife/venv/bin/python /opt/wildlife/kiosk/wildlife_kiosk.py
EOF
chmod +x "/home/$INSTALL_USER/.xinitrc"
chown "$INSTALL_USER:$INSTALL_USER" "/home/$INSTALL_USER/.xinitrc"

# .bash_profile: auto-startx on tty1
PROFILE="/home/$INSTALL_USER/.bash_profile"
if ! grep -q "startx" "$PROFILE" 2>/dev/null; then
    cat >> "$PROFILE" <<'EOF'

# Auto-start kiosk on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor
fi
EOF
    chown "$INSTALL_USER:$INSTALL_USER" "$PROFILE"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
echo "==> Installation complete."
echo
echo "    Broker:   mqtt://${BROKER_USER}@$(hostname -I | awk '{print $1}'):1883"
echo "    Kiosk:    will start on next reboot (auto-login on tty1)"
echo "    Config:   /etc/wildlife/config.yaml"
echo "    DB:       /var/lib/wildlife/observations.db"
echo "    Logs:     journalctl -u wildlife-kiosk -f"
echo
echo "    Reboot now: sudo reboot"
