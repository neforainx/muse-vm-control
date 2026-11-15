#!/usr/bin/env python3
"""Launcher browser sederhana untuk stack bridge (display dari env DISPLAY).

- profil persisten ~/workspace/tools/vm-browser/profile (sesi login di
  dalamnya utuh antar peluncuran);
- ukuran jendela/viewport 1280x800 mengikuti geometri Xtigervnc.

Proxy opsional dari env VM_BROWSER_PROXY (kosong = tanpa proxy).
Membuka URL argumen pertama, menyimpan screenshot bukti ke
vnc-ctrl/last-screenshot.png, lalu TETAP TERBUKA sampai SIGTERM/SIGINT
(ditutup bersih lewat ctx.close()).
"""
import signal
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
PROFILE = Path.home() / "workspace/tools/vm-browser/profile"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"

stop = False


def _sigterm(_sig, _frm):
    global stop
    stop = True


signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)

with sync_playwright() as p:
    import os
    _proxy = os.environ.get("VM_BROWSER_PROXY") or None
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE),
        headless=False,
        proxy={"server": _proxy} if _proxy else None,
        args=["--no-sandbox", "--window-size=1280,800", "--no-first-run"],
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    # Navigasi dibuat tahan lambat: rute lewat proxy bisa
    # 20+ dtk per lompatan dan VM berbagi CPU — timeout 180 dtk, sampai 3
    # percobaan, dan kegagalan navigasi TIDAK membunuh browser (tetap parkir
    # supaya bisa dinavigasikan ulang lewat input VNC).
    last_err = None
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=180000)
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"NAV attempt {attempt + 1} gagal: {e}", flush=True)
            page.wait_for_timeout(3000)
    if last_err is not None:
        print(f"NAV-FAILED url={page.url}", flush=True)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(BASE / "last-screenshot.png"))
    print(f"READY title={page.title()!r} url={page.url}", flush=True)
    while not stop:
        time.sleep(1)
    ctx.close()
print("CLOSED", flush=True)
