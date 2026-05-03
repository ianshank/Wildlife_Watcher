"""Read serial output from the XIAO ESP32S3 on COM12 for ~15 seconds."""
from __future__ import annotations

import os
import sys
import time

import serial  # type: ignore

PORT = os.environ.get("XIAO_PORT", "COM12")
BAUD = int(os.environ.get("XIAO_BAUD", "115200"))
DUR = int(os.environ.get("XIAO_READ_SECS", "15"))

def main() -> int:
    try:
        s = serial.Serial(PORT, BAUD, timeout=0.2)
    except Exception as exc:
        print(f"open failed: {exc}")
        return 1
    print(f"reading {DUR}s from {PORT}@{BAUD} ...", flush=True)
    deadline = time.time() + DUR
    while time.time() < deadline:
        try:
            chunk = s.read(4096)
        except Exception as exc:
            print(f"\n[read error: {exc}]", flush=True)
            time.sleep(0.5)
            continue
        if chunk:
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
    s.close()
    print("\n---END---")
    return 0

if __name__ == "__main__":
    sys.exit(main())
