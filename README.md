# SuperHexagonFPSUnlocker

Small binary patcher for the Windows Steam build of Super Hexagon.

It changes render pacing to 60, 120, or 240 Hz while keeping the game simulation at its original 60 Hz. A small draw hook interpolates selected visual state between fixed updates so gameplay speed, collision timing, and timers keep their original behavior. The patcher only modifies the user's local executable. It does not include or redistribute the game, Steam files, assets, DLLs, or copyrighted data.

## Supported Build

Current supported executable:

- Steam app ID: `221640`
- File: `SuperHexagon.exe`
- Size: `1467904` bytes
- SHA-256: `72b0c26053c37edd3435def461e9027cd6ffad12032db2fd0b32c256fdbee6b9`

If Steam updates the game, the hash may change. In that case the patcher will refuse to patch by default.

## Usage

Install Python 3, then run from this repository:

```powershell
python .\superhexagon_fps_unlocker.py status
python .\superhexagon_fps_unlocker.py patch --hz 240
python .\superhexagon_fps_unlocker.py patch --hz 120
python .\superhexagon_fps_unlocker.py patch --hz 60
python .\superhexagon_fps_unlocker.py diagnose --hz 240
python .\superhexagon_fps_unlocker.py unpatch
```

If auto-detection does not find the Steam install:

```powershell
python .\superhexagon_fps_unlocker.py --path "C:\Program Files (x86)\Steam\steamapps\common\Super Hexagon" patch --hz 240
```

The patcher writes a backup next to the executable before changing it:

```text
SuperHexagon.exe.bak.<hash-prefix>
```

Close the game before patching or unpatching.

`--hz 60` restores the original 60 Hz behavior. `unpatch` also restores the original executable layout.

`diagnose` temporarily instruments the executable, launches the game, counts update/draw/swap calls, then restores the executable bytes it started with. A healthy 240 Hz run should report about 60 update calls per second and about 240 draw/swap calls per second.

## Notes

- Disable in-game VSync if your monitor or driver is still limiting rendering to a lower refresh rate.
- This patch targets the Windows Steam executable only.
- Older versions of this repository either accelerated gameplay, only redrew repeated 60 Hz state, or missed part of the visual interpolation. This patcher detects those legacy states and migrates them before applying the current high-refresh render patch.
- Use `--force` only when you know the executable is signature-compatible with the supported build.
- See `docs/troubleshooting.md` if the status reports 120/240 IPS but the game still feels like 60 Hz.

## Development

Run the unit tests without needing the game files:

```powershell
python -m unittest discover -s tests
```

Do not commit a Steam install or patched executable. `.gitignore` excludes the local `Super Hexagon/` folder and common binary outputs.
