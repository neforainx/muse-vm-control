# Muse VM Control

A control room for a company that runs on a Muse VM: one Space that
merges **VM status**, a **3D virtual office with live analytics**, a
**file manager**, and a **persistent terminal** — backed by a small,
token-free script framework that keeps the VM's bot fleets alive and
its numbers honest.

Built and run in production on a live Muse VM since November 2026.
Packaged so any Muse user can install the same setup in their own VM.

![status](https://img.shields.io/badge/production-running-green) ![license](https://img.shields.io/badge/license-MIT-blue)

## What you get

**The Space (`space/`)** — a Muse `web_fullstack` artifact with 4
pages and 32 published actions:

- **Beranda** — host uptime, CPU/RAM/disk rings, fleet health, systemd
  timers, daemon probes, cash-vs-target scorecard.
- **Kantor** — a flat, soft-coloured 3D office (only active agents
  shown) plus the full analytics tab: KPI scorecard, charts,
  filters/slicers, detail tables, real-time indicators, grouped by
  work category.
- **File** — the VM's real filesystem: browse, preview, edit, upload,
  search, favorites — behind a root jail and a credential denylist.
- **Terminal** — real bash sessions in tabs on persistent PTY daemons,
  with history and quick-command chips.

**The backend (`backend/`)** — plain Python, zero Muse tokens:

- `fleet/` — a manifest-driven fleet checker: verifies every bot's
  processes *and* heartbeat freshness, writes `status.json` (the
  contract the Space reads), and flags dead fleets for revival.
- `reviver/` — a start-only, allowlisted reviver with flock and
  anti-loop caps (3 attempts/hour). It never kills anything.
- `analytics/` — a read-only aggregator that merges your pipelines'
  state files into one analytics state for the statistics tab.
  Missing/stale sources become flags with reasons — never fake zeros.
- `collectors/` — a host status collector (uptime, load, RAM, disk,
  localhost daemon probes) emitting the Beranda contract as JSON.

**The schedules (`schedules/`)** — the three cadences that keep it
alive: fleet check every 10 min (system), fleet revival every ±15 min
(agent cron — agent context is what gives launchers their network
egress), office refresh every 1 min (space action).

**Bundled framework (`datahub-rag/`)** — DataHub RAG, the
layered-context search box the VM's agent uses to read its own memory
tree and operations register for zero model tokens: a single-file
local RAG (`rag.py`), the official `rag.sh` launcher, a resident
daemon fast path (`daemon.py` + `ragd.sh`) with an exact fallback, a
fictional sample corpus, and its own README and systemd units. It
installs standalone — see `datahub-rag/README.md`.

## Quick start

Hand this repo to your Muse and say:

> Install VM Control from this repo: follow `install/SKILL.md`.

The skill walks your Muse through installing the backend, proving it
against your real bots, building the Space from `space/SPEC.md` +
`space/BUILD-PROMPTS.md`, wiring the schedules, and verifying
everything from inside the Space.

## Design language

iOS 26 Liquid Glass: big numbers, short labels, charts over
paragraphs. A long floating glass capsule navbar on top; each page's
sub-navbar is a floating pill at the bottom above a 20 px blur
gradient. One shared dark/light toggle. When pages are merged into one
Space, each page's own appearance is carried over 1:1 — only the shell
and the theme are unified.

## Security notes

- The Space contains a **real shell and real file access** — it is an
  owner-only tool. Never publish or share it.
- File actions are jailed to the home directory with a credential
  denylist (`~/.ssh`, `~/.aws`, wallet vaults, `.env`, `*secret*`,
  `*.pem`, `*.key`). The terminal is deliberately the owner's own
  shell.
- The reviver can only start the launchers listed in its own
  `bots.json`. Review that file like you'd review a sudoers file.

## Origin

Extracted from a live production system: the fleet layer survived
months of VM restarts (including a stale-pidfile incident class that
the cwd+cmdline process matching in `reviver.py` now guards against),
and the analytics layer's "flag, never fabricate" rule exists because
the owner would rather see *not yet recorded* than a confident wrong
number.

## License

MIT — see `LICENSE`. Use it, fork it, sell services on top of it.
