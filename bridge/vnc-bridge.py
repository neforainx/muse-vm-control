#!/usr/bin/env python3
"""vnc-bridge: local VNC client + HTTP bridge for the phone controller.

Connects to the local TigerVNC server (Xtigervnc :99, 127.0.0.1:5999) over RFB,
keeps the framebuffer current, and serves it over plain HTTP on 127.0.0.1:5901
for the Pengendali VNC artifact server to proxy. No relay, no Cloudflare, no
egress needed — everything is local to the VM.

Endpoints (all localhost-only):
  GET  /health  -> {"ok":bool,"vnc":bool,"w":1280,"h":800,"seq":n,"frame_age_ms":n}
  GET  /clipboard -> {"ok":true,"text":"..."}  (latest ServerCutText from the VM)
  GET  /frame   -> latest desktop frame as JPEG (503 while no frame yet)
  POST /input   -> {"type":"pointer","x":int,"y":int,"button":int}  (button mask:
                   1 left, 2 middle, 4 right; 0 = move only)
                   {"type":"key","keysym":int,"down":bool}
                   {"type":"type","text":"..."}  (type a string, keysym per char)
                   {"type":"scroll","x":int,"y":int,"dy":int}  (dy>0 up, dy<0 down)
  POST /refresh -> force a full framebuffer request on the next cycle

Stdlib + numpy + PIL only. Run: python3 vnc-bridge.py (logs to stdout).
"""
import io
import json
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image

VNC_HOST = "127.0.0.1"
VNC_PORT = 5999
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 5901
JPEG_QUALITY = 70

# RFB encodings we accept
ENC_RAW = 0
ENC_COPYRECT = 1
# Pseudo-encodings the server may send only if requested (we never request them)
ENC_DESKTOP_SIZE = -223


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class RFBClient:
    """One persistent RFB 3.8 connection. Keeps a numpy framebuffer + JPEG cache."""

    def __init__(self):
        self.sock = None
        self.connected = False
        self.w = 1280
        self.h = 800
        self.fb = np.zeros((800, 1280, 3), dtype=np.uint8)
        self.jpeg = None
        self.jpeg_seq = 0
        self.jpeg_ts = 0.0
        self.cut_text = ""
        self.dirty = False
        self.want_full = False
        self.send_lock = threading.Lock()
        self.fb_lock = threading.Lock()
        self.stop = False

    # -- low-level socket helpers -----------------------------------------
    def _recvn(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise IOError("vnc connection closed")
            buf += chunk
        return buf

    def _send(self, data):
        with self.send_lock:
            self.sock.sendall(data)

    # -- connection --------------------------------------------------------
    def connect(self):
        s = socket.create_connection((VNC_HOST, VNC_PORT), timeout=10)
        s.settimeout(None)  # blokir tanpa batas sesudah connect: desktop diam >10 dtk tidak lagi memutus koneksi RFB (perbaikan satu baris, disetujui pemilik 12 Nov 2026)
        self.sock = s
        ver = self._recvn(12)
        assert ver.startswith(b"RFB 003."), ver
        self._send(b"RFB 003.008\n")
        nsec = self._recvn(1)[0]
        types = self._recvn(nsec)
        assert 1 in types, "None auth not offered"
        self._send(bytes([1]))
        result = struct.unpack(">I", self._recvn(4))[0]
        assert result == 0, "auth failed"
        self._send(bytes([1]))  # shared
        w, h = struct.unpack(">HH", self._recvn(4))
        self._recvn(16)  # server pixel format (we set our own below)
        nlen = struct.unpack(">I", self._recvn(4))[0]
        self._recvn(nlen)
        self.w, self.h = w, h
        with self.fb_lock:
            self.fb = np.zeros((h, w, 3), dtype=np.uint8)
        # pixel format: 32bpp, depth 24, little-endian, true colour,
        # max 255/255/255, shifts 16/8/0
        self._send(struct.pack(">BxxxBBBBHHHBBBxxx",
                                0, 32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
        # encodings: Raw + CopyRect
        self._send(struct.pack(">BxH", 2, 2)
                   + struct.pack(">i", ENC_RAW) + struct.pack(">i", ENC_COPYRECT))
        self.connected = True
        log(f"VNC connected {w}x{h}")
        # full frame first, then incremental loop
        self._request_frame(incremental=0)

    def _request_frame(self, incremental):
        self._send(struct.pack(">BBHHHH", 3, incremental, 0, 0, self.w, self.h))

    # -- update loop -------------------------------------------------------
    def run(self):
        while not self.stop:
            try:
                if not self.connected:
                    self.connect()
                self._read_update()
                # next request (full if a refresh was asked for)
                full = self.want_full
                self.want_full = False
                self._request_frame(incremental=0 if full else 1)
            except (IOError, OSError, AssertionError, struct.error) as e:
                log("VNC error:", e)
                self.connected = False
                try:
                    self.sock.close()
                except Exception:
                    pass
                time.sleep(1)

    def _read_update(self):
        msg = self._recvn(1)[0]
        if msg == 0:  # FramebufferUpdate
            self._recvn(1)
            nrect = struct.unpack(">H", self._recvn(2))[0]
            with self.fb_lock:
                for _ in range(nrect):
                    rx, ry, rw, rh, enc = struct.unpack(">HHHHi", self._recvn(12))
                    if enc == ENC_RAW:
                        raw = self._recvn(rw * rh * 4)
                        arr = np.frombuffer(raw, dtype=np.uint8).reshape((rh, rw, 4))
                        self.fb[ry:ry + rh, rx:rx + rw, 0] = arr[:, :, 2]
                        self.fb[ry:ry + rh, rx:rx + rw, 1] = arr[:, :, 1]
                        self.fb[ry:ry + rh, rx:rx + rw, 2] = arr[:, :, 0]
                    elif enc == ENC_COPYRECT:
                        sx, sy = struct.unpack(">HH", self._recvn(4))
                        tmp = self.fb[sy:sy + rh, sx:sx + rw].copy()
                        self.fb[ry:ry + rh, rx:rx + rw] = tmp
                    elif enc == ENC_DESKTOP_SIZE:
                        self.w, self.h = rw, rh
                        self.fb = np.zeros((rh, rw, 3), dtype=np.uint8)
                        log(f"desktop resized to {rw}x{rh}")
                    else:
                        raise IOError(f"unsupported encoding {enc}")
                self.dirty = True
                self._encode_jpeg()
        elif msg == 2:  # Bell
            pass
        elif msg == 3:  # ServerCutText — VM clipboard changed; keep the
            # text so GET /clipboard can hand it to the phone (Copy button)
            self._recvn(3)
            n = struct.unpack(">I", self._recvn(4))[0]
            raw = self._recvn(n)
            try:
                self.cut_text = raw.decode("utf-8")
            except UnicodeDecodeError:
                self.cut_text = raw.decode("latin-1")
        else:
            raise IOError(f"unexpected server message {msg}")

    def _encode_jpeg(self):
        buf = io.BytesIO()
        Image.fromarray(self.fb).save(buf, "JPEG", quality=JPEG_QUALITY)
        self.jpeg = buf.getvalue()
        self.jpeg_seq += 1
        self.jpeg_ts = time.time()

    # -- input --------------------------------------------------------------
    def pointer(self, x, y, button):
        x = max(0, min(self.w - 1, int(x)))
        y = max(0, min(self.h - 1, int(y)))
        self._send(struct.pack(">BBHH", 5, int(button) & 0xFF, x, y))

    def key(self, keysym, down):
        self._send(struct.pack(">BBxxI", 4, 1 if down else 0, int(keysym)))

    def scroll(self, x, y, dy):
        steps = max(1, min(10, abs(int(dy))))
        mask = 8 if dy > 0 else 16  # wheel up / wheel down
        for _ in range(steps):
            self.pointer(x, y, mask)
            self.pointer(x, y, 0)

    # Characters that need Shift held on a US layout: A-Z plus the
    # shifted symbol row. Without Shift the VNC server drops these
    # keysyms entirely (verified live: typing "UJIKETIK9" landed
    # nothing, "uji9" landed fine).
    _SHIFTED = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ~!@#$%^&*()_+{}|:"<>?')

    def type_text(self, text):
        for ch in text:
            ks = ord(ch)
            if ch in self._SHIFTED:
                self.key(65505, True)  # Shift_L
                self.key(ks, True)
                self.key(ks, False)
                self.key(65505, False)
            else:
                self.key(ks, True)
                self.key(ks, False)


CLIENT = RFBClient()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass  # keep the log quiet

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            age = int((time.time() - CLIENT.jpeg_ts) * 1000) if CLIENT.jpeg else -1
            self._json({"ok": True, "vnc": CLIENT.connected,
                        "w": CLIENT.w, "h": CLIENT.h,
                        "seq": CLIENT.jpeg_seq, "frame_age_ms": age})
        elif self.path == "/clipboard":
            self._json({"ok": True, "text": CLIENT.cut_text})
        elif self.path == "/frame":
            with CLIENT.fb_lock:
                data = CLIENT.jpeg
            if data is None:
                self._json({"ok": False, "error": "no frame yet"}, code=503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._json({"ok": False, "error": "unknown path"}, code=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json({"ok": False, "error": "bad json"}, code=400)
            return
        if self.path == "/input":
            try:
                t = body.get("type")
                if t == "pointer":
                    CLIENT.pointer(body.get("x", 0), body.get("y", 0),
                                   body.get("button", 0))
                elif t == "key":
                    CLIENT.key(body.get("keysym", 0), body.get("down", True))
                elif t == "type":
                    CLIENT.type_text(body.get("text", ""))
                elif t == "scroll":
                    CLIENT.scroll(body.get("x", 0), body.get("y", 0),
                                  body.get("dy", 0))
                else:
                    self._json({"ok": False, "error": "unknown input type"}, code=400)
                    return
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, code=500)
        elif self.path == "/refresh":
            CLIENT.want_full = True
            self._json({"ok": True})
        else:
            self._json({"ok": False, "error": "unknown path"}, code=404)


def main():
    threading.Thread(target=CLIENT.run, daemon=True).start()
    srv = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    log(f"vnc-bridge listening on {HTTP_HOST}:{HTTP_PORT} (VNC {VNC_HOST}:{VNC_PORT})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
