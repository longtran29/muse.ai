"""Pull muse.ai session cookies out of a Chrome that is already logged in, via CDP.

Chrome must be started with a debugging port, e.g.:

    google-chrome --remote-debugging-port=9222

Then:

    python scripts/grab_cookies.py                 # print the cookie string
    python scripts/grab_cookies.py --import acc1   # also POST it to the gateway

CDP reads httpOnly cookies, which page JavaScript and document.cookie cannot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx
import websockets

CDP_HTTP = "http://127.0.0.1:9222"
GATEWAY = "http://127.0.0.1:18610"
WANTED_PREFIX = "hatch_"
REQUIRED = ("hatch_sess", "hatch_native_auth_device")


async def cookies_from_cdp(port_http: str) -> list[dict[str, Any]]:
    targets = httpx.get(f"{port_http}/json/list", timeout=10).json()
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    muse = [t for t in pages if "muse.ai" in (t.get("url") or "")]
    order = muse + pages
    last_error = "no page target found"
    for target in order:
        try:
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=32 << 20) as ws:
                await ws.send(json.dumps({
                    "id": 1, "method": "Network.enable", "params": {},
                }))
                await ws.send(json.dumps({
                    "id": 2, "method": "Network.getCookies",
                    "params": {"urls": ["https://muse.ai", "https://www.muse.ai"]},
                }))
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                    if msg.get("id") == 2:
                        found = (msg.get("result") or {}).get("cookies") or []
                        if found:
                            return found
                        last_error = "target has no muse.ai cookies (is it logged in?)"
                        break
        except Exception as exc:  # noqa: BLE001 - diagnostics
            last_error = f"{type(exc).__name__}: {exc}"
    raise SystemExit(f"could not read cookies: {last_error}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cdp", default=CDP_HTTP, help="CDP http endpoint (default 127.0.0.1:9222)")
    ap.add_argument("--gateway", default=GATEWAY, help="gateway base URL")
    ap.add_argument("--admin-key", default="", help="admin key; default read from data/api_key")
    ap.add_argument("--import", dest="label", default="", help="label to import into the gateway")
    args = ap.parse_args()

    cookies = asyncio.run(cookies_from_cdp(args.cdp))
    picked = {c["name"]: c["value"] for c in cookies if c["name"].startswith(WANTED_PREFIX)}
    expires = {c["name"]: int(c.get("expires") or 0) for c in cookies
               if c["name"] in picked and (c.get("expires") or 0) > 0}
    for name in REQUIRED:
        if not picked.get(name):
            print(f"missing required cookie: {name}", file=sys.stderr)
            print(f"found {WANTED_PREFIX}* cookies: {sorted(picked)}", file=sys.stderr)
            return 1

    header = "; ".join(f"{k}={v}" for k, v in picked.items())
    print(header)

    if not args.label:
        return 0

    key = args.admin_key
    if not key:
        try:
            from pathlib import Path
            key = Path("data/api_key").read_text().strip()
        except OSError:
            print("no --admin-key and no data/api_key", file=sys.stderr)
            return 1
    resp = httpx.post(
        f"{args.gateway}/admin/accounts",
        headers={"Authorization": f"Bearer {key}"},
        json={"label": args.label, "cookies": picked, "cookie_expires": expires},
        timeout=30,
    )
    print(f"import -> {resp.status_code} {resp.text}")
    return 0 if resp.status_code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
