---
name: vm-control-setup
description: Install the VM Control framework (fleet health, analytics feed, host collectors) into a Muse VM and build the "VM control" Space — merged VM status home, 3D virtual office with analytics, file manager, and persistent terminal — then wire its three schedules and verify every layer from inside the Space.
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
- **Space (web_fullstack artifact):** "VM control" — Beranda (VM
  status), Kantor (3D office + statistics), File (file manager),
  Terminal (persistent PTY shells). Spec: `space/SPEC.md`; contracts:
  `space/ACTIONS.md`.
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

## 3. Build the Space

Use the master build prompt in `space/BUILD-PROMPTS.md` with the
artifact tools (`web_fullstack`, place it in the sidebar). Keep the
design standard from `space/SPEC.md` exactly: Liquid Glass, top
capsule navbar, bottom pill sub-navbars above a 20 px blur gradient,
one shared dark/light toggle, no descriptive paragraphs.

If your user already has separate Office / File Manager / Terminal
Spaces, merge in this order: build the combined Space with an
idempotent `import_legacy_data` action → verify the old records
arrived → only then delete the originals.

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
