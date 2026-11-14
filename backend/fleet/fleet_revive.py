#!/usr/bin/env python3
"""Agent-context fleet revival.

WHY THIS EXISTS: fleet_check.py runs from a systemd system service,
whose context cannot harvest the agent's proxy environment; bot
launchers that need network egress die there. The identical reviver
run from the agent context works, so revival happens in agent context. So revival happens HERE, in
agent context, driven by an agent cron every ±15 minutes:

- No revival-needed.json flag (or flag older than 30 min) → exit 0
  silently.
- Flag present → run the existing reviver (--once, start-only,
  anti-loop), wait, re-check the flagged fleets' processes from the
  manifest, append the outcome to fleet-log.jsonl, and clear the flag
  only when every flagged fleet's processes are alive again.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FLAG = BASE / "revival-needed.json"
MANIFEST = BASE / "manifest.json"
LOG = BASE / "fleet-log.jsonl"
REVIVER = Path(__import__("os").environ.get("VM_CONTROL_REVIVER", str(BASE.parent / "reviver" / "reviver.py")))


def main():
    if not FLAG.exists():
        return 0
    try:
        flag = json.loads(FLAG.read_text(encoding="utf-8"))
    except Exception:
        FLAG.unlink()
        return 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    subprocess.run([sys.executable, str(REVIVER), "--once"],
                   capture_output=True, text=True, timeout=300)
    time.sleep(20)
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True,
                        timeout=30).stdout
    still_dead = []
    for name in flag.get("dead", []):
        fleet = next((f for f in manifest["bot_fleets"]
                      if f["name"] == name), None)
        if fleet is None:
            continue
        alive = all(any(p in line and "grep" not in line
                        for line in ps.splitlines())
                    for p in fleet["processes"])
        if not alive:
            still_dead.append(name)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             "event": "agent-context-revival",
             "flagged": flag.get("dead", []), "still_dead": still_dead}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False))
    if not still_dead:
        FLAG.unlink()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
