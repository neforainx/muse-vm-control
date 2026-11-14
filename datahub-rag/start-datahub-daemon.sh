#!/bin/bash
# DataHub RAG daemon guardian — a self-healing loop, deliberately NOT a
# systemd service for the process itself (agent context): a daemon that
# dies or crashes is restarted within 5 seconds.
# Stop fully: pkill -f start-datahub-daemon.sh (then kill daemon.py).
cd "$(dirname "$0")" || exit 1
echo "[guardian] start $(date '+%F %T %Z')" >> daemon-guardian.log
while true; do
  HF_HUB_OFFLINE=1 ./.venv/bin/python daemon.py >> daemon.log 2>&1
  echo "[guardian] daemon stopped rc=$? — restarting in 5s $(date '+%F %T %Z')" >> daemon-guardian.log
  sleep 5
done
