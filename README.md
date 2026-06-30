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
uv run superhexagon-fps-unlocker status
uv run superhexagon-fps-unlocker restore
uv run superhexagon-fps-unlocker patch --hz 240
```

Custom Hz values must be multiples of `60` and at least `120`.

## Notes

Close the game before patching or restoring.

The patcher creates one `.bak` backup next to the executable.

## Docs

- [Usage](docs/usage.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Neo backend](docs/neo.md)
- [Pre-Neo backend](docs/pre-neo.md)
