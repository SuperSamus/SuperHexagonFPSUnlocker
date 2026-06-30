# Release Checklist

Use this before tagging or publishing a GitHub release.

## Source checks

```powershell
python -m unittest discover -s tests
python .\superhexagon_fps_unlocker.py status
```

Confirm that `git status --short` does not include:

- `Super Hexagon/`
- `SuperHexagon.exe`
- `*.dll`
- backup executables

## Runtime checks on the supported Steam build

Close the game before each patch command.

```powershell
python .\superhexagon_fps_unlocker.py unpatch
python .\superhexagon_fps_unlocker.py patch --hz 120
python .\superhexagon_fps_unlocker.py diagnose --hz 120
python .\superhexagon_fps_unlocker.py patch --hz 240
python .\superhexagon_fps_unlocker.py diagnose --hz 240
```

Expected diagnostic shape:

- update stays near 60/s
- draw stays near selected Hz
- swap stays near selected Hz

## GitHub release notes

Mention:

- Supported executable size and SHA-256.
- Supported refresh options.
- That the game simulation remains 60 Hz.
- That no game files are included.
- How to unpatch or verify files through Steam.
