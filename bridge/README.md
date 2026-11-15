# Bridge — the two-way VNC bridge behind "Pengendali VNC"

This is the component that makes the VM's browser **controllable from a
phone, in both directions**: frames flow out (you see the real desktop),
input flows in (your taps, drags and pastes land in the real browser).
Earlier versions of this repo shipped only the Space *spec* — installs
built from that spec alone ended up one-way (a viewer) or not smooth,
because the bridge itself was missing. **Install this stack first; the
Space is a thin client of it.**

## Architecture

```
 phone Space ──getframe──▶ Space action ──HTTP──▶ vnc-bridge.py ──RFB──▶ Xtigervnc :98
 phone Space ──sendinput─▶ Space action ──HTTP──▶ vnc-bridge.py ──RFB──▶ (pointer/key/scroll)
 phone Space ──Copy/Paste▶ Space action ──HTTP──▶ vnc-bridge.py ◀─ServerCutText─ VNC server
 browser tabs/nav ───────▶ Space action ──TCP JSON──▶ vm-browser-chromium.py (Playwright)
```

| Piece | File | Listens on | Role |
|---|---|---|---|
| X server | Xtigervnc :98 | RFB 127.0.0.1:5999 | 1280×800 desktop that hosts the browser |
| Frame/input bridge | `vnc-bridge.py` | HTTP 127.0.0.1:5901 | one persistent RFB connection; keeps the latest frame as JPEG; injects pointer/keyboard/scroll; tracks the VM clipboard |
| Browser driver | `vm-browser-chromium.py` | TCP JSON 127.0.0.1:8081 | owns the persistent-profile Chromium on :98; tabs, navigation, clicks, typing, screenshots |
| Simple launcher | `browser-98.py` | — | fallback browser without the control server |
| CLI client | `vm-ctl.py` | — | send control commands from a shell (verification) |

## Why it feels smooth (the numbers that matter)

- The bridge holds **one persistent RFB connection** and requests
  frames continuously; every completed frame is re-encoded once as
  **JPEG quality 70** at 1280×800 and cached. Clients always read the
  latest cached frame — no per-request capture, no screenshot stalls.
- `GET /health` returns `seq` (frame counter) and `frame_age_ms`; a
  healthy bridge advances `seq` constantly while the desktop changes
  and `frame_age_ms` stays small. If your install feels laggy, check
  these two numbers before blaming the Space.
- Input is injected over the **same** RFB connection (pointer events,
  keysyms, scroll) — there is no second channel to fall out of sync.
- The Space polls `getframe` on a short interval and renders the frame
  full-bleed; see `space/PENGENDALI-VNC.md` for the exact client spec.

## HTTP bridge API (127.0.0.1:5901)

- `GET /health` → `{"ok":bool,"vnc":bool,"w":1280,"h":800,"seq":n,"frame_age_ms":n}`
- `GET /frame` → latest desktop frame as JPEG (503 while no frame yet)
- `GET /clipboard` → `{"ok":true,"text":"..."}` (latest ServerCutText from the VM)
- `POST /input` → JSON events:
  - `{"type":"pointer","x":int,"y":int,"button":int}` (button = RFB button mask)
  - `{"type":"key","keysym":int,"down":bool}`
  - `{"type":"scroll","x":int,"y":int,"dy":int}`
  - `{"type":"type","text":"..."}` (types text into the VM, for Paste)

## Browser control protocol (TCP 127.0.0.1:8081, one JSON per line)

`status` · `screenshot` · `click` · `rightclick` · `dblclick` · `move` ·
`type` · `key` · `scroll` · `goto` · `back` · `forward` · `reload` ·
`activeelement` · `tabs` · `newtab` · `switchtab` · `closetab` ·
`hclick` (optional humanized click, needs a `humanize` module in
`VM_STEALTH_DIR`; replies `ok:false` when absent).
Popups opened by the active page automatically become the active tab,
like a normal browser.

## Install

```bash
# system pieces (Debian/Ubuntu-style VM)
sudo apt-get install -y tigervnc-standalone-server   # provides Xtigervnc
python3 -m pip install numpy pillow                  # for vnc-bridge.py
# a Python with Playwright + Chromium for the driver, e.g. your own venv:
#   pip install playwright && playwright install chromium

mkdir -p ~/workspace/tools/vm-browser   # persistent browser profile lives here
cp bridge/*.py bridge/*.sh ~/workspace/tools/bridge/   # or any fixed folder
chmod +x ~/workspace/tools/bridge/*.sh
BRIDGE_PYTHON=/path/to/venv/bin/python ~/workspace/tools/bridge/start-stack.sh
curl -s http://127.0.0.1:5901/health
```

Optional env (set in the shell that runs `start-stack.sh`):

- `VM_BROWSER_PROXY=http://127.0.0.1:PORT` — route the browser through
  one fixed egress proxy (a static-IP exit). Empty = direct.
- `VM_STEALTH_DIR=/path` — folder with an optional `stealth.py`
  (`launch_stealth`) / `humanize.py`; the driver falls back to plain
  Chromium when absent.

Keep the stack alive across VM restarts the same way as the rest of
this repo: register `start-stack.sh` with your reviver/fleet layer
(start-only, idempotent — it only starts what is missing).

## Verify two-way interactivity (do not skip)

1. **Frames out:** `curl -s http://127.0.0.1:5901/health` twice, a few
   seconds apart, while the desktop changes — `seq` must increase and
   `frame_age_ms` must stay low. `curl -s http://127.0.0.1:5901/frame
   -o /tmp/f.jpg` must be a real 1280×800 JPEG of the desktop.
2. **Input in:** `python3 vm-ctl.py goto https://example.com/` then
   `python3 vm-ctl.py status` — the URL must change. Then, from the
   Space: tap a text field on a page, use Paste, and confirm the text
   appears in the frame; use Copy on selected text and confirm
   `GET /clipboard` returns it.
3. **The Space check:** open Pengendali VNC, drag on the frame — the
   desktop must scroll/move under your finger with no visible
   steppiness, and the frame must follow within a fraction of a second.

If step 1 passes but the Space feels one-way, the Space was built
without the `sendinput` wiring — rebuild it from
`space/PENGENDALI-VNC.md` exactly.
