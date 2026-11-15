# Space spec — Pengendali VNC (VNC Controller)

A phone-first Space that remote-controls the VM's real desktop through
the bridge in `bridge/`. Build it **exactly** as specified here — in
production this page was rebuilt several times, and every deviation
(extra buttons, extra fields, a different gesture map) was rejected.
The whole value of the page is that it feels like touching the desktop
itself: frames out, input in, nothing else on screen.

## Layout — non-negotiable

- The desktop frame fills the whole page (1280×800, letterboxed).
- **Exactly two buttons: `Copy` and `Paste`.** Nothing else.
  - **No Keyboard button. Ever.**
  - **No visible text input field** anywhere on the page.
  - No URL bar, no tab strip, no settings, no status paragraphs.
- Dark, neutral chrome; the frame is the interface.

## Actions — exactly three

| Action | Bridge call | Contract |
|---|---|---|
| `getframe` | `GET http://127.0.0.1:5901/frame` (+ `/health`) | returns the latest frame image + `seq`; the client polls it on a short interval and swaps the image only when `seq` changed |
| `getclipboard` | `GET http://127.0.0.1:5901/clipboard` | returns the VM clipboard text |
| `sendinput` | `POST http://127.0.0.1:5901/input` | forwards one input event: `pointer` / `key` / `scroll` / `type` (see `bridge/README.md`) |

No other actions. In particular, do **not** add screenshot actions,
browser-control actions, or a second input channel — interactivity
breaks when input and frames travel different paths.

## Buttons

- **Copy** — calls `getclipboard` and writes the returned text to the
  phone's clipboard.
- **Paste** — reads the phone's clipboard and sends it as one
  `{"type":"type","text":...}` event through `sendinput`, so the text
  is typed into whatever field is focused in the VM.

## Gesture map — exact

| Gesture on the frame | Sent to the VM |
|---|---|
| Tap | left click at that point (pointer down+up) |
| Drag (one finger) | pointer move with button held (drags windows/text) |
| Long press / hold | right click |
| Pinch | zoom the *view* up to 3.5× (client-side only; never sent) |
| Two-finger scroll | scroll events at that point |
| Double-tap on a text field (≤400 ms, ≤48 px apart) | opens the **phone keyboard**; typed characters are forwarded as key/type events. This replaces any Keyboard button — do not add one. |

Touch coordinates are scaled from the displayed frame back to the
1280×800 desktop coordinate space before sending.

## Smoothness requirements

- Poll `getframe` continuously while the page is open; render each new
  `seq` immediately (no transitions, no fade).
- Send pointer-move events during a drag as a stream, not only on
  release — the desktop must track the finger.
- If `/health` reports a stale `frame_age_ms`, show the last frame and
  keep polling; never replace the frame with an error page.

## Verification (from inside the Space)

1. Open the page: the real desktop is visible and alive (clock/page
   changes appear without reloading).
2. Tap a button on a web page in the frame — it clicks.
3. Drag — the desktop follows your finger.
4. Double-tap a text field, type on the phone keyboard — the text
   lands in the VM field.
5. Select text in the VM, tap **Copy** — the phone clipboard has it.
   Tap **Paste** in another field — it appears.
