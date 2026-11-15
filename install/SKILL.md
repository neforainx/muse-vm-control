---
name: vm-control-setup
description: Install the VM Control framework (fleet health, analytics feed, host collectors, two-way VNC bridge) into a Muse VM and build the "VM control" Space — merged VM status home, 3D virtual office with analytics, file manager, and persistent terminal — plus the "Pengendali VNC" controller Space, then wire its three schedules and verify every layer from inside the Spaces.
---

# VM Control — setup for the receiving Muse

You are installing this for your user, in their VM. Work in this order;
do not skip the verification steps. Everything here is read-only or
start-only by design — nothing in this framework kills processes,
moves money, or sends messages.

## 0. What you are building

- **Backend (plain scripts, zero Muse tokens):** a fleet health layer
  (check + revive), an analytics aggregator, and a host status
  collector, all under `~/workspace/tools/`.
- **Bridge (plain scripts, zero Muse tokens):** the two-way VNC
  bridge in `bridge/` — Xtigervnc desktop, frame/clipboard/input
  bridge, and the browser control driver. **Install this before
  building the controller Space; without it the Space is a one-way
  viewer and will feel broken.**
- **Space (web_fullstack artifact):** "VM control" — Beranda (VM
  status), Kantor (3D office + statistics), File (file manager),
  Terminal (persistent PTY shells). Spec: `space/SPEC.md`; contracts:
  `space/ACTIONS.md`.
- **Space (web_fullstack artifact):** "Pengendali VNC" — the phone
  controller for the VM desktop: full frame, exactly two buttons
  (Copy, Paste), three actions (`getframe`, `getclipboard`,
  `sendinput`). Spec: `space/PENGENDALI-VNC.md` — follow it exactly;
  do not add a keyboard button, a text field, or extra actions.
- **Schedules:** fleet check 10 min (system), fleet revival ±15 min
  (agent cron), office refresh 1 min (space_action).

## 1. Install the backend

```bash
mkdir -p ~/workspace/tools/{fleet,reviver,analytics,collectors}
cp backend/fleet/fleet_check.py backend/fleet/fleet_revive.py ~/workspace/tools/fleet/
cp backend/reviver/reviver.py ~/workspace/tools/reviver/
cp backend/analytics/analytics_feed.py ~/workspace/tools/analytics/
cp backend/collectors/vm_status.py ~/workspace/tools/collectors/
chmod +x ~/workspace/tools/fleet/*.py ~/workspace/tools/reviver/reviver.py
```

Then create the two live configs from the examples and edit them for
your user's actual bots (names, directories, launcher scripts,
heartbeat files):

```bash
cp backend/fleet/manifest.example.json ~/workspace/tools/fleet/manifest.json
cp backend/reviver/bots.example.json ~/workspace/tools/reviver/bots.json
mkdir -p ~/workspace/tools/reviver/stop
```

Also edit the `SOURCES` list at the top of
`~/workspace/tools/analytics/analytics_feed.py` to point at the state
files your user's pipelines really write, and set `PROBES` in
`vm_status.py` to the localhost daemons worth probing (or leave it
empty).

## 2. Prove the backend before building anything visual

```bash
python3 ~/workspace/tools/fleet/fleet_check.py; echo exit=$?
cat ~/workspace/tools/fleet/status.json        # fleets + timers, all_fleets_ok
python3 ~/workspace/tools/analytics/analytics_feed.py
cat ~/workspace/tools/analytics/state.json     # ok:false must carry a reason
python3 ~/workspace/tools/collectors/vm_status.py
```

A source that is missing or stale must show up as a flag with a
reason — if anything reports a fabricated zero, stop and fix the
config; that honesty rule is the point of the framework.

## 2b. Install and prove the bridge

Follow `bridge/README.md`:

```bash
sudo apt-get install -y tigervnc-standalone-server
python3 -m pip install numpy pillow
# plus a Python env with playwright + chromium for the driver
mkdir -p ~/workspace/tools/vm-browser ~/workspace/tools/bridge
cp bridge/*.py bridge/*.sh ~/workspace/tools/bridge/
chmod +x ~/workspace/tools/bridge/*.sh
BRIDGE_PYTHON=/path/to/venv/bin/python ~/workspace/tools/bridge/start-stack.sh
```

Prove it from the shell before building any Space:

```bash
curl -s http://127.0.0.1:5901/health   # twice: seq must increase
curl -s http://127.0.0.1:5901/frame -o /tmp/f.jpg   # a real 1280x800 desktop
python3 ~/workspace/tools/bridge/vm-ctl.py goto https://example.com/
python3 ~/workspace/tools/bridge/vm-ctl.py status   # URL must have changed
```

Register `start-stack.sh` with the reviver (start-only, idempotent)
so the stack returns after VM restarts. If `/health` does not advance
`seq`, fix the bridge first — no Space work will make a dead bridge
feel interactive.

## 3. Build the Spaces

Use the master build prompt in `space/BUILD-PROMPTS.md` with the
artifact tools (`web_fullstack`, place it in the sidebar). Keep the
design standard from `space/SPEC.md` exactly: Liquid Glass, top
capsule navbar, bottom pill sub-navbars above a 20 px blur gradient,
one shared dark/light toggle, no descriptive paragraphs.

If your user already has separate Office / File Manager / Terminal
Spaces, merge in this order: build the combined Space with an
idempotent `import_legacy_data` action → verify the old records
arrived → only then delete the originals.

Then build **Pengendali VNC** from `space/PENGENDALI-VNC.md` exactly:
full frame, only Copy and Paste buttons, no keyboard button, no
visible input field, the gesture map as written, and exactly the
three actions `getframe` / `getclipboard` / `sendinput` wired to the
bridge on 127.0.0.1:5901. This page is a thin client of the bridge —
if it feels one-way or laggy afterwards, the wiring or the bridge is
wrong, not the spec.

## 4. Wire the three schedules

Follow `schedules/SCHEDULES.md` exactly:

1. fleet check every 10 min (systemd timer or plain cron),
2. `fleet-recovery-agent` Muse cron, interval 15m, running
   `fleet_revive.py` in agent context,
3. `vm-control-kantor-refresh` space_action cron, interval 1m,
   action `refreshoffice`.

## 5. Verify from inside the Space (not from outside)

- Open the Space: Beranda shows real host numbers and your fleets.
- `getvmstatus` returns the same `status.json` the timer wrote.
- Kill one harmless test bot, wait for the check + revival cycle, and
  watch it come back and the flag clear.
- In Terminal, run a command, reload the page, confirm the shell and
  its history survived.
- In File, confirm a denylisted path (e.g. `~/.ssh`) is refused.
- In Pengendali VNC, prove **both directions**: the frame is alive
  without reloading; a tap clicks; a drag tracks your finger;
  double-tap a text field, type on the phone keyboard, and the text
  lands in the VM; select text in the VM → Copy puts it on the phone
  clipboard → Paste types it into another field. If any direction
  fails, do not hand the install over as done — re-check the bridge
  health (`seq`, `frame_age_ms`) and the `sendinput` wiring.

## Hard rules inherited from production

- The reviver is **start-only** and allowlisted; never extend it to
  kill or to run arbitrary commands.
- Revival runs in **agent context only** — systemd contexts lose the
  agent's proxy environment.
- Unreadable data renders as "not yet recorded" **with the error** —
  never invent numbers, and never present projected revenue as
  collected cash.
- The Space is **owner-only**: it contains a real shell. Never share
  it publicly.
