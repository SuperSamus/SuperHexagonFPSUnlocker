# Usage

## Run

Recommended from the repository:

```text
uv run superhexagon-fps-unlocker
```

Classic Python install:

```text
python -m pip install .
superhexagon-fps-unlocker
```

If the project is installed with pip, remove the `uv run` prefix from commands.

This repository does not include or redistribute the game, Steam files, DLLs,
assets, or patched executables.

## Commands

```text
uv run superhexagon-fps-unlocker status
uv run superhexagon-fps-unlocker patch --fps 120
uv run superhexagon-fps-unlocker patch --fps 240
uv run superhexagon-fps-unlocker patch --fps 360
uv run superhexagon-fps-unlocker patch --fps 480
uv run superhexagon-fps-unlocker patch --fps 960
uv run superhexagon-fps-unlocker diagnose --fps 240 --seconds 5 --warmup 2
uv run superhexagon-fps-unlocker restore
```

`120`, `240`, `360`, and `480` are the default menu choices. Custom values must be
multiples of `60` and at least `120`.

`60 FPS` is handled by restoring the original executable:

```text
uv run superhexagon-fps-unlocker restore
```

## Manual Path

If Steam auto-detection does not find the install:

```text
uv run superhexagon-fps-unlocker --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon" patch --fps 240
```

## Backups

The patcher writes one backup next to the executable before changing it:

```text
SuperHexagon.exe.bak
superhexagon.exe.bak
SuperHexagon.bak
```

Existing old `*.bak.<hash-prefix>` backups are left untouched. If a valid
original backup is found there, the patcher migrates it to the stable `.bak`
name.

If the stable `.bak` belongs to a different build, the patcher replaces it with
an original executable for the currently detected build.

The native Linux backend needs a valid `.bak` to restore because it reuses part
of the original executable as patch space. `--no-backup` is accepted there only
when a valid `SuperHexagon.bak` already exists.

## Current Backends

Current patch backends target these Steam executables:

- Neo build: `SuperHexagon.exe`
- Pre-Neo build: `superhexagon.exe`
- Neo Linux build: `SuperHexagon`

The native Linux backend is signature-based and currently targets the known
Steam ELF64 build.

Unknown builds are refused by default. Use `--force` only when you know the byte
signatures match.

Runtime diagnostics are currently implemented for the Windows backends only.

## How It Works

The patch keeps gameplay simulation on the original fixed cadence and runs
rendering at a higher cadence. Visual state is interpolated during draw so the
game does not simply run faster.

Neo and Pre-Neo are different binaries, so they use separate patch backends.
