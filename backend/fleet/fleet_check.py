#!/usr/bin/env python3
"""Fleet check + recovery — the health layer of the VM Control framework.

What this does (and does not) do:
- CHECKS every bot fleet in manifest.json: its processes are alive AND
  its heartbeat file (when it has one) is fresh (< 25 min).
- REVIVES dead fleets ONLY through the existing reviver
  (~/workspace/tools/reviver/reviver.py --once): start-only, anti-loop,
  no kills, no other commands. This script never starts anything itself.
- CHECKS the systemd timers listed in the manifest are active
  (report-only here; unit restoration belongs to the timer sweep /
  boot-repair, which read daftar-unit.tsv).
- WRITES status.json + appends fleet-log.jsonl in this directory.
- Exit code 0 only when every fleet is verified alive after any revival.

It never touches wallet daemons or other on-demand services.
On-demand services are healthy when idle.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "manifest.json"
REVIVER = Path(os.environ.get("VM_CONTROL_REVIVER", str(BASE.parent / "reviver" / "reviver.py")))
STATUS = BASE / "status.json"
LOG = BASE / "fleet-log.jsonl"
HEARTBEAT_MAX_AGE = 25 * 60  # seconds


def _ps():
    out = subprocess.run(["ps", "aux"], capture_output=True, text=True,
                         timeout=30).stdout
    return out


def fleet_state(fleet, ps_text):
    alive = [p for p in fleet["processes"]
             if any(p in line and "grep" not in line
                    for line in ps_text.splitlines())]
    hb_age = None
    if fleet.get("heartbeat"):
        hp = Path(fleet["heartbeat"])
        if hp.exists():
            hb_age = time.time() - hp.stat().st_mtime
    processes_ok = len(alive) == len(fleet["processes"])
    hb_ok = hb_age is None or hb_age < HEARTBEAT_MAX_AGE
    return {"fleet": fleet["name"], "processes_alive": alive,
            "processes_expected": fleet["processes"],
            "processes_ok": processes_ok,
            "heartbeat_age_sec": (round(hb_age) if hb_age is not None
                                  else None),
            "heartbeat_ok": hb_ok, "ok": processes_ok and hb_ok}


def timer_state(unit):
    r = subprocess.run(["systemctl", "is-active", unit],
                       capture_output=True, text=True, timeout=15)
    return {"unit": unit, "state": r.stdout.strip()}


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ps_text = _ps()
    fleets = [fleet_state(f, ps_text) for f in manifest["bot_fleets"]]
    revived = []
    if not all(f["ok"] for f in fleets):
        # One reviver pass (start-only, anti-loop inside the reviver).
        subprocess.run([sys.executable, str(REVIVER), "--once"],
                       capture_output=True, text=True, timeout=300)
        revived = [f["fleet"] for f in fleets if not f["ok"]]
        time.sleep(20)  # let launchers bring children up
        ps_text = _ps()
        fleets = [fleet_state(f, ps_text) for f in manifest["bot_fleets"]]
    timers = [timer_state(t["unit"]) for t in manifest["systemd_timers"]]
    result = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "fleets": fleets, "revival_attempted_for": revived,
              "timers": timers,
              "all_fleets_ok": all(f["ok"] for f in fleets)}
    # Revival from a system-service context is unreliable here (a system
    # service cannot harvest the agent proxy env — proven 8 Nov 2026:
    # systemd-run revival failed, the same reviver in agent context
    # succeeded). So a dead fleet also raises a flag file that an agent
    # cron consumes with fleet_revive.py in agent context.
    flag = BASE / "revival-needed.json"
    if not result["all_fleets_ok"]:
        flag.write_text(json.dumps(
            {"ts": result["ts"],
             "dead": [f["fleet"] for f in fleets if not f["ok"]]},
            ensure_ascii=False), encoding="utf-8")
    elif flag.exists():
        flag.unlink()
    STATUS.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["all_fleets_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
