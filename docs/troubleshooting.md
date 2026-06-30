# Troubleshooting

## The game says 240 IPS but still feels like 60 Hz

Run the diagnostic command:

```powershell
.\SuperHexagonFPSUnlocker.bat diagnose --hz 240
```

A healthy 240 Hz result should be close to:

```text
update: 60/s
draw:   240/s
swap:   240/s
```

If update is near 60/s but draw or swap is near 60/s, something outside the simulation loop is still limiting presentation.

Check these first:

- Make sure Windows is set to the monitor's high refresh mode.
- Disable in-game VSync.
- Check the GPU driver control panel for forced VSync, frame caps, or half-refresh modes.
- Try borderless/windowed vs fullscreen if your setup forces different presentation behavior.
- Close overlays or capture tools that may force a lower present rate.

## The game runs too fast

That usually means an older speedup patch is still installed or the executable was patched by another tool.

Run:

```powershell
.\SuperHexagonFPSUnlocker.bat status
```

Then apply the current patch again:

```powershell
.\SuperHexagonFPSUnlocker.bat patch --hz 240
```

The current patch keeps the simulation cadence at the original rate. Only render
pacing and draw-time interpolation are changed.

## The patcher says the executable is unsupported

This patcher is signature-based and targets a known Windows Steam build. If Steam updates the game or the file was modified, the SHA-256 hash can change.

Recommended recovery:

1. In Steam, verify the integrity of the game files.
2. Run `.\SuperHexagonFPSUnlocker.bat status`.
3. If the file is still unsupported, open an issue with the executable size, SHA-256, and command output.

Use `--force` only if you have confirmed the executable is layout-compatible with the supported build.

## I want to remove the patch

Use:

```powershell
.\SuperHexagonFPSUnlocker.bat restore
```

Or restore the file through Steam's integrity check.
