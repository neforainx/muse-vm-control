#!/usr/bin/env python3
"""Klien baris perintah kecil untuk server kendali browser (TCP 8081).

Pakai:
  vm-ctl.py status
  vm-ctl.py goto https://example.com/
  vm-ctl.py tabs
  vm-ctl.py raw '{"cmd":"click","x":100,"y":200}'

Satu perintah JSON per baris, satu jawaban JSON per baris — protokol
yang sama dengan yang dipakai Space Pengendali VNC.
"""
import json
import socket
import sys

HOST, PORT = "127.0.0.1", 8081


def send(obj, timeout=120):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
    s.sendall((json.dumps(obj) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(1048576)
        if not chunk:
            break
        data += chunk
    s.close()
    return json.loads(data.decode())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    name = sys.argv[1]
    if name == "raw":
        obj = json.loads(sys.argv[2])
    elif name == "goto":
        obj = {"cmd": "goto", "url": sys.argv[2]}
    else:
        obj = {"cmd": name}
    print(json.dumps(send(obj), indent=2)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
