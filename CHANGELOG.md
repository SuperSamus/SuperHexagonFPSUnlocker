# Changelog

## 0.1.0

- Added a source-only Windows Steam Super Hexagon patcher.
- Supported render choices: 60, 120, and 240 Hz.
- Kept gameplay simulation, collision timing, and timers at the original 60 Hz behavior.
- Added draw-time interpolation for selected visual state so 120/240 Hz rendering is not just repeated 60 Hz state.
- Added runtime diagnostics that count update, draw, and swap calls.
- Added migration support for earlier experimental patch states.
- Added unit tests that build synthetic PE images and validate patch layout.

No game files, Steam files, assets, DLLs, or copyrighted game data are included.
