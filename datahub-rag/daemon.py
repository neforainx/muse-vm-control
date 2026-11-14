#!/usr/bin/env python3
"""DataHub RAG daemon — resident query server (Workstream 1, 10 Nov 2026).

Memuat model intfloat/multilingual-e5-small SEKALI saat start, lalu melayani
kueri lewat Unix socket (daemon.sock di folder ini) memakai logika hibrida
rag.py PERSIS: daemon mengimpor modul rag dan menambal rag.muat_model agar
mengembalikan model yang sudah termuat, lalu memanggil rag.cmd_query dengan
stdout/stderr ditangkap. Tidak ada logika skor yang ditulis ulang di sini —
semua skor makna+kata/idf+kebaruan+sinonim+demosi tetap milik rag.py.

Protokol: satu baris JSON per koneksi.
  {"cmd":"ping"}                          -> {"ok":true,"cmd":"pong",...}
  {"cmd":"status"}                        -> status daemon + model + uptime
  {"query":"teks kueri","k":6}            -> {"ok":true,"stdout":...,"stderr":...,"elapsed_sec":...}
  {"cmd":"shutdown"}                      -> daemon berhenti rapi (fallback rag.sh mengambil alih)

Jalur resmi rag.sh TIDAK diubah dan tetap fallback bila daemon mati:
client (ragd.sh) mencoba socket; gagal -> exec rag.sh persis apa adanya.

Heartbeat: daemon-heartbeat.json disentuh tiap 60 dtk (utas latar) dan tiap
kueri, untuk pemeriksaan fleet (ambang fleet_check 25 mnt).
"""
import io, json, os, socket, sys, threading, time
from contextlib import redirect_stderr, redirect_stdout

BASE = os.path.dirname(os.path.abspath(__file__))
SOCK = os.path.join(BASE, "daemon.sock")
PIDF = os.path.join(BASE, "daemon.pid")
HB = os.path.join(BASE, "daemon-heartbeat.json")
LOG = os.path.join(BASE, "daemon.log")

sys.path.insert(0, BASE)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

T_START = time.time()
_state = {"model": None, "queries": 0, "last_query_at": None}


def log(msg):
    line = f"[{time.strftime('%F %T %Z')}] {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def touch_hb():
    try:
        with open(HB, "w", encoding="utf-8") as fh:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                       "pid": os.getpid(), "queries": _state["queries"],
                       "uptime_sec": round(time.time() - T_START, 1)}, fh)
    except Exception:
        pass


def hb_loop(stop):
    while not stop.wait(60):
        touch_hb()


def run_query(pertanyaan, k):
    """Jalankan rag.cmd_query dengan model resident; tangkap keluaran."""
    import rag  # noqa: F401  (muat_model sudah ditambal di main)
    buf_out, buf_err = io.StringIO(), io.StringIO()
    t0 = time.time()
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        rag.cmd_query(pertanyaan, int(k))
    _state["queries"] += 1
    _state["last_query_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    touch_hb()
    return {"ok": True, "stdout": buf_out.getvalue(),
            "stderr": buf_err.getvalue(),
            "elapsed_sec": round(time.time() - t0, 3)}


def handle(conn):
    try:
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        if not data.strip():
            return True
        req = json.loads(data.decode("utf-8"))
        cmd = req.get("cmd")
        if cmd == "ping":
            resp = {"ok": True, "cmd": "pong", "pid": os.getpid(),
                    "uptime_sec": round(time.time() - T_START, 1)}
        elif cmd == "status":
            resp = {"ok": True, "cmd": "status", "pid": os.getpid(),
                    "model": "intfloat/multilingual-e5-small",
                    "model_loaded": _state["model"] is not None,
                    "queries_served": _state["queries"],
                    "last_query_at": _state["last_query_at"],
                    "uptime_sec": round(time.time() - T_START, 1)}
        elif cmd == "shutdown":
            resp = {"ok": True, "cmd": "bye"}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            return False
        elif req.get("query"):
            resp = run_query(req["query"], req.get("k", 6))
        else:
            resp = {"ok": False, "error": "permintaan tidak dikenal"}
        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        return True
    except Exception as e:  # daemon tidak boleh mati karena satu kueri gagal
        log(f"ERROR handle: {type(e).__name__}: {e}")
        try:
            conn.sendall((json.dumps(
                {"ok": False, "error": f"{type(e).__name__}: {e}"})
                + "\n").encode("utf-8"))
        except Exception:
            pass
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    import rag
    log("start: memuat model (satu kali) ...")
    t0 = time.time()
    model = rag.muat_model()
    _state["model"] = model
    rag.muat_model = lambda: model  # semua cmd_query berikutnya pakai ini
    log(f"model termuat dalam {time.time()-t0:.1f} dtk")
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(8)
    srv.settimeout(1.0)
    with open(PIDF, "w") as fh:
        fh.write(str(os.getpid()))
    stop = threading.Event()
    threading.Thread(target=hb_loop, args=(stop,), daemon=True).start()
    touch_hb()
    log(f"siap: socket {SOCK} pid {os.getpid()}")
    running = True
    while running:
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        running = handle(conn)
    stop.set()
    srv.close()
    for p in (SOCK, PIDF):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
    log("berhenti rapi")


if __name__ == "__main__":
    main()
