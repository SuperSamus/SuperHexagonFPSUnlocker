# Neo Linux Patcher

The Neo Linux patcher targets the Neo Linux Steam build:

```text
File: SuperHexagon
SHA-256: 6f13c58d136b84df212cc23a560f7383e2f689005af18072e51d8a7439d2ba1d
Size: 2253968 bytes
```

It patches the known x86-64 build by byte signatures and refuses unknown layouts
unless `--force` is supplied.

The patch raises the game's frame-rate fields, updates the native frame
interval, and scales the expected frame delta so time-based gameplay logic stays
on the original 60 FPS cadence.

Unlike the Neo Windows patcher, this patcher does not add a new executable
section. It reuses part of the original `setGameFrameRate` code area as patch
space, so restoring a patched Linux executable requires the original `.bak`
backup. The patcher preserves Unix executable permissions when writing both the
patched file and the restored file.

Runtime diagnostics are not implemented for this patcher yet.
