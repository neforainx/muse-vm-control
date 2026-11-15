"""Browser VM di display VNC :98 — Chromium (Playwright) + server kendali.

Chromium pasangan dari protokol server kendali vm-browser (perintah,
bentuk balasan, perilaku tab/popup/ensure_page ditiru persis), mesinnya
Chromium biasa yang dikendalikan Playwright pada display VNC, dengan
profil persisten sehingga sesi login di dalamnya TIDAK perlu login
ulang setiap peluncuran. Parameter launch: profil persisten
~/workspace/tools/vm-browser/profile, proxy opsional dari env
VM_BROWSER_PROXY, viewport/jendela 1280x800 mengikuti geometri VNC,
navigasi awal tahan lambat.

- Chromium memakai ignore_https_errors=True + toko sertifikat sistem.
- Bila modul stealth opsional tersedia (env VM_STEALTH_DIR menunjuk ke
  folder berisi stealth.py dengan launch_stealth), peluncuran memakai
  mesin stealth itu; bila tidak, Chromium polos dipakai — protokol
  kendalinya identik.

SERVER KENDALI: server TCP JSON di 127.0.0.1:8081.
Satu perintah JSON per baris, satu jawaban JSON per baris. Perintah:
  {"cmd":"status"}            -> {"ok":true,"url":..,"title":..}
  {"cmd":"screenshot"}        -> {"ok":true,"image":"<base64 jpeg>","width":..,"height":..}
  {"cmd":"click","x":N,"y":N} -> {"ok":true}  (opsi "button":"left|right|middle", "click_count":N)
  {"cmd":"rightclick","x":N,"y":N} -> {"ok":true}  (klik kanan; untuk gestur double-tap artifak)
  {"cmd":"dblclick","x":N,"y":N} -> {"ok":true}  (klik ganda tombol kiri)
  {"cmd":"move","x":N,"y":N}  -> {"ok":true}  (gerakkan mouse tanpa klik, untuk hover + posisi kursor)
  {"cmd":"type","text":".."}  -> {"ok":true}
  {"cmd":"key","key":"Enter"} -> {"ok":true}
  {"cmd":"scroll","dy":N}     -> {"ok":true}
  {"cmd":"goto","url":".."}   -> {"ok":true,"url":..,"title":..}
  {"cmd":"back"}              -> {"ok":true,"url":..,"title":..}  (riwayat mundur; untuk bilah browser artifak)
  {"cmd":"forward"}           -> {"ok":true,"url":..,"title":..}  (riwayat maju)
  {"cmd":"reload"}            -> {"ok":true,"url":..,"title":..}  (muat ulang halaman)
  {"cmd":"activeelement"}     -> {"ok":true,"editable":bool,"tag":..,"type":..}  (elemen yang sedang fokus di halaman; supaya artifak tahu ketukan mendarat di kolom isian -> keyboard HP boleh muncul, atau bukan -> keyboard tetap sembunyi)
  {"cmd":"tabs"}              -> {"ok":true,"tabs":[{"id":N,"url":..,"title":..,"active":bool}]}  (semua tab di konteks browser — strip tab seperti browser bawaan Muse pada contoh pemilik)
  {"cmd":"newtab"}            -> {"ok":true,"id":N,"tabs":[..]}  (tab baru kosong, langsung aktif)
  {"cmd":"switchtab","id":N}  -> {"ok":true,"id":N,"url":..,"title":..}  (pindah tab aktif)
  {"cmd":"closetab","id":N}   -> {"ok":true,"tabs":[..]}  (tutup tab; tab terakhir ditutup -> tab kosong baru)
Popup dari halaman aktif (mis. jendela masuk Google dari tombol
"Continue with Google") otomatis jadi tab aktif, seperti browser biasa.
Hanya localhost. Artifak Space bicara ke server ini lewat socket TCP
mentah (pola yang sama seperti Pengendali VNC).

Penutupan bersih: SIGTERM/SIGINT menutup konteks Chromium lewat
ctx.close() (pola browser-98.py), supaya profil tidak tertinggal terkunci.
"""
import asyncio
import base64
import json
import signal
import sys
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = Path.home() / "workspace/tools/vm-browser/profile"
START_URL = (sys.argv[1] if len(sys.argv) > 1
             else "https://example.com/")
# Proxy keluar opsional, mis. VM_BROWSER_PROXY=http://127.0.0.1:8080
# untuk pintu keluar ber-IP tetap. Kosong = tanpa proxy.
PROXY = __import__("os").environ.get("VM_BROWSER_PROXY") or None
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8081

PAGE = None  # halaman (tab) aktif; diisi main() sesudah halaman dibuat
CONTEXT = None  # konteks browser; diisi main(), dipakai perintah tab
_HUMANIZER_MOD = None  # modul humanize opsional; dimuat malas oleh hclick
TAB_IDS = {}  # id(objek page) -> nomor tab stabil untuk klien
NEXT_TAB_ID = 1


def tab_id(page) -> int:
    """Nomor tab stabil selama halaman hidup (untuk switchtab/closetab)."""
    global NEXT_TAB_ID
    key = id(page)
    if key not in TAB_IDS:
        TAB_IDS[key] = NEXT_TAB_ID
        NEXT_TAB_ID += 1
    return TAB_IDS[key]


async def page_title(page) -> str:
    """Judul halaman dengan batas waktu — halaman yang sedang memuat
    tidak boleh menggantung perintah tabs."""
    try:
        return await asyncio.wait_for(page.title(), timeout=2.5)
    except Exception:  # noqa: BLE001
        return ""


async def tabs_payload() -> list:
    """Daftar tab terbuka: id, url, judul, dan mana yang aktif."""
    pages = list(CONTEXT.pages) if CONTEXT is not None else (
        [PAGE] if PAGE is not None else [])
    live = {id(p) for p in pages}
    for key in list(TAB_IDS.keys()):
        if key not in live:
            del TAB_IDS[key]
    tabs = []
    for p in pages:
        tabs.append({
            "id": tab_id(p),
            "url": p.url,
            "title": await page_title(p),
            "active": p is PAGE,
        })
    return tabs


async def activate(page) -> None:
    """Jadikan halaman sebagai tab aktif (yang dilihat/diklik artifak)."""
    global PAGE
    PAGE = page
    try:
        await page.bring_to_front()
    except Exception:  # noqa: BLE001 - halaman mungkin baru lahir
        pass


async def ensure_page() -> None:
    """Sembuhkan PAGE bila menunjuk halaman yang sudah tertutup (tab
    ditutup dari sisi browser, popup yang langsung mati, tab crash) —
    tanpa ini satu halaman mati meracuni semua perintah sampai restart.
    Beralih ke tab hidup terakhir, atau buat tab kosong baru. Kegagalan
    membuat halaman (jendela browser mati) TIDAK dilempar — pemanggil
    melaporkan error lewat balasan perintah."""
    global PAGE
    if PAGE is not None and not PAGE.is_closed():
        return
    pages = list(CONTEXT.pages) if CONTEXT is not None else []
    if pages:
        PAGE = pages[-1]
        return
    PAGE = None
    if CONTEXT is not None:
        try:
            PAGE = await CONTEXT.new_page()
        except Exception:  # noqa: BLE001 - jendela mati; biarkan PAGE None
            PAGE = None


async def maybe_activate_popup(new_page) -> None:
    """Popup dari tab aktif otomatis jadi tab aktif, seperti browser
    biasa (jendela masuk Google, tautan target=_blank). Halaman latar
    tanpa pembuka tidak merebut fokus."""
    try:
        opener = await new_page.opener()
    except Exception:  # noqa: BLE001
        opener = None
    if opener is not None and opener is PAGE:
        await activate(new_page)


def on_new_page(new_page) -> None:
    tab_id(new_page)
    asyncio.ensure_future(maybe_activate_popup(new_page))


async def handle_command(cmd: dict) -> dict:
    """Satu perintah JSON -> satu jawaban JSON. PAGE sudah hidup."""
    global PAGE
    if CONTEXT is not None:
        await ensure_page()
    if PAGE is None:
        return {"ok": False, "error": "browser belum siap"}
    name = cmd.get("cmd")
    try:
        if name == "status":
            return {"ok": True, "url": PAGE.url, "title": await PAGE.title()}
        if name == "screenshot":
            shot = await PAGE.screenshot(type="jpeg", quality=70)
            return {
                "ok": True,
                "image": base64.b64encode(shot).decode("ascii"),
                "width": PAGE.viewport_size["width"] if PAGE.viewport_size else None,
                "height": PAGE.viewport_size["height"] if PAGE.viewport_size else None,
            }
        if name == "click":
            button = str(cmd.get("button", "left"))
            if button not in ("left", "right", "middle"):
                button = "left"
            count = int(cmd.get("click_count", 1))
            await PAGE.mouse.click(
                int(cmd["x"]), int(cmd["y"]), button=button,
                click_count=max(1, count))
            return {"ok": True}
        if name == "hclick":
            # Klik humanize (opsional): putar ulang rekaman gerak mouse
            # manusia asli dari modul humanize.py mode "replay" di dalam
            # proses driver — lintasan + tempo persis rekaman, bukan kurva
            # sintetis lewat soket. Modul dicari di VM_STEALTH_DIR; bila
            # tidak tersedia, perintah ini membalas ok:false dan pemanggil
            # memakai "click" biasa.
            global _HUMANIZER_MOD
            if _HUMANIZER_MOD is None:
                _sdir = __import__("os").environ.get("VM_STEALTH_DIR")
                if not _sdir:
                    return {"ok": False,
                            "error": "modul humanize tidak tersedia (VM_STEALTH_DIR kosong)"}
                sys.path.insert(0, _sdir)
                import humanize as _hz
                _HUMANIZER_MOD = _hz
            hz = _HUMANIZER_MOD.Humanizer(PAGE)
            await hz.click_at(float(cmd["x"]), float(cmd["y"]))
            return {"ok": True, "mode": hz.mode,
                    "replay": getattr(hz, "last_replay", None)}
        if name == "rightclick":
            await PAGE.mouse.click(int(cmd["x"]), int(cmd["y"]),
                                   button="right")
            return {"ok": True}
        if name == "dblclick":
            await PAGE.mouse.dblclick(int(cmd["x"]), int(cmd["y"]))
            return {"ok": True}
        if name == "move":
            await PAGE.mouse.move(int(cmd["x"]), int(cmd["y"]))
            return {"ok": True}
        if name == "type":
            await PAGE.keyboard.type(str(cmd.get("text", "")))
            return {"ok": True}
        if name == "key":
            await PAGE.keyboard.press(str(cmd.get("key", "Enter")))
            return {"ok": True}
        if name == "scroll":
            await PAGE.mouse.wheel(0, int(cmd.get("dy", -300)))
            return {"ok": True}
        if name == "goto":
            await PAGE.goto(str(cmd["url"]), wait_until="domcontentloaded",
                            timeout=120000)
            await PAGE.wait_for_timeout(2000)
            return {"ok": True, "url": PAGE.url, "title": await PAGE.title()}
        if name == "back":
            resp = await PAGE.go_back(wait_until="domcontentloaded",
                                      timeout=60000)
            if resp is None:
                return {"ok": False, "error": "tidak ada riwayat mundur"}
            await PAGE.wait_for_timeout(1000)
            return {"ok": True, "url": PAGE.url, "title": await PAGE.title()}
        if name == "forward":
            resp = await PAGE.go_forward(wait_until="domcontentloaded",
                                         timeout=60000)
            if resp is None:
                return {"ok": False, "error": "tidak ada riwayat maju"}
            await PAGE.wait_for_timeout(1000)
            return {"ok": True, "url": PAGE.url, "title": await PAGE.title()}
        if name == "reload":
            await PAGE.reload(wait_until="domcontentloaded", timeout=60000)
            await PAGE.wait_for_timeout(1000)
            return {"ok": True, "url": PAGE.url, "title": await PAGE.title()}
        if name == "activeelement":
            info = await PAGE.evaluate("""() => {
                const el = document.activeElement;
                if (!el) return { editable: false, tag: "", type: "" };
                const tag = (el.tagName || "").toLowerCase();
                const type = (el.getAttribute("type") || "").toLowerCase();
                const nonText = ["button", "submit", "reset", "checkbox",
                                 "radio", "file", "image", "range", "color",
                                 "hidden"];
                const editable = !!el.isContentEditable ||
                    tag === "textarea" ||
                    (tag === "input" && !nonText.includes(type || "text"));
                return { editable, tag, type };
            }""")
            return {"ok": True, **info}
        if name == "tabs":
            return {"ok": True, "tabs": await tabs_payload()}
        if name == "newtab":
            if CONTEXT is None:
                return {"ok": False, "error": "konteks browser belum siap"}
            new_page = await CONTEXT.new_page()
            await activate(new_page)
            return {"ok": True, "id": tab_id(new_page),
                    "tabs": await tabs_payload()}
        if name == "switchtab":
            if CONTEXT is None:
                return {"ok": False, "error": "konteks browser belum siap"}
            want = int(cmd.get("id", -1))
            target = None
            for p in CONTEXT.pages:
                if tab_id(p) == want:
                    target = p
                    break
            if target is None:
                return {"ok": False, "error": "tab tidak ditemukan"}
            await activate(target)
            return {"ok": True, "id": tab_id(target), "url": target.url,
                    "title": await page_title(target)}
        if name == "closetab":
            if CONTEXT is None:
                return {"ok": False, "error": "konteks browser belum siap"}
            want = int(cmd.get("id", -1))
            target = None
            for p in CONTEXT.pages:
                if tab_id(p) == want:
                    target = p
                    break
            if target is None:
                return {"ok": False, "error": "tab tidak ditemukan"}
            if len(CONTEXT.pages) <= 1:
                # Tab terakhir tidak pernah ditutup beneran: menutupnya
                # menutup jendela Chromium dan konteks rusak. Seperti
                # browser biasa yang menyisakan tab kosong: kosongkan
                # halamannya saja.
                try:
                    await target.goto("about:blank",
                                      wait_until="domcontentloaded",
                                      timeout=15000)
                except Exception:  # noqa: BLE001
                    pass
                await activate(target)
                return {"ok": True, "tabs": await tabs_payload()}
            was_active = target is PAGE
            await target.close()
            pages = list(CONTEXT.pages)
            if not pages:
                await ensure_page()
            elif was_active:
                await activate(pages[-1])
            return {"ok": True, "tabs": await tabs_payload()}
        return {"ok": False, "error": f"perintah tidak dikenal: {name}"}
    except Exception as e:  # noqa: BLE001 - laporkan ke pemanggil
        return {"ok": False, "error": str(e)}


async def handle_client(reader, writer):
    """Satu koneksi TCP: baca baris JSON, jawab baris JSON, sampai tutup."""
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line.decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                resp = {"ok": False, "error": f"JSON tidak valid: {e}"}
            else:
                try:
                    resp = await handle_command(cmd)
                except Exception as e:  # noqa: BLE001 - satu perintah buruk
                    # tidak boleh membunuh koneksi tanpa balasan
                    resp = {"ok": False, "error": str(e)}
            writer.write((json.dumps(resp) + "\n").encode("utf-8"))
            await writer.drain()
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def navigate_initial(page) -> None:
    """Navigasi awal tahan lambat (pola browser-98.py): rute lewat proxy
    bisa 20+ dtk per lompatan dan VM berbagi CPU — timeout 180 dtk,
    sampai 3 percobaan, kegagalan TIDAK membunuh server kendali
    (browser tetap parkir supaya bisa dinavigasikan ulang)."""
    last_err = None
    for attempt in range(3):
        try:
            await page.goto(START_URL, wait_until="domcontentloaded",
                            timeout=180000)
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"NAV attempt {attempt + 1} gagal: {e}", flush=True)
            await page.wait_for_timeout(3000)
    if last_err is not None:
        print(f"NAV-FAILED url={page.url}", flush=True)
    await page.wait_for_timeout(1500)


async def main():
    global PAGE, CONTEXT
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # noqa: BLE001 - platform tanpa sinyal
            pass
    async with async_playwright() as p:
        # Peluncuran: mesin stealth dipakai bila modulnya tersedia di
        # VM_STEALTH_DIR (persona bawaan modul itu, ukuran layar disetel
        # 1280x800 mengikuti jendela VNC supaya koordinat klik Space
        # tidak geser); selain itu Chromium polos Playwright.
        import os as _os
        context = None
        _sdir = _os.environ.get("VM_STEALTH_DIR")
        if _sdir:
            try:
                sys.path.insert(0, _sdir)
                from stealth import launch_stealth  # type: ignore
                context, _persona = await launch_stealth(
                    p,
                    str(PROFILE_DIR),
                    proxy=PROXY,
                    headless=False,
                    extra_args=["--no-sandbox"],
                )
            except Exception as e:  # noqa: BLE001
                print(f"stealth launch gagal, jatuh ke polos: {e}", flush=True)
                context = None
        if context is None:
            context = await p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
                proxy={"server": PROXY} if PROXY else None,
                args=["--no-sandbox", "--window-size=1280,800",
                      "--no-first-run"],
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )
        CONTEXT = context
        context.on("page", on_new_page)
        page = context.pages[0] if context.pages else await context.new_page()
        PAGE = page
        tab_id(page)
        server = await asyncio.start_server(
            handle_client, CONTROL_HOST, CONTROL_PORT)
        print(f"Server kendali jalan di {CONTROL_HOST}:{CONTROL_PORT}",
              flush=True)
        await navigate_initial(page)
        print(f"READY title={await page_title(page)!r} url={page.url}",
              flush=True)
        async with server:
            serve_task = asyncio.ensure_future(server.serve_forever())
            stop_task = asyncio.ensure_future(stop.wait())
            _done, pending = await asyncio.wait(
                {serve_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
        await context.close()
    print("CLOSED", flush=True)


asyncio.run(main())
