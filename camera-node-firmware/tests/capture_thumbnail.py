"""Capture a single JPEG thumbnail and show detections from the camera node via MQTT."""

# pyright: reportMissingTypeStubs=false
import asyncio
import base64
import json
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt  # type: ignore # pyright: ignore[reportMissingTypeStubs]

BROKER = os.environ.get("MQTT_BROKER", "192.168.4.30")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
NODE_ID = os.environ.get("NODE_ID", "test-camera-1")
OUTPUT = sys.argv[1] if len(sys.argv) > 1 else "capture.jpg"


def run_broker(loop, started):
    asyncio.set_event_loop(loop)

    async def start():
        from amqtt.broker import Broker

        config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{BROKER}:{PORT}",
                    "max_connections": 50,
                },
            },
            "sys_interval": 0,
            "auth": {
                "allow-anonymous": True,
                "plugins": ["auth_anonymous"],
            },
        }
        b = Broker(config)
        await b.start()
        started.set()
        while True:
            await asyncio.sleep(1)

    loop.run_until_complete(start())


# Start the embedded broker
loop = asyncio.new_event_loop()
started = threading.Event()
t = threading.Thread(target=run_broker, args=(loop, started), daemon=True)
t.start()
if not started.wait(10):
    print("Broker failed to start")
    sys.exit(1)
print(f"[capture] Broker ready on {BROKER}:{PORT}")

captured = False
det_count = 0


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(f"wildlife/#")
        print(f"[capture] Connected to MQTT broker (rc={rc}), waiting for data from {NODE_ID}...")
    else:
        print(f"[capture] Connection failed: {rc}")


def on_message(client, userdata, msg):
    global captured, det_count
    if captured:
        return

    if msg.topic.startswith("wildlife/status/"):
        try:
            p = json.loads(msg.payload)
            print(
                f"  [Status] IP={p.get('ip')}, State={p.get('state')}, Uptime={p.get('uptime_ms')}ms"
            )
        except Exception:
            pass
    elif msg.topic.startswith("wildlife/detections/"):
        try:
            p = json.loads(msg.payload)
            det_count += 1
            n = len(p.get("detections", []))
            print(
                f"  [Detection #{det_count}] {n} object(s), "
                f"fps={p.get('fps', '?')}, frame={p.get('frame_id', '?')}"
            )
        except Exception:
            pass
    elif msg.topic.startswith(f"wildlife/thumbs/{NODE_ID}/"):
        payload = bytes(msg.payload)
        try:
            jpeg_bytes = base64.b64decode(payload, validate=True)
        except Exception:
            jpeg_bytes = payload

        if jpeg_bytes.startswith(b"\xff\xd8\xff"):
            from pathlib import Path

            with Path(OUTPUT).open("wb") as f:
                f.write(jpeg_bytes)
            print(f"[capture] SUCCESS! Saved {len(jpeg_bytes)} bytes to {OUTPUT}")
            captured = True
            client.disconnect()
        else:
            print(f"[capture] Got payload but not JPEG ({len(jpeg_bytes)} bytes)")


client = mqtt.Client(client_id="capture-tool", clean_session=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)

start = time.time()
client.loop_start()

while not captured and time.time() - start < 120:
    time.sleep(0.5)

client.loop_stop()

if not captured:
    print(f"[capture] Timeout — received {det_count} detections but no thumbnail in 120s.")
    print("          Make sure the camera can see something detectable.")
    sys.exit(1)
