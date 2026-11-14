#!/usr/bin/env python3
# analytics_feed.py — read-only analytics aggregator (adapted reference
# implementation from the production VM Control framework).
#
# Collects the newest numbers from the state files your own pipelines
# already write, and merges them into ONE structured analytics state
# (state.json) plus a human-readable digest (ringkasan.md, "summary" in
# Indonesian — rename freely). This is the data engine behind the
# Kantor/Office statistics tab of the VM Control Space: scorecard/KPI,
# charts, filters/slicers, detail tables and real-time indicators,
# grouped by work category.
#
# ABSOLUTELY READ-ONLY toward its sources: it never writes to a source,
# never edits a register, never ratifies anything. A source that is
# missing, unparseable, or older than its staleness threshold produces a
# flag file under flags/ and an ok:false entry — never a fabricated 0.
#
# Configure the SOURCES list below for your own pipelines, then run it
# from a timer (every few minutes is plenty; see schedules/SCHEDULES.md).
import json, os, re, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- config
TZ = ZoneInfo(os.environ.get("VM_CONTROL_TZ", "UTC"))
BASE = os.path.dirname(os.path.abspath(__file__))
STATE_F = os.path.join(BASE, "state.json")
OUT_F = os.path.join(BASE, "ringkasan.md")
LOG_F = os.path.join(BASE, "analytics-feed.log")
FLAG_DIR = os.path.join(BASE, "flags")

# One entry per pipeline state source.
#   name:     stable id used in state.json
#   category: work category the numbers belong to (drives the
#             statistics tab grouping in the Space)
#   path:     state file the pipeline itself writes
#   kind:     "json" (parsed as JSON) or "md-table" (markdown tables)
#   stale_sec: older than this -> flagged stale
SOURCES = [
    {"name": "revenue_tracker", "category": "Business",
     "path": "~/workspace/analytics/revenue-tracker.md",
     "kind": "md-table", "stale_sec": 26 * 3600},
    {"name": "pipeline_a", "category": "Web3",
     "path": "~/workspace/tools/pipeline-a/state.json",
     "kind": "json", "stale_sec": 26 * 3600},
    {"name": "pipeline_b", "category": "Web2",
     "path": "~/workspace/tools/pipeline-b/state.json",
     "kind": "json", "stale_sec": 3 * 3600 + 1800},
]

MONTHLY_TARGET = 0  # your monthly revenue target, in your currency; 0 = off


# ---------------------------------------------------------------- helpers
def now():
    return datetime.now(TZ)


def log(line):
    with open(LOG_F, "a", encoding="utf-8") as f:
        f.write(f"[{now().strftime('%Y-%m-%d %H:%M:%S %Z')}] {line}\n")


def parse_amount(cell):
    """'Rp1.250.000' / '$1,250' / '—' -> int or None."""
    c = (cell or "").strip()
    if c in ("", "—", "-", "–"):
        return None
    digits = re.sub(r"[^0-9]", "", c)
    return int(digits) if digits else None


def table_rows(lines):
    rows = []
    for ln in lines:
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue  # separator row
        rows.append(cells)
    return rows


def flag(name, problem):
    os.makedirs(FLAG_DIR, exist_ok=True)
    p = os.path.join(FLAG_DIR, f"{name}.flag")
    with open(p, "w", encoding="utf-8") as f:
        f.write(problem + "\n")


def unflag(name):
    p = os.path.join(FLAG_DIR, f"{name}.flag")
    if os.path.exists(p):
        os.unlink(p)


# ---------------------------------------------------------------- loading
def load_source(src):
    path = os.path.expanduser(src["path"])
    entry = {"name": src["name"], "category": src["category"],
             "ok": False, "at": None, "data": None, "problems": []}
    if not os.path.exists(path):
        entry["problems"].append(f"missing: {path}")
        return entry
    age = now().timestamp() - os.path.getmtime(path)
    if age > src["stale_sec"]:
        entry["problems"].append(f"stale: {int(age)}s > {src['stale_sec']}s")
    try:
        if src["kind"] == "json":
            with open(path, encoding="utf-8") as f:
                entry["data"] = json.load(f)
        else:
            with open(path, encoding="utf-8") as f:
                entry["data"] = {"tables": table_rows(f.readlines())}
        entry["at"] = datetime.fromtimestamp(
            os.path.getmtime(path), timezone.utc).astimezone(TZ).isoformat()
        entry["ok"] = not entry["problems"]
    except Exception as e:  # unparseable is a flag, never a crash
        entry["problems"].append(f"unparseable: {e}")
    return entry


# ---------------------------------------------------------------- main
def main():
    sources = {}
    for src in SOURCES:
        e = load_source(src)
        sources[src["name"]] = e
        if e["ok"]:
            unflag(src["name"])
        else:
            flag(src["name"], "; ".join(e["problems"]))
            log(f"{src['name']}: " + "; ".join(e["problems"]))
    state = {"tool": "analytics-feed", "at": now().isoformat(),
             "monthly_target": MONTHLY_TARGET, "sources": sources}
    tmp = STATE_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    os.replace(tmp, STATE_F)

    lines = [f"# Analytics summary — {now().strftime('%Y-%m-%d %H:%M %Z')}", ""]
    by_cat = {}
    for e in sources.values():
        by_cat.setdefault(e["category"], []).append(e)
    for cat, items in by_cat.items():
        lines.append(f"## {cat}")
        for e in items:
            mark = "OK" if e["ok"] else "FLAG: " + "; ".join(e["problems"])
            lines.append(f"- {e['name']}: {mark} (source at {e['at']})")
        lines.append("")
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    bad = [n for n, e in sources.items() if not e["ok"]]
    print(f"analytics-feed: {len(sources) - len(bad)}/{len(sources)} sources ok"
          + (f"; flagged: {', '.join(bad)}" if bad else ""))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
