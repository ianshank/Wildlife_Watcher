r"""End-to-end live user-journey validation for the Wildlife Watcher pipeline.

What it proves, top to bottom, against the *actual* deployed system:

  Step 1 (camera presence):
    the real XIAO ESP32S3 is on the LAN and publishing wildlife/status/<node>
    messages that mosquitto can see.

  Step 2 (broker round-trip — synthetic camera):
    publish a synthetic detection JSON (and optionally a synthetic JPEG
    thumbnail) to the live mosquitto broker on the Pi from this dev box,
    impersonating a camera node. This proves the broker accepts
    authenticated publishes on the production topics, independent of any
    hardware quirks (e.g. Grove Vision AI V2 thumbnail issues).

  Step 3 (kiosk ingest):
    SSH into the Pi and query observations.db via sudo. The synthetic frame_id
    is unique per run, so finding it in the DB proves the running kiosk
    process consumed our injected MQTT message, parsed it, and persisted it.

  Step 4 (thumbnail attachment):
    if a thumbnail was injected, verify the row's thumb_jpeg column is the
    exact bytes we sent (round-trip identity through MQTT + base64 +
    Storage.update_thumb).

Exit code 0 only if every step passes. Anything else is a real regression.

Credentials are loaded from environment variables via _pi_creds; the broker
user/password come from MQTT_USER / MQTT_PASS (defaults match the deployed
broker for convenience but no secrets are hard-coded in this file).

Usage (PowerShell):
    $env:PI_PASS = '<pi-ssh-password>'
    $env:MQTT_PASS = '<broker-password>'
    .\.venv\Scripts\python.exe scripts/verify_e2e_journey.py
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import shlex
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt_client  # type: ignore  # noqa: F401  (kept for type-only references)
import paramiko  # type: ignore
from _mqtt_client import make_client as _make_mqtt_client
from _pi_creds import load as _load_creds
from _ssh_client import build_ssh_client
from _ssh_client import connect as _ssh_connect

# Smallest valid JPEG (1x1 white pixel). Sourced verbatim from the kiosk's
# own test fixture (pi-display-node/tests/test_thumb_cache.py::VALID_JPEG) so
# QImage / QPixmap on the Pi will accept it without quirks.
VALID_JPEG_1X1 = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
    b"\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
    b"\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xdb\x00C\x01\t\t\t\x0c\x0b\x0c\x18\r\r\x182!\x1c!22222222222222"
    b"22222222222222222222222222222222222222"
    b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\"\x00\x02\x11\x01\x03"
    b"\x11\x01"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04"
    b"\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q"
    b"\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18"
    b"\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
    b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4"
    b"\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2"
    b"\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda"
    b"\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7"
    b"\xf8\xf9\xfa"
    b"\xff\xc4\x00\x1f\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04"
    b"\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13\"2"
    b"\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0\x15br\xd1\n\x16$4\xe1%\xf1"
    b"\x17\x18\x19\x1a&'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83"
    b"\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2"
    b"\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba"
    b"\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9"
    b"\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8"
    b"\xf9\xfa"
    b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xfd\xfc\xa8"
    b"\xff\xd9"
)


def _say(label: str, msg: str) -> None:
    print(f"[{label}] {msg}", flush=True)


def _fail(label: str, msg: str) -> RuntimeError:
    _say(label, f"FAIL: {msg}")
    return RuntimeError(f"{label}: {msg}")


# ---------------------------------------------------------------------------
# Step 1 — real camera is on the air
# ---------------------------------------------------------------------------

def step1_camera_alive(broker: str, port: int, user: str, pw: str, node_id: str,
                        timeout_s: int = 10) -> bool:
    """Subscribe briefly and confirm we see a status from the *real* camera."""
    _say("step1", f"watching wildlife/status/+ for {timeout_s}s "
                  f"(expecting {node_id})")
    seen: dict[str, Any] = {}

    def _on_msg(_c: Any, _u: Any, m: Any) -> None:
        try:
            payload = json.loads(m.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": m.payload[:80].decode("utf-8", "replace")}
        seen[m.topic] = payload

    cli = _make_mqtt_client(f"e2e-watcher-{secrets.token_hex(4)}")
    cli.username_pw_set(user, pw)
    cli.on_message = _on_msg
    cli.connect(broker, port, keepalive=15)
    cli.subscribe("wildlife/status/+", qos=0)
    cli.loop_start()
    deadline = time.time() + timeout_s
    target_topic = f"wildlife/status/{node_id}"
    try:
        while time.time() < deadline and target_topic not in seen:
            time.sleep(0.2)
    finally:
        cli.loop_stop()
        cli.disconnect()
    if target_topic in seen:
        _say("step1", f"OK saw {target_topic} payload={seen[target_topic]}")
        return True
    _say("step1", f"WARN no message on {target_topic} within {timeout_s}s "
                  f"(other topics seen: {list(seen)})")
    return False


# ---------------------------------------------------------------------------
# Step 2 — synthetic camera publish
# ---------------------------------------------------------------------------

@dataclass
class InjectedFrame:
    node_id: str
    frame_id: str
    ts: str
    class_name: str
    class_id: int
    confidence: float
    bbox: tuple[int, int, int, int]
    thumb: bytes | None


def step2_inject(broker: str, port: int, user: str, pw: str,
                 with_thumb: bool) -> InjectedFrame:
    node_id = "e2e-test-cam"
    frame_id = f"e2e_{uuid.uuid4().hex[:10]}"
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    frame = InjectedFrame(
        node_id=node_id,
        frame_id=frame_id,
        ts=ts,
        class_name="bird",
        class_id=0,
        confidence=0.91,
        bbox=(10, 20, 30, 40),
        thumb=VALID_JPEG_1X1 if with_thumb else None,
    )
    payload = {
        "ts": ts,
        "node_id": node_id,
        "frame_id": frame_id,
        "model": "e2e-synthetic",
        "fps": 1.0,
        "detections": [{
            "class_id": frame.class_id,
            "class_name": frame.class_name,
            "confidence": frame.confidence,
            "bbox": list(frame.bbox),
        }],
    }
    cli = _make_mqtt_client(f"e2e-cam-{secrets.token_hex(4)}")
    cli.username_pw_set(user, pw)
    cli.connect(broker, port, keepalive=15)
    cli.loop_start()
    try:
        det_topic = f"wildlife/detections/{node_id}"
        det_info = cli.publish(det_topic, json.dumps(payload).encode("utf-8"),
                               qos=1, retain=False)
        det_info.wait_for_publish(timeout=5)
        _say("step2", f"published {det_topic} frame_id={frame_id} "
                      f"rc={det_info.rc}")
        if frame.thumb is not None:
            # Brief gap so the kiosk's MQTT thread is overwhelmingly
            # likely to enqueue the detection row before the retained
            # thumb arrives. step3_4 also polls/retries in case of any
            # residual reordering, so this is belt-and-braces.
            time.sleep(0.25)
            thumb_topic = f"wildlife/thumbs/{node_id}/{frame_id}"
            b64 = base64.b64encode(frame.thumb)
            t_info = cli.publish(thumb_topic, b64, qos=0, retain=True)
            t_info.wait_for_publish(timeout=5)
            _say("step2", f"published {thumb_topic} ({len(frame.thumb)} raw "
                          f"bytes -> {len(b64)} b64) rc={t_info.rc}")
    finally:
        cli.loop_stop()
        cli.disconnect()
    return frame


# ---------------------------------------------------------------------------
# Step 3 + 4 — confirm row landed in observations.db on the Pi
# ---------------------------------------------------------------------------

def _ssh(host: str, user: str, pw: str) -> paramiko.SSHClient:
    cli = build_ssh_client()
    _ssh_connect(cli, host, user, pw, timeout=15)
    return cli


def _sudo_exec(cli: paramiko.SSHClient, cmd: str, sudo_pw: str,
               timeout: int = 20) -> tuple[int, str, str]:
    """Run cmd via sudo -S using a PTY so we can stuff the password in."""
    chan = cli.get_transport().open_session()  # type: ignore[union-attr]
    chan.get_pty()
    chan.settimeout(timeout)
    # shlex.quote handles every shell metachar correctly; do NOT hand-roll.
    chan.exec_command(f"sudo -S -p '' bash -c {shlex.quote(cmd)}")
    chan.send(sudo_pw + "\n")
    out: list[str] = []
    err: list[str] = []
    while True:
        if chan.recv_ready():
            out.append(chan.recv(65536).decode("utf-8", "replace"))
        if chan.recv_stderr_ready():
            err.append(chan.recv_stderr(65536).decode("utf-8", "replace"))
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    rc = chan.recv_exit_status()
    return rc, "".join(out), "".join(err)


def step3_4_verify_db(host: str, user: str, pw: str,
                      frame: InjectedFrame, settle_s: int = 3,
                      poll_s: int = 12, poll_interval_s: float = 1.0) -> None:
    """Confirm the kiosk persisted both the detection row and the thumbnail.

    The kiosk processes detection and thumbnail messages from the same MQTT
    queue but in receive order, and ``Storage.update_thumb()`` is a no-op
    when the row does not yet exist. Rather than racing on a single read,
    poll the DB for up to ``poll_s`` seconds: success requires the
    detection row to land *and* (when a thumb was injected) the
    ``thumb_jpeg`` column to reach byte-identity with what we published.
    """
    _say("step3", f"settling {settle_s}s before first poll ...")
    time.sleep(settle_s)
    cli = _ssh(host, user, pw)
    try:
        # Query the row by (node_id, frame_id). Output is pipe-separated; the
        # last field is hex-encoded thumb_jpeg or empty.
        sql = (
            "SELECT ts, node_id, frame_id, class_name, class_id, confidence, "
            "bbox_x, bbox_y, bbox_w, bbox_h, model, fps, "
            "IFNULL(hex(thumb_jpeg), '') "
            f"FROM observations WHERE node_id='{frame.node_id}' "
            f"AND frame_id='{frame.frame_id}';"
        )
        cmd = (
            f'sqlite3 -separator "|" /var/lib/wildlife/observations.db "{sql}"'
        )

        deadline = time.monotonic() + poll_s
        last_err: str = ""
        cols: list[str] = []
        while time.monotonic() < deadline:
            rc, out, err = _sudo_exec(cli, cmd, pw)
            if rc != 0:
                last_err = f"sqlite3 rc={rc} stderr={err.strip()}"
                time.sleep(poll_interval_s)
                continue
            line = out.strip().splitlines()[-1] if out.strip() else ""
            if not line or "|" not in line:
                last_err = f"no row yet for frame_id={frame.frame_id}"
                time.sleep(poll_interval_s)
                continue
            cols = line.split("|")
            if len(cols) < 13:
                last_err = f"unexpected row shape: {cols}"
                time.sleep(poll_interval_s)
                continue
            db_thumb_hex = cols[12]
            # If we expected a thumb, wait for it to be populated too.
            if frame.thumb is not None and not db_thumb_hex:
                last_err = "row present but thumb_jpeg still NULL"
                time.sleep(poll_interval_s)
                continue
            break
        else:
            raise _fail("step3", f"polled {poll_s}s, last error: {last_err}")

        (db_ts, db_node, db_frame, db_class, db_cid, db_conf,
         db_x, db_y, db_w, db_h, db_model, db_fps, db_thumb_hex) = cols[:13]

        # Step 3: detection-row content
        checks = [
            ("node_id",    db_node,            frame.node_id),
            ("frame_id",   db_frame,           frame.frame_id),
            ("class_name", db_class,           frame.class_name),
            ("class_id",   int(db_cid),        frame.class_id),
            ("confidence", round(float(db_conf), 3), round(frame.confidence, 3)),
            ("bbox_x",     int(db_x),          frame.bbox[0]),
            ("bbox_y",     int(db_y),          frame.bbox[1]),
            ("bbox_w",     int(db_w),          frame.bbox[2]),
            ("bbox_h",     int(db_h),          frame.bbox[3]),
            ("model",      db_model,           "e2e-synthetic"),
        ]
        for name, got, want in checks:
            if got != want:
                raise _fail("step3", f"{name} got={got!r} want={want!r}")
        _say("step3", f"OK observation row matches injected payload "
                      f"(ts={db_ts}, fps={db_fps})")

        # Step 4: thumbnail bytes (only if we sent one)
        if frame.thumb is not None:
            db_thumb = bytes.fromhex(db_thumb_hex) if db_thumb_hex else b""
            if not db_thumb:
                raise _fail("step4", "thumb_jpeg column is empty in DB")
            if db_thumb != frame.thumb:
                raise _fail(
                    "step4",
                    f"thumb mismatch: db {len(db_thumb)}B / sent "
                    f"{len(frame.thumb)}B"
                )
            _say("step4", f"OK thumb_jpeg round-trip identity "
                          f"({len(db_thumb)} bytes)")
        else:
            _say("step4", "skipped (no thumbnail injected)")
    finally:
        cli.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--broker", default=None,
                   help="MQTT broker host (default: PI_HOST)")
    p.add_argument("--mqtt-port", type=int,
                   default=int(os.environ.get("MQTT_PORT", "1883")))
    p.add_argument("--mqtt-user",
                   default=os.environ.get("MQTT_USER", "wildlife"))
    p.add_argument("--mqtt-pass",
                   default=os.environ.get("MQTT_PASS", ""),
                   help="broker password (env: MQTT_PASS, required)")
    p.add_argument("--camera-node-id", default="test-camera-1",
                   help="node_id of the real XIAO to look for in step 1")
    p.add_argument("--no-camera-check", action="store_true",
                   help="skip step 1 (don't require real camera on the air)")
    p.add_argument("--no-thumb", action="store_true",
                   help="skip thumbnail injection and step 4")
    p.add_argument("--settle", type=int, default=3,
                   help="seconds to wait for kiosk to ingest the publish")
    args = p.parse_args(argv)

    pi_host, pi_user, pi_pass = _load_creds()
    broker = args.broker or pi_host

    if not args.mqtt_pass:
        sys.stderr.write(
            "error: MQTT broker password is required. "
            "Set MQTT_PASS env var or pass --mqtt-pass.\n"
        )
        return 2

    print("=== Wildlife Watcher full-journey validation ===")
    print(f"  Pi host : {pi_host} (user={pi_user})")
    print(f"  Broker  : {broker}:{args.mqtt_port} (user={args.mqtt_user})")
    print(f"  Cam id  : {args.camera_node_id} "
          f"({'skipped' if args.no_camera_check else 'required'})")
    print(f"  Thumb   : {'skipped' if args.no_thumb else 'injected'}")
    print()

    failures: list[str] = []

    if not args.no_camera_check:
        try:
            ok = step1_camera_alive(broker, args.mqtt_port, args.mqtt_user,
                                    args.mqtt_pass, args.camera_node_id)
            if not ok:
                failures.append("step1: real camera not seen")
        except Exception as exc:
            _say("step1", f"ERROR {exc}")
            failures.append(f"step1: {exc}")

    try:
        frame = step2_inject(broker, args.mqtt_port, args.mqtt_user,
                             args.mqtt_pass, with_thumb=not args.no_thumb)
    except Exception as exc:
        _say("step2", f"ERROR {exc}")
        return 2

    try:
        step3_4_verify_db(pi_host, pi_user, pi_pass, frame,
                          settle_s=args.settle)
    except Exception as exc:
        failures.append(str(exc))

    print()
    if failures:
        print("=== FAILED ===")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
