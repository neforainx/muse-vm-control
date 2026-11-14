#!/usr/bin/env python3
# vm_status.py — host status collector (reference implementation).
#
# Emits vm-status.json: the host half of the contract that the VM
# Control Space's Beranda (home) page renders. The Space's own
# getvmstatus action reads the host live and merges this shape with the
# fleet status.json; if your Space build prefers file-based reads,
# point it at this file instead — the shape is identical.
#
# Pure stdlib, read-only, no network except optional localhost TCP
# probes of daemons you list in PROBES.
import json, os, socket, sys, time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vm-status.json")
FLEET_STATUS = os.path.expanduser(
    os.environ.get("VM_CONTROL_FLEET_STATUS",
                   "~/workspace/tools/fleet/status.json"))
# (label, host, port) — on-demand daemons: "listening" only means the
# port answers; an idle on-demand daemon that is not listening is a
# normal state, reported as such, never as an error.
PROBES = [
    ("example-daemon", "127.0.0.1", 8080),
    ("example-forwarder", "127.0.0.1", 9000),
]


def host():
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    load = os.getloadavg()
    mem = {}
    with open("/proc/meminfo") as f:
        for ln in f:
            k, v = ln.split(":")
            mem[k] = int(v.split()[0]) * 1024
    disk = os.statvfs(os.path.expanduser("~/workspace"))
    return {
        "hostname": socket.gethostname(),
        "uptime_sec": int(up),
        "load1": round(load[0], 2), "load5": round(load[1], 2),
        "load15": round(load[2], 2),
        "ram_total": mem.get("MemTotal"), "ram_available": mem.get("MemAvailable"),
        "disk_total": disk.f_blocks * disk.f_frsize,
        "disk_free": disk.f_bavail * disk.f_frsize,
    }


def probe(host_, port, timeout=1.5):
    try:
        with socket.create_connection((host_, port), timeout=timeout):
            return True
    except OSError:
        return False


def main():
    data = {"tool": "vm-status", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "host": host(), "probes": [
                {"label": label, "port": port, "listening": probe(h, port)}
                for label, h, port in PROBES]}
    if os.path.exists(FLEET_STATUS):
        try:
            with open(FLEET_STATUS) as f:
                data["fleet"] = json.load(f)
        except Exception as e:
            data["fleet"] = {"error": f"unreadable: {e}"}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, OUT)
    print(f"vm-status: wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
