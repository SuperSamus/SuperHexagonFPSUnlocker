# SuperHexagonFPSUnlocker

FPS Unlocker for Super Hexagon on Steam.

## Usage

Install Python 3.10+ and `uv`, then run from this folder:

```text
uv run superhexagon-fps-unlocker
```

Choose to patch at `120 FPS`, `240 FPS`, `480 FPS`, or a custom FPS value,
restore the original executable, or check the current status from the menu!

## Commands

```text
uv run superhexagon-fps-unlocker status
uv run superhexagon-fps-unlocker restore
uv run superhexagon-fps-unlocker patch --fps 360
```

Custom FPS values must be multiples of `60` and at least `120`.

## Notes

Close the game before patching or restoring.

The patcher creates or refreshes one `.bak` backup next to the executable.

## Docs

- [Usage](docs/usage.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Neo backend](docs/neo.md)
- [Pre-Neo backend](docs/pre-neo.md)
