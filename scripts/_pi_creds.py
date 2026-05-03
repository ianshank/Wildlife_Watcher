"""Shared Pi SSH credential loader for verify_pi_*.py scripts.

Reads from environment variables — never hard-codes secrets in the repo:
  PI_HOST  (default: "192.168.4.21")
  PI_USER  (default: "ian")
  PI_PASS  (required, no default)

Set them in your shell before running, e.g. in PowerShell:
    $env:PI_PASS = "<your-pi-password>"
or in bash:
    export PI_PASS="<your-pi-password>"
"""
from __future__ import annotations

import os
import sys


def load() -> tuple[str, str, str]:
    host = os.environ.get("PI_HOST", "192.168.4.21")
    user = os.environ.get("PI_USER", "ian")
    pw = os.environ.get("PI_PASS")
    if not pw:
        sys.stderr.write(
            "error: PI_PASS environment variable is required.\n"
            "  PowerShell:  $env:PI_PASS = '<password>'\n"
            "  bash:        export PI_PASS='<password>'\n"
        )
        sys.exit(2)
    return host, user, pw
