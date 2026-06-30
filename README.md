# SuperHexagonFPSUnlocker

Unified binary patcher for the Windows Steam build of Super Hexagon.

It supports both known Windows Steam executable families:

- Neo build: `SuperHexagon.exe`
- pre-Neo build: `superhexagon.exe` or `SuperHexagon.exe`

The tool auto-detects the installed build, applies the matching backend, and
patches the executable in place. After patching once, launch the game normally
from Steam.

This repository does not include or redistribute the game, Steam files, DLLs,
assets, or patched executables.

## Quick Start

Install Python 3.10 or newer, then run from this repository:

```powershell
.\SuperHexagonFPSUnlocker.bat status
.\SuperHexagonFPSUnlocker.bat patch --hz 240
```

If Steam auto-detection does not find the install:

```powershell
.\SuperHexagonFPSUnlocker.bat --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon" patch --hz 240
```

Available patch refresh choices:

```text
120, 180, 240, 300, 360
```

`60 Hz` is handled through restore:

```powershell
.\SuperHexagonFPSUnlocker.bat restore
```

## Commands

```powershell
.\SuperHexagonFPSUnlocker.bat status
.\SuperHexagonFPSUnlocker.bat patch --hz 120
.\SuperHexagonFPSUnlocker.bat patch --hz 180
.\SuperHexagonFPSUnlocker.bat patch --hz 240
.\SuperHexagonFPSUnlocker.bat patch --hz 300
.\SuperHexagonFPSUnlocker.bat patch --hz 360
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
- `120` and `240` are the most tested modes. `180`, `300`, and `360` are
  exposed because they are multiples of 60, but they should be treated as
  experimental until they are tested across both build families.

## Development

Run a basic syntax check:

```powershell
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
```
