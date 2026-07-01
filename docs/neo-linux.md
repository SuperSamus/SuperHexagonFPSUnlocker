# Neo Linux Backend

The Neo Linux backend targets the native Steam `SuperHexagon` ELF64 executable.
It patches the known x86-64 build by byte signatures and refuses unknown layouts
unless `--force` is supplied.

The patch raises the game's frame-rate fields, updates the native frame
interval, and scales the expected frame delta so time-based gameplay logic stays
on the original 60 FPS cadence.

Unlike the Windows Neo backend, this backend does not add a new executable
section. It reuses part of the original `setGameFrameRate` code area as patch
space, so restoring a patched Linux executable requires the original `.bak`
backup. The patcher preserves Unix executable permissions when writing both the
patched file and the restored file.

Runtime diagnostics are not implemented for this backend yet.
