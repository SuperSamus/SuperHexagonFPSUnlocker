# SuperHexagonFPSUnlocker

FPS Unlocker for Super Hexagon, supporting Windows and Linux builds. Compatible with Steam Deck OLED!

## Usage

Install Python 3.10+ and `uv`, then run from this folder:

```text
uv run superhexagon-fps-unlocker
```

Choose to patch at `120 FPS`, `240 FPS`, `360 FPS`, `480 FPS`, or a custom FPS value!

## Commands

```text
uv run superhexagon-fps-unlocker status
uv run superhexagon-fps-unlocker restore
uv run superhexagon-fps-unlocker patch --fps 960
```

Custom FPS values must be multiples of `60` and at least `120`.

## Notes

Close the game before patching or restoring.

The patcher creates or refreshes one `.bak` backup next to the executable.

The patcher supports the Neo Windows, Neo Linux, and Pre-Neo Windows Steam builds.

## Docs

- [Usage](docs/usage.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Neo Windows patcher](docs/neo.md)
- [Neo Linux patcher](docs/neo-linux.md)
- [Pre-Neo Windows patcher](docs/pre-neo.md)
