# VM Control — Space specification

A single Muse **web_fullstack** Space that merges four tools into one
surface for running a company on a Muse VM:

1. **Beranda (Home) — VM status.** Host readings (uptime, CPU/RAM/disk
   rings), bot-fleet health, systemd timers, on-demand daemon probes,
   plus the analytics scorecard: collected cash vs the monthly target
   and the milestone curve.
2. **Kantor (Office) — a 3D virtual office.** A flat, minimalist,
   soft-coloured L-shaped building (rounded ends, two staircases on
   opposite sides, a third-floor pool with a waterfall to the first
   floor, **no pillars**). Only agents that are actually active appear
   in it. Each room carries the live statistics of its work category.
   The Kantor page hosts the **Statistik tab**: the full analytics set
   (scorecard KPI, charts, filters/slicers, detail tables, real-time
   indicators) grouped by the current work categories — categories are
   *work categories*, not org-chart divisions.
3. **File — a file manager** over the VM's real filesystem (virtual
   paths rooted at the home directory), with favorites, search,
   upload/download, and in-place text editing.
4. **Terminal — real interactive shells** in browser tabs (persistent
   PTY daemons, command history, quick-command chips).

## Design standard (the owner's house style — keep it)

- **Liquid Glass, iOS 26 style:** big numbers, short labels, charts and
  rings, **no descriptive paragraphs** in the UI.
- **Main navbar:** a long floating glass capsule pill at the **top**,
  detached from the edges (blur + saturate + highlight + shadow):
  `Beranda · Kantor · File · Terminal`.
- **Per-page sub-navbars:** a floating pill at the **bottom**, above a
  20 px bottom blur gradient; the capsule renders **above** the blur
  layer.
- **One shared dark/light theme toggle** for the whole Space. When
  merging pre-existing pages into one Space, carry each page over 1:1
  without changing its own appearance — unify only the shared shell
  and the single theme toggle.

## Pages carried over 1:1

VM Control is a merge of three earlier Spaces (Virtual Office, File
Manager, Terminal VM): all 32 actions and the existing records carried
over unchanged, verified after import (`import_legacy_data`), and only
then were the old Spaces deleted. If you build fresh, you can skip the
migration action; if you merge existing Spaces, this order matters:
**merge → verify the data arrived → delete the originals.**

## Guards (do not weaken these)

- File actions resolve **virtual paths under the home root only**;
  `..` escapes are rejected.
- A **denylist** blocks credential material from read/write actions:
  wallet vault directories, `~/.ssh`, `~/.aws`, `~/.gnupg`,
  `.env` / `*secret*` / `*.pem` / `*.key` files, and the Secure Vault.
  The terminal is the owner's own shell and is intentionally not
  denylisted — which is why this Space is owner-only and must never be
  shared publicly.
- Uploads are capped at **15 MB** per file.
- Unreadable data sources render as "not yet recorded" **with the
  error shown** — never as invented zeros. Paper/projected figures are
  labelled as such; only collected cash counts as revenue.

## Data the Space reads from the host

| Source | Read by | Producer |
|---|---|---|
| `~/workspace/tools/fleet/status.json` | `getvmstatus` | `backend/fleet/fleet_check.py` (10-minute timer) |
| Each pipeline's own state files | `gettaskstats` | Your pipelines; aggregated by `backend/analytics/analytics_feed.py` |
| Host `/proc`, `statvfs`, TCP probes | `getvmstatus`, `getsysinfo` | Live reads (reference: `backend/collectors/vm_status.py`) |
| Its own tables | Office, Terminal, Favorites | The Space itself (sessions, history, chips, favorites, office snapshots) |

## Refresh

A **1-minute space_action schedule** calls `refreshoffice` silently
(see `schedules/SCHEDULES.md`). Everything else is read live on open,
so the Space stays truthful even if the refresh stalls.
