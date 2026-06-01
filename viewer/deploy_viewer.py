#!/usr/bin/env python3
"""Rebuild viewer/worker.js from the wiki and redeploy the Cloudflare Worker.

This keeps the live viewer in sync with the wiki. The worker is a static bake
(node-free, and the wiki lives in a private repo the worker cannot read at
request time), so "always reflects the wiki" means: rebuild and redeploy
whenever the wiki changes. The daily lint calls this after it folds in new
sources; you can also run it by hand after editing the wiki.

Secrets are never hardcoded:
  - The Cloudflare API token is read from CF_API_TOKEN. If it is absent the
    script refuses to deploy (so it is a safe no-op in environments without
    Cloudflare access).
  - The viewer is public by site owner request. This deploy does not attach
    VIEWER_USER / VIEWER_PASS bindings.

Usage:
    CF_API_TOKEN=... python3 viewer/deploy_viewer.py
    CF_API_TOKEN=... python3 viewer/deploy_viewer.py --skip-build   # reuse worker.js

Env:
    CF_API_TOKEN        (required) Cloudflare token with Workers Scripts:Edit
    CF_ACCOUNT_ID       default 48e57a851f7eb0ffe06570f14f317428
    VIEWER_WORKER       default intelligence-layer-prototype-claude
    VIEWER_COMPAT_DATE  default 2025-01-01
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER_JS = HERE / "worker.js"
BUILD = HERE / "build_viewer.py"

ACCOUNT = os.environ.get("CF_ACCOUNT_ID", "48e57a851f7eb0ffe06570f14f317428")
WORKER = os.environ.get("VIEWER_WORKER", "intelligence-layer-prototype-claude")
COMPAT = os.environ.get("VIEWER_COMPAT_DATE", "2025-01-01")


def build():
    subprocess.run([sys.executable, str(BUILD)], check=True)


def _multipart(metadata_bytes, script_bytes):
    boundary = "----ilpviewer" + os.urandom(8).hex()
    b = boundary.encode()
    crlf = b"\r\n"
    chunks = [
        b"--", b, crlf,
        b'Content-Disposition: form-data; name="metadata"', crlf,
        b"Content-Type: application/json", crlf, crlf,
        metadata_bytes, crlf,
        b"--", b, crlf,
        b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"', crlf,
        b"Content-Type: application/javascript+module", crlf, crlf,
        script_bytes, crlf,
        b"--", b, b"--", crlf,
    ]
    return boundary, b"".join(chunks)


def deploy(token):
    metadata = json.dumps({
        "main_module": "worker.js",
        "compatibility_date": COMPAT,
        "bindings": [],
    }).encode()
    boundary, body = _multipart(metadata, WORKER_JS.read_bytes())
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/workers/scripts/{WORKER}"
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # Surface the API error body, never the token.
        try:
            return json.loads(e.read())
        except Exception:
            return {"success": False, "errors": [{"message": f"HTTP {e.code}"}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true",
                    help="deploy the existing worker.js without rebuilding")
    args = ap.parse_args()

    token = os.environ.get("CF_API_TOKEN")
    if not token:
        sys.exit("CF_API_TOKEN not set; refusing to deploy. "
                 "Set it in the routine env to enable viewer auto-deploy.")
    if not args.skip_build:
        build()
    if not WORKER_JS.exists():
        sys.exit(f"missing {WORKER_JS}; run build_viewer.py first")

    data = deploy(token)
    if not data.get("success"):
        sys.exit(f"deploy failed: {data.get('errors')}")
    print(f"viewer redeployed: {WORKER} ({WORKER_JS.stat().st_size} bytes) "
          f"modified {data.get('result', {}).get('modified_on')}")


if __name__ == "__main__":
    main()
