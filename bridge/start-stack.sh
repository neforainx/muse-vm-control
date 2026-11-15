#!/usr/bin/env bash
# Starter stack bridge VNC — hanya menyalakan yang hilang (idempoten).
# Komponen: Xtigervnc :98 (RFB 127.0.0.1:5999) -> vnc-bridge.py (HTTP
# 127.0.0.1:5901) -> vm-browser-chromium.py: server kendali TCP
# 127.0.0.1:8081 yang MEMILIKI browser Chromium (profil persisten
# ~/workspace/tools/vm-browser/profile) di display :98.
# Pola pgrep memakai trik kurung ("vnc-bridg[e]") supaya pola tidak muncul
# literal di baris perintah pemanggil.
#
# Env opsional:
#   VM_BROWSER_PROXY  proxy keluar browser, mis. http://127.0.0.1:8080
#                     untuk pintu keluar ber-IP tetap (kosong = langsung)
#   VM_STEALTH_DIR    folder modul stealth opsional (stealth.py)
#   BRIDGE_PYTHON     python untuk driver browser (butuh playwright);
#                     bawaan: python3. vnc-bridge cukup python3 sistem
#                     dengan numpy + Pillow.
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
RUN="$BASE/run"; LOGS="$BASE/logs"
mkdir -p "$RUN" "$LOGS"
URL="${1:-https://example.com/}"
PY="${BRIDGE_PYTHON:-python3}"

# 1. Xtigervnc :98
if pgrep -f "Xtigervn[c] :98" >/dev/null; then
  echo "Xtigervnc :98 sudah jalan"
else
  setsid nohup Xtigervnc :98 -geometry 1280x800 -depth 24 -rfbport 5999 \
    -localhost -SecurityTypes None >"$LOGS/xtigervnc-98.log" 2>&1 < /dev/null &
  sleep 4
  pgrep -f "Xtigervn[c] :98" > "$RUN/xtigervnc.pid"
  echo "Xtigervnc :98 dijalankan (pid $(cat "$RUN/xtigervnc.pid"))"
fi

# 2. vnc-bridge.py -> HTTP 127.0.0.1:5901 (frame JPEG + clipboard + input)
if pgrep -f "vnc-bridg[e].py" >/dev/null; then
  echo "vnc-bridge sudah jalan"
else
  cd "$BASE" && setsid nohup python3 vnc-bridge.py >"$LOGS/vnc-bridge.log" 2>&1 < /dev/null &
  sleep 3
  pgrep -f "vnc-bridg[e].py" > "$RUN/vnc-bridge.pid"
  echo "vnc-bridge dijalankan (pid $(cat "$RUN/vnc-bridge.pid"))"
fi

# 3. server kendali browser (vm-browser-chromium.py) di display :98
if pgrep -f "vm-browser-chromiu[m].py" >/dev/null; then
  echo "vm-browser-chromium sudah jalan"
elif pgrep -f "browser-9[8].py" >/dev/null; then
  echo "PERINGATAN: browser-98.py masih jalan — matikan dulu (stop-stack.sh) supaya profil tidak terkunci ganda"
else
  cd "$BASE" && DISPLAY=:98 setsid nohup \
    "$PY" vm-browser-chromium.py "$URL" \
    >"$LOGS/vm-browser-chromium.log" 2>&1 < /dev/null &
  sleep 2
  pgrep -f "vm-browser-chromiu[m].py" > "$RUN/vm-browser-chromium.pid"
  echo "vm-browser-chromium dijalankan (pid $(cat "$RUN/vm-browser-chromium.pid"), url awal $URL)"
fi

echo "== ports =="
ss -tln | grep -E ':5999|:5901|:8081' || echo NO_PORTS
echo "== health bridge =="
curl -s -m 8 http://127.0.0.1:5901/health || echo "health GAGAL"
echo
