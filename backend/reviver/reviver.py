#!/usr/bin/env python3
"""Automatic bot reviver — a pure script, zero Muse tokens.

Safety principles:
- Start-only: it only runs the official launchers on its allowlist.
- It never kills a process and never runs any other command.
- Single instance (flock). A bot that is already alive is skipped.
- Anti-loop: a cooldown between attempts plus a max-attempts window;
  once the cap is hit it stops trying and only logs.
- Stop marker: a stop/<name>.stop file makes a bot fully skipped.
- It never touches wallet daemons or trading execution.
"""
import argparse, fcntl, json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))

def now():
    return time.time()

def fmt(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

class Reviver:
    def __init__(self, config_path, state_path, lock_path, status_path, log_path):
        with open(config_path) as f:
            self.bots = json.load(f)["bots"]
        self.state_path, self.status_path, self.log_path = state_path, status_path, log_path
        self.state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}
        self.lockf = open(lock_path, "w")
        try:
            fcntl.flock(self.lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another reviver is running — exiting")
            sys.exit(0)

    def log(self, msg):
        line = f"[{fmt(now())}] {msg}"
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def save_state(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.state_path)

    @staticmethod
    def proc_table():
        """pid -> (cwd, cmdline) for every readable process."""
        table = {}
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace")
                table[int(pid)] = (cwd, cmd)
            except Exception:
                continue
        return table

    def is_running(self, bot, table):
        me = os.getpid()
        for pid, (cwd, cmd) in table.items():
            if pid == me or cwd != bot["dir"]:
                continue
            if any(tok in cmd for tok in bot["match"]):
                return pid
        return None

    def check_bot(self, bot, table):
        name = bot["name"]
        st = self.state.setdefault(name, {"attempts": []})
        if os.path.exists(os.path.join(BASE, "stop", name + ".stop")):
            return {"bot": name, "status": "skipped (stop marker)"}
        pid = self.is_running(bot, table)
        if pid:
            st["attempts"] = []
            return {"bot": name, "status": f"alive (pid {pid})"}
        # dead -> apply the anti-loop brake
        window = bot.get("window_sec", 3600)
        max_att = bot.get("max_attempts", 3)
        cooldown = bot.get("cooldown_sec", 300)
        att = [t for t in st.get("attempts", []) if now() - t < window]
        st["attempts"] = att
        if att and now() - att[-1] < cooldown:
            return {"bot": name, "status": f"dead — anti-loop cooldown ({len(att)}/{max_att})"}
        if len(att) >= max_att:
            if not st.get("capped_logged"):
                self.log(f"{name}: DEAD and the cap of {max_att} attempts/{window//60} min reached — stop trying, log only")
                st["capped_logged"] = True
            return {"bot": name, "status": "dead — attempt cap reached, not forced"}
        st.pop("capped_logged", None)
        att.append(now())
        st["attempts"] = att
        launcher = os.path.join(bot["dir"], bot["launcher"])
        try:
            with open(os.path.join(BASE, "launch.out"), "a") as out:
                subprocess.Popen(["bash", launcher], cwd=bot["dir"], stdout=out,
                                 stderr=subprocess.STDOUT, env=dict(os.environ),
                                 start_new_session=True)
            self.log(f"{name}: started via {bot['launcher']} (attempt {len(att)}/{max_att})")
            result = {"bot": name, "status": "started"}
        except Exception as e:
            self.log(f"{name}: FAILED to run launcher: {e}")
            result = {"bot": name, "status": f"failed to start: {e}"}
        return result

    def cycle(self):
        table = self.proc_table()
        results = [self.check_bot(b, table) for b in self.bots]
        self.save_state()
        status = {"ts": fmt(now()), "results": results}
        tmp = self.status_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(status, f, indent=1)
        os.replace(tmp, self.status_path)
        return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(BASE, "bots.json"))
    ap.add_argument("--state", default=os.path.join(BASE, "state.json"))
    ap.add_argument("--lock", default=os.path.join(BASE, "reviver.lock"))
    ap.add_argument("--status", default=os.path.join(BASE, "status.json"))
    ap.add_argument("--log", default=os.path.join(BASE, "reviver.log"))
    ap.add_argument("--interval", type=int, default=120)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    r = Reviver(args.config, args.state, args.lock, args.status, args.log)
    if args.once:
        for res in r.cycle():
            print(f"{res['bot']}: {res['status']}")
        return
    r.log(f"reviver started (interval {args.interval}s, {len(r.bots)} bots)")
    while True:
        try:
            r.cycle()
        except Exception as e:
            r.log(f"cycle error: {e}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
