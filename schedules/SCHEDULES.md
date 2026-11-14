# Schedules that keep VM Control alive

Three schedules, three different mechanisms — each exists because the
other two contexts cannot do its job.

## 1. Fleet check — every 10 minutes (system script)

Runs `backend/fleet/fleet_check.py` from a systemd timer (or any plain
cron — it needs no agent context and no network):

```ini
# your-fleet-check.service — oneshot
ExecStart=/usr/bin/python3 %h/workspace/tools/fleet/fleet_check.py
# your-fleet-check.timer
OnUnitActiveSec=10min
```

Writes `fleet/status.json` (the Space's contract) and, when a fleet is
down, the `fleet/revival-needed.json` flag.

## 2. Fleet revival — every ±15 minutes (Muse agent cron)

Revival must run **in agent context**: bot launchers inherit the
agent's proxy environment there; from a systemd context they lose
network egress and die. Create it with Muse's cron tools:

- id: `fleet-recovery-agent`, mode: `task`, interval `15m`
- body: "Run `python3 ~/workspace/tools/fleet/fleet_revive.py`. If it
  exits 0, finish silently. If it exits 1, read the last lines of
  `~/workspace/tools/fleet/fleet-log.jsonl` and briefly report which
  fleet is still dead and since when (from `status.json`). Do not try
  any other repair; never touch wallet daemons."

`fleet_revive.py` itself is start-only through the reviver
(`backend/reviver/reviver.py --once`): flock, anti-loop (max 3
attempts/hour, 5-minute cooldown), and it clears the flag only when
every flagged fleet's processes are verified alive in the process
table.

## 3. Office refresh — every 1 minute (space_action)

A silent schedule on the Space itself, created by the Space's builder
or with the cron tools as `execution.kind = space_action`:

- slug: `vm-control`, action: `refreshoffice`, args: `{}`
- interval: `1m`, id: `vm-control-kantor-refresh`

No chat delivery; failures live in the schedule's run history. The
Space reads everything else live on open, so a stalled refresh never
makes the UI lie — it only makes the 3D office snapshot older.
