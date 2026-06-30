# SuperHexagonFPSUnlocker

FPS Unlocker for Super Hexagon on Steam.

## Usage

Install Python 3.10+ and `uv`, then run from this folder:

```text
uv run superhexagon-fps-unlocker
```

Choose `120`, `240`, `480`, a custom refresh rate, restore, or status from the
menu.

## Commands

```text
uv run superhexagon-fps-unlocker patch --hz 240
uv run superhexagon-fps-unlocker restore
uv run superhexagon-fps-unlocker status
```

Custom values must be multiples of `60` and at least `120`.

## Game Not Found

Pass the Super Hexagon install folder manually:

```text
uv run superhexagon-fps-unlocker --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon"
```

## Notes

Close the game before patching or restoring.

The patcher creates one `.bak` backup next to the executable.

## Docs

- [Usage](docs/usage.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Neo backend](docs/neo.md)
- [Pre-Neo backend](docs/pre-neo.md)
