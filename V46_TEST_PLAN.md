# v46 — REAL one-VD CarPlay vs dual-VD IME composition A/B

Version: `0.3#17.8-v46`, code `3146`. Base: pinned lagXkjy/AADisplay commit `494dcc4909e8765e8798be4e7b8031fefd90a4eb` with v2–v46 patches applied in order.

## Why this experiment

Nitsuya's original Android Auto implementation creates **one** VirtualDisplay and sends its Surface directly to Android Auto's TextureView. Our CarPlay host creates **two** independent virtual displays; SurfaceTexture/GLES combines them and MediaCodec encodes that composite. Captures on the user's HyperOS show Gboard visible/drawn as a SurfaceFlinger layer but missing from the per-VD **Output Layer** list; sometimes the temporary `IME-screenshot-surface` participates instead. v45 IME parent hooks were installed but did not record a successful parent change.

This build isolates one structural variable first: **one real VirtualDisplay** (secondary ID is `Display.INVALID_DISPLAY`, not a hidden second display). Same flags, LOCAL IME policy, Host GLES/encoder and CarPlay connectivity as dual baseline. A second switch separately recreates Nitsuya's non-focusable, non-touchable transparent 0×0 overlay window. No global Greezer change or package allowlist.

## Modes (read when Host + system_server split controller create their displays)

| Test | `debug.carplay.v46_single_vd` | `debug.carplay.v46_anchor_window` | Meaning |
|---|---:|---:|---|
| A | 0 | 0 | Original v45 dual VD baseline |
| B | 1 | 0 | **Exactly one** primary VD, full 1280×720 (or negotiated size) |
| C | 1 | 1 | One VD + Nitsuya-style 0×0 transparent window |

**Do not mix these with v28/v41/v44/v45 IME surface experiments.** In all A/B/C cases disable prior experiments:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v45_ime_parent_policy 0; setprop debug.carplay.v45_ime_diag 0; setprop debug.carplay.v43_ime_freeze_guard 0'
```

### Test B: one VD, no anchor

1. Install v46 and reboot Android for LSPosed code.
2. **Before connecting CarPlay**, run:

```sh
su -c 'setprop debug.carplay.v46_single_vd 1; setprop debug.carplay.v46_anchor_window 0'
```

3. Connect CarPlay. The screen is deliberately full-width primary only; there is no right pane, split divider or peel gesture. Open Via/MT Manager on the visible primary display; try the same input field with phone locked and unlocked.
4. Check both keyboard **visibility and touch**. A single-VD test that simply blanks half the screen is invalid: inspect log for `v46 topology realSingle=true ... secondaryId=-1`.

### Test C: one VD with original-style window

Disconnect and fully destroy the old CarPlay Host and virtual displays (a phone reboot followed by `setprop` before reconnect is the most reliable way to avoid delayed-destroy reuse). Then run:

```sh
su -c 'setprop debug.carplay.v46_single_vd 1; setprop debug.carplay.v46_anchor_window 1'
```

Reconnect, try the same field, and verify the `v46 original 0x0 anchor installed` log. If you see `optional original anchor failed`, this test did not enable the window; do not treat it as successful C.

### Test A: normal dual VD baseline

Reboot/destroy previous VDs, then:

```sh
su -c 'setprop debug.carplay.v46_single_vd 0; setprop debug.carplay.v46_anchor_window 0'
```

Reconnect and verify `v46 topology realSingle=false` with two **different** valid display IDs. Repeat the same keyboard scenario.

**Note:** `setprop` values are typically non-persistent across reboot. Re-enter them after reboot, before connecting; do not change modes mid-session. Restoring dual mode does not require reinstalling the APK.

## Capture each test independently

Run when an input field is focused, preferably immediately after the keyboard is expected to show. Change `MODE` to A, B or C before each capture:

```sh
su -c '(
 MODE=B
 OUT=/sdcard/Download/v46_$MODE
 mkdir -p "$OUT"
 date > "$OUT/time.txt"
 getprop debug.carplay.v46_single_vd > "$OUT/single.txt"
 getprop debug.carplay.v46_anchor_window > "$OUT/anchor.txt"
 dumpsys display > "$OUT/display.txt"
 dumpsys input_method > "$OUT/ime.txt"
 dumpsys window displays > "$OUT/window.txt"
 dumpsys SurfaceFlinger --layers > "$OUT/sf_layers.txt" 2>&1
 logcat -b main -b system -d -v threadtime |
   grep -iE "AAD_V46Mode|v46 topology|v46 original|v46 single|AADisplay_SplitDisplayController|MiuiMirrorInputMethodImpl|AAD_VdImeDisplayPin" |
   tail -500 > "$OUT/events.txt"
 tar -czf /sdcard/Download/v46_$MODE.tar.gz -C /sdcard/Download v46_$MODE
)'
```

Upload `v46_A.tar.gz`, `v46_B.tar.gz`, and optionally `v46_C.tar.gz`; note locked/unlocked, visible/invisible, and touch working/not working for each.

## How to interpret results

- **B works while A fails:** dual-display topology/focus or IME window ownership is implicated. Next isolate dual VDs but one active client; avoid guessing surface layer changes.
- **B fails, C works:** original zero-size overlay/context is implicated, and must be isolated from unrelated flags.
- **B and C fail:** single-vs-dual and original anchor alone are insufficient. Compare true InputMethod layer Output Layer membership to trace WindowManager/SF composition; GL/encoder is secondary.
- **Keyboard appears only on phone Display 0:** this is not success; LOCAL on VD must remain confirmed.
- **B has two AADisplay VDs:** test is invalid due to stale session/flags; fully destroy VDs and recapture.

## Boundaries

- No fix claimed in advance; experiment default OFF.
- Any unexpected app/window effect: disconnect CarPlay, set both v46 properties to 0, and fully restart Host or reboot.
- Greezer/HyperOS background freezing is a separate concern; no blanket exemptions added.
- Pre-existing v23 IPv4 gateway fast-ready, v39 network lifecycle and v40 lean defaults are unchanged.

Original source: https://github.com/Nitsuya/AADisplay/blob/main/aa-display/src/main/java/io/github/nitsuya/aa/display/ui/aa/AaVirtualDisplayAdapter.kt
