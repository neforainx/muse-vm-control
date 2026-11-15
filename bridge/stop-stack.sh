#!/usr/bin/env bash
# Matikan stack bridge saja: vm-browser-chromium -> vnc-bridge ->
# Xtigervnc :98. Tidak menyentuh proses lain di VM.
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
RUN="$BASE/run"

# server kendali: SIGTERM supaya konteks Chromium ditutup bersih (ctx.close)
CPID="$(pgrep -f "vm-browser-chromiu[m].py" | head -1 || true)"
if [ -n "${CPID:-}" ]; then kill -TERM "$CPID" && echo "vm-browser-chromium (pid $CPID) SIGTERM"; sleep 5; fi
BPID="$(pgrep -f "browser-9[8].py" | head -1 || true)"
if [ -n "${BPID:-}" ]; then kill -TERM "$BPID" && echo "browser-98 (pid $BPID) SIGTERM"; sleep 5; fi
pkill -f "vnc-bridg[e].py" 2>/dev/null && echo "vnc-bridge dimatikan" || true
pkill -f "Xtigervn[c] :98" 2>/dev/null && echo "Xtigervnc :98 dimatikan" || true
rm -f "$RUN"/*.pid
sleep 1
ss -tln | grep -E ':5999|:5901|:8081' || echo "port 5999/5901/8081 tertutup"
