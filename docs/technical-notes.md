# Technical Notes

The supported Windows Steam executable is a 32-bit PE file. Its main loop uses SDL performance counters and initializes fixed timing intervals from `QueryPerformanceFrequency()`.

Relevant addresses for SHA-256 `72b0c26053c37edd3435def461e9027cd6ffad12032db2fd0b32c256fdbee6b9`:

- `0x4325df`: original `push 0xfa`, used to initialize `[timer+0xb8/0xbc]`. The patch changes this render divisor to `frequency / refresh`.
- `0x43263f`: original `push 0x3c`, the simulation divisor. The current patch leaves this unchanged, so the fixed update loop remains 60 Hz.
- `0x4291e4`: original `cmp dword ptr [esi+0x40cc8], 0x3c`. The current patch leaves this unchanged because the simulation still runs at 60 Hz.
- `0x43996b`, `0x4399de`, `0x439b73`: counter accumulation hooks. They keep adding elapsed time to the original simulation accumulator and also add it to a separate render accumulator stored at `[timer+0x4d0/0x4d4]`.
- `0x439cee`: render-end hook. It subtracts one render interval from the render accumulator after a frame is presented.
- `0x431000`: update entry hook. The hook stores the previous tick's `[game+0x1a0]` rotation offset in `.shfps` before running the original update prologue. Diagnostic mode also increments the update counter here.
- `0x430c50`: draw entry hook. The hook temporarily advances visual phase field `[game+0x2924]`, wall angle offset `[game+0x29b8]`, rotation offset `[game+0x1a0]`, and active obstacle segment distances at `[game+0x214 + n*0x14]` by the fractional simulation accumulator, calls the original draw body at `0x42fe40`, then restores the original values. Segment movement mirrors the update branch: when `[game+0x2970] <= 1.0`, delta is `fraction * 5.0 * [game+0x2970]`; otherwise, when `[game+0x54b0] <= 0`, delta is `fraction * [game+0x2968]`. The draw body returns with a plain `ret`, so the wrapper calls it directly and returns normally.
- `0x44dbc0`: diagnostic-only swap hook. It counts presented frames while preserving the original `FNA3D_SwapBuffers` prologue.

The original loop uses one accumulator for both waiting and simulation. A render-only patch can report `240 IPS`, but the visible game state still changes at 60 Hz because the draw routine reads the latest discrete simulation state directly. Running the entire update loop at 120/240 Hz is also wrong because some gameplay paths are tick-based and speed up. The current patch keeps update at 60 Hz, runs draw at the selected refresh, and interpolates visual state only during rendering. The `.shfps` section is writable because the normal patch stores the previous tick rotation offset there.

Runtime diagnostics should show update staying near 60/s while draw and swap match the chosen render refresh. On the local supported build, measured runs were about 60 update calls/s with about 240 draw/swap calls/s at 240 Hz, and about 60 update calls/s with about 120 draw/swap calls/s at 120 Hz.

Refresh choices:

- `60`: original executable layout, no `.shfps` section.
- `120`: render interval uses `frequency / 120`; simulation interval remains `frequency / 60`.
- `240`: render interval uses `frequency / 240`; simulation interval remains `frequency / 60`.

Legacy states:

- `legacy-speedup`: older v1 patch used `0x432653` and `0x4326d3` to overwrite the simulation divisor.
- `legacy-render-only`: older v2 patch paced rendering at 120/240 Hz but left the draw path on repeated 60 Hz state.
- `legacy-high-tick`: older experiment ran update above 60 Hz and patched one known 60-tick threshold, but still accelerated gameplay.
- `legacy-no-wall-angle`: older interpolation patch left `[game+0x29b8]` on 60 Hz state.
- `legacy-no-rotation-offset`: older interpolation patch left `[game+0x1a0]` on 60 Hz state and may have the stale draw-hook stack layout that overlapped the saved wall angle with the fractional accumulator.

Applying the current patch migrates these legacy states before installing the high-refresh render/interpolation patch.
