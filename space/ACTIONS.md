# VM Control — published action contracts

The Space is a Muse **web_fullstack** artifact. Everything the UI (or a
schedule, or the agent) can do goes through these published actions.
This list is the live contract of the production Space (32 actions);
keep names and semantics when you rebuild it.

## Home / status

| Action | Contract |
|---|---|
| `getvmstatus` | Live VM home status: host readings (hostname, uptime, CPU load, RAM, disk), the fleet `status.json` (bot fleets + systemd timers), and on-demand daemon port probes (e.g. wallet daemon, proxy forwarder). |
| `getsysinfo` | Live host info only: hostname, uptime, disk, RAM. |
| `gettaskstats` | Full analytics ("Data Analitik") grouped by work category — production grouping: Web3 (Dashboard Web3, Airdrop, NFT, Wallet) and Web2 (Clipper, Freelancer, Affiliate, Creator). Mapped live from each pipeline's host state files; an unreadable source surfaces as "Belum terdata" ("not yet recorded") **with the read error**, never as a zero. |
| `getoffice` | Current 3D office state (rooms, active agents, per-room stats). |
| `refreshoffice` | Recomputes and stores the office snapshot. This is the action the 1-minute refresh schedule calls; it must stay cheap and side-effect-free beyond its own tables. |

## File manager

All file actions take **virtual paths** rooted at the owner's home
(e.g. `workspace/tools`). The server enforces the root and a denylist
(see SPEC.md, "Guards") on every one of them.

| Action | Contract |
|---|---|
| `listdir` | Lists one VM folder, live from disk. |
| `readfile` | Reads one file for preview (text/image) or download (base64). |
| `savetextfile` | Overwrites an existing text file (preview Edit/Save); same root + denylist guards as reads. |
| `createtextfile` | Creates a new text file with the given content in a VM folder. |
| `createfolder` | Creates a folder inside a VM folder. |
| `renameitem` | Renames a file or folder in place. |
| `deleteitem` | Deletes a file or folder (folders recursively); the UI confirms first. |
| `uploadfile` | Uploads one file (base64, max 15 MB) into a VM folder. |
| `searchfiles` | Searches file/folder names under a VM folder (depth-limited live walk). |
| `storageinfo` | VM disk total and free bytes. |
| `listfavorites` / `addfavorite` / `removefavorite` | The owner's pinned files/folders, by virtual path. |

## Terminal

Sessions are real interactive bash shells held by a small persistent
PTY daemon per session, so a shell survives page reloads and keeps its
working directory and running processes.

| Action | Contract |
|---|---|
| `getbootstrap` | Terminal tabs, quick-command chips, and settings; seeds defaults on first run. |
| `createsession` / `deletesession` / `renamesession` | Tab lifecycle. Delete kills the shell and removes the tab and its history. |
| `ensuresession` | Starts (or reconnects to) the session's PTY daemon; returns live state and output offsets. |
| `termread` | Reads new raw PTY output bytes (base64) since a byte offset; also persists any finished commands the shell hook reported into the session history. |
| `termwrite` | Writes raw keystroke bytes (base64) into the PTY — typing, control keys, and paste all go through here. |
| `termresize` | Resizes the PTY (columns/rows) so full-screen programs redraw correctly. |
| `resetsession` | Restarts the session's PTY daemon (fresh interactive bash, same starting directory). |
| `listhistory` / `clearhistory` | Per-session command history, newest first. |
| `addquickcommand` / `deletequickcommand` | User quick-command chips (label + shell command). |

## Migration

| Action | Contract |
|---|---|
| `import_legacy_data` | One-time, idempotent import from the three predecessor Spaces (Virtual Office, File Manager, Terminal VM) into this combined Space. Only fills tables that are still empty; never overwrites. Safe to leave published; harmless when there is nothing to import. |
