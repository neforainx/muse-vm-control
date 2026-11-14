#!/bin/bash
# Start the reviver loop in AGENT context (launchers inherit the agent
# proxy environment there). Do NOT run it from systemd.
cd ~/workspace/tools/reviver || exit 1
exec /usr/bin/python3 reviver.py --interval 120 >> reviver.out 2>&1
