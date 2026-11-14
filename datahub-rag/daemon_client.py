#!/usr/bin/env python3
"""Klien tipis daemon DataHub RAG: kirim satu baris JSON ke daemon.sock,
cetak respons. Dipakai ragd.sh. Exit 2 bila daemon tak terjangkau."""
import json, os, socket, sys

SOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.sock")


def main():
    if len(sys.argv) < 2:
        print("pakai: daemon_client.py ping|status|shutdown | query \"teks\" [k]",
              file=sys.stderr)
        return 2
    mode = sys.argv[1]
    if mode == "query":
        req = {"query": sys.argv[2], "k": int(sys.argv[3]) if len(sys.argv) > 3 else 6}
    else:
        req = {"cmd": mode}
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(300)
        s.connect(SOCK)
    except OSError as e:
        print(f"daemon tidak terjangkau: {e}", file=sys.stderr)
        return 2
    s.sendall((json.dumps(req) + "\n").encode("utf-8"))
    data = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\n"):
            break
    s.close()
    resp = json.loads(data.decode("utf-8"))
    if mode == "query":
        if not resp.get("ok"):
            print(f"daemon error: {resp.get('error')}", file=sys.stderr)
            return 1
        sys.stdout.write(resp["stdout"])
        sys.stderr.write(resp["stderr"])
        print(f"[daemon: {resp['elapsed_sec']}s]", file=sys.stderr)
    else:
        print(json.dumps(resp, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
