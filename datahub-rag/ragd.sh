#!/bin/sh
# DataHub fast path: try the resident daemon first; daemon down or
# unreachable -> fall back EXACTLY to the official launcher rag.sh
# (rag.sh's contract is unchanged).
# Usage: ragd.sh query "text" [k]   |   ragd.sh ping   |   ragd.sh status
cd "$(dirname "$0")" || exit 1
export HF_HUB_OFFLINE=1
case "$1" in
  ping|status)
    exec ./.venv/bin/python daemon_client.py "$1" ;;
  shutdown)
    exec ./.venv/bin/python daemon_client.py shutdown ;;
  query)
    if ./.venv/bin/python daemon_client.py query "$2" "${3:-6}"; then
      exit 0
    fi
    echo "[ragd] daemon failed — falling back to rag.sh" >&2
    exec ./rag.sh query "$2" ;;
  *)
    echo "usage: ragd.sh query \"text\" [k] | ping | status | shutdown" >&2
    exit 2 ;;
esac
