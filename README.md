# SuperHexagonFPSUnlocker

Unified binary patcher for the Windows Steam executable of Super Hexagon.

The patcher itself runs on Windows and Linux/Steam Deck. On Linux, it patches
the Windows executable used by Steam Play/Proton.

It supports both known Windows Steam executable families:

- Neo build: `SuperHexagon.exe`
- pre-Neo build: `superhexagon.exe`

The tool auto-detects the installed build, applies the matching backend, and
patches the executable in place. After patching once, launch the game normally
from Steam.

This repository does not include or redistribute the game, Steam files, DLLs,
assets, or patched executables.

## Quick Start

Install Python 3.10 or newer.

Recommended from this repository with `uv`:

```text
uv run superhexagon-fps-unlocker
```

That opens the interactive menu:

```text
120, 240, 480, custom, restore, status
```

Classic Python install from this repository:

```text
python -m pip install .
superhexagon-fps-unlocker
```

The examples below use `uv run`. If the project is installed with pip, remove
the `uv run` prefix and call `superhexagon-fps-unlocker` directly.

If Steam auto-detection does not find the install:

```text
uv run superhexagon-fps-unlocker --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon" patch --hz 240
```

Default menu choices:

```text
120, 240, 480
```

Custom command-line values are accepted when they are multiples of `60` and at
least `120`.

`60 Hz` is handled through restore:

```text
uv run superhexagon-fps-unlocker restore
```

## Commands

Running without a subcommand opens the interactive menu:

```text
uv run superhexagon-fps-unlocker
```

The same entry point also accepts command-line arguments:

```text
uv run superhexagon-fps-unlocker status
uv run superhexagon-fps-unlocker patch --hz 120
uv run superhexagon-fps-unlocker patch --hz 240
uv run superhexagon-fps-unlocker patch --hz 480
uv run superhexagon-fps-unlocker patch --hz 960
uv run superhexagon-fps-unlocker diagnose --hz 240 --seconds 5 --warmup 2
uv run superhexagon-fps-unlocker restore
```

The patcher writes one stable backup next to the executable before changing it:

```text
SuperHexagon.exe.bak
superhexagon.exe.bak
```

Existing old `*.bak.<hash-prefix>` backups are left untouched. If a valid
original backup is found there, the patcher migrates it to the stable `.bak`
name.

Close the game before patching or restoring.

## How It Works

The patch keeps gameplay simulation on the original fixed cadence and runs
rendering at a higher cadence. Visual state is interpolated during draw so the
game does not simply run faster.

Neo and pre-Neo are different binaries, so they use separate patch backends.
The launcher only chooses the backend and forwards the command.

## Supported Builds

Neo:

```text
SHA-256: 72b0c26053c37edd3435def461e9027cd6ffad12032db2fd0b32c256fdbee6b9
Size: 1467904 bytes
```

pre-Neo:

```text
SHA-256: 69411cb275202b21c3e0428a5c27704e97663a17723497b61bd7dfeaa1534bdd
Size: 2698240 bytes
```

Unknown builds are refused by default. Use `--force` only when you know the
byte signatures match.

## Notes

- Disable in-game VSync if your monitor or driver still limits rendering.
- Steam file verification or game updates can restore the original executable.
  Re-run `patch --hz 240` after that.
- `120`, `240`, and `480` are the default menu choices. Any multiple of `60`
  from `120` upward is accepted as a custom value, but very high values should
  be treated as experimental until tested on your setup.

## Development

Run a basic syntax check:

```text
uv run python -m compileall -q src
```
