# VM Control — build prompts

## Master build prompt (paste this to your Muse)

> Build a web_fullstack Space named "VM control" that merges a virtual
> office, a file manager, and a VM terminal into one Space, plus a new
> home page:
>
> - **Beranda (Home):** live VM status — host uptime, CPU/RAM/disk
>   rings, bot-fleet health read from `~/workspace/tools/fleet/status.json`,
>   systemd timers, on-demand daemon port probes, and an analytics
>   scorecard (collected cash vs monthly target, milestone curve).
> - **Kantor (Office):** a 3D virtual office — flat minimalist
>   soft-coloured L-shaped building, rounded ends, two staircases on
>   opposite sides, no pillars, a third-floor pool with a waterfall to
>   the first floor. Show only agents that are actually active. The
>   Kantor page also hosts a **Statistik tab**: the full analytics set
>   (scorecard KPI, charts, filters/slicers, detail tables, real-time
>   indicators) grouped by work category (mine are Web3: Dashboard
>   Web3, Airdrop, NFT, Wallet; Web2: Clipper, Freelancer, Affiliate,
>   Creator — adapt to yours), mapped live from each pipeline's host
>   state files; an unreadable source shows "not yet recorded" with the
>   read error, never a zero.
> - **File:** a file manager over the real VM filesystem using virtual
>   paths rooted at my home directory — list, preview, edit text in
>   place, create, rename, delete, upload (max 15 MB), search, disk
>   info, and pinned favorites. Enforce the root and a credential
>   denylist (`~/.ssh`, `~/.aws`, wallet vaults, `.env`, `*secret*`,
>   `*.pem`, `*.key`) on every file action.
> - **Terminal:** real interactive bash sessions in tabs, held by a
>   persistent PTY daemon per session (survives reloads), with
>   byte-offset output reads, raw keystroke writes, resize, per-session
>   command history, and quick-command chips.
>
> Design: iOS 26 Liquid Glass — big numbers, short labels, no
> descriptive paragraphs. Main navbar is a long floating glass capsule
> at the top (Beranda · Kantor · File · Terminal); each page's own
> sub-navbar is a floating pill at the bottom above a 20 px blur
> gradient, capsule above the blur. One shared dark/light toggle for
> the whole Space.
>
> Publish exactly the actions listed in ACTIONS.md of this repo, add a
> silent 1-minute space_action schedule that calls `refreshoffice`,
> and verify every page against live host data before reporting done.

## How the production Space was actually built (for reference)

The production Space grew in six steps. The original requests
(Indonesian, verbatim) are kept here because the *order* is the lesson:
merge first with appearances untouched, verify, then polish.

1. **Create (merge):** "Gabung juga jadi satu space, kantor virtual,
   file manager, terminal vm, seperti tadi dan tambahan halaman
   beranda status vm yang menampilkan status vm, vps dan runtime apa
   saja yang kamu handle. Beri nama spacenya " VM control""
2. **Edit:** "Tanpa mengubah tampilan space masing masing yang sudah
   ada ya. Serta sinkronisasi toggle darkmode seperti tadi ya" —
   carry pages over 1:1; unify only the shell and the theme toggle.
3. **Edit (File page fix):** "Waduh tolong geser keatas bar search di
   halaman file managenya itu bolong diatas di sisi navbar"
4. **Edit (statistics categories):** "Oh iya semua data statistik nya
   mulai dari web3 dan web2 Untuk statistik halaman tab perusahaan di
   kantor virtual ganti jadi sesuai kategori halaman task di web3 dan
   web2 nanti."
5. **Edit:** "Kembalikan statistik lengkap seperti sebelumnya.
   Maksudnya kategori nya sekarang bukan divisi lagi pada statistik
   data analitik" — restore the full analytics set; categories are
   work categories, not divisions.
6. **Edit (3D office repair):** "Perbaiki kantor virtual 3d hapus tiang
   tiangnya, dan pindahkan satu tangga kesisi lain jangan sejajar
   begitu. Ubah warna interior jadi flat minimlist warna soft.
   Pastikan yang tampil bekerja di kantor agent agent yang aktif saja,
   tolong sesuaikan."
