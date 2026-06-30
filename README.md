# SuperHexagonFPSUnlocker

Unified binary patcher for the Windows Steam build of Super Hexagon.

It supports both known Windows Steam executable families:

- Neo build: `SuperHexagon.exe`
- pre-Neo build: `superhexagon.exe`

The tool auto-detects the installed build, applies the matching backend, and
patches the executable in place. After patching once, launch the game normally
from Steam.

This repository does not include or redistribute the game, Steam files, DLLs,
assets, or patched executables.

## Quick Start

Install Python 3.10 or newer, then run from this repository:

```text
Double-click SuperHexagonFPSUnlocker.bat and choose a patch/restore option.
```

Or use commands:

```powershell
.\SuperHexagonFPSUnlocker.bat status
.\SuperHexagonFPSUnlocker.bat patch --hz 240
```

If Steam auto-detection does not find the install:

```powershell
.\SuperHexagonFPSUnlocker.bat --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon" patch --hz 240
```

Default menu choices:

```text
120, 240, 480
```

Custom command-line values are accepted when they are multiples of `60` and at
least `120`.

`60 Hz` is handled through restore:

```powershell
.\SuperHexagonFPSUnlocker.bat restore
```

## Commands

Double-clicking `SuperHexagonFPSUnlocker.bat` opens an interactive menu:

```text
120, 240, 480, custom, restore, status
```

The same launcher also accepts command-line arguments:

```powershell
.\SuperHexagonFPSUnlocker.bat status
.\SuperHexagonFPSUnlocker.bat patch --hz 120
.\SuperHexagonFPSUnlocker.bat patch --hz 240
.\SuperHexagonFPSUnlocker.bat patch --hz 480
.\SuperHexagonFPSUnlocker.bat patch --hz 960
.\SuperHexagonFPSUnlocker.bat diagnose --hz 240 --seconds 5 --warmup 2
.\SuperHexagonFPSUnlocker.bat restore
```

The patcher writes a backup next to the executable before changing it:

```text
SuperHexagon.exe.bak.<hash-prefix>
superhexagon.exe.bak.<hash-prefix>
```

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

```powershell
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
```
