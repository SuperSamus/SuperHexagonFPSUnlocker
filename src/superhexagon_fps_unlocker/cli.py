from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from . import __version__
from . import steam
from .patchers import neo, pre_neo


PRESET_REFRESH_CHOICES = (120, 240, 480)
MIN_PATCH_REFRESH_HZ = 120
REFRESH_HZ_STEP = 60

GOOD_STATES = {"original", "patched", "diagnostic"}
NEO_LEGACY_STATES = {
    "legacy-no-rotation-offset",
    "legacy-no-wall-angle",
    "legacy-speedup",
    "legacy-render-only",
    "legacy-high-tick",
}


class CliError(RuntimeError):
    """Raised when the unified launcher cannot choose or run a backend."""


@dataclass(frozen=True)
class Backend:
    key: str
    label: str
    module: ModuleType


@dataclass(frozen=True)
class Detection:
    path: Path
    backend: Backend
    state: object
    score: int


BACKENDS = {
    "neo": Backend("neo", "Neo Steam build", neo),
    "pre-neo": Backend("pre-neo", "pre-Neo Steam build", pre_neo),
}


def state_score(backend: Backend, state: object) -> int:
    status = getattr(state, "status", "")
    supported = bool(getattr(state, "supported_signatures", False))

    if status in GOOD_STATES:
        return 100 if supported else 80
    if backend.key == "neo" and status in NEO_LEGACY_STATES:
        return 70
    if status == "conflict":
        return 50
    return 0


def analyze_with_backend(path: Path, backend: Backend) -> Detection:
    data = path.read_bytes()
    state = backend.module.analyze_image(data)
    return Detection(path, backend, state, state_score(backend, state))


def detect_file(path: Path, forced_build: str) -> Detection:
    if forced_build != "auto":
        backend = BACKENDS[forced_build]
        detection = analyze_with_backend(path, backend)
        if detection.score <= 0:
            raise CliError(
                f"{path} is not recognized as {backend.label}: "
                f"{getattr(detection.state, 'reason', None) or getattr(detection.state, 'status', 'unknown')}"
            )
        return detection

    detections = [analyze_with_backend(path, backend) for backend in BACKENDS.values()]
    detections.sort(key=lambda item: item.score, reverse=True)
    best = detections[0]
    if best.score <= 0:
        details = "; ".join(
            f"{detection.backend.key}: {getattr(detection.state, 'reason', None) or getattr(detection.state, 'status', 'unknown')}"
            for detection in detections
        )
        raise CliError(f"{path} is not a supported Super Hexagon executable ({details})")
    return best


def resolve_detection(path_arg: str | None, forced_build: str) -> Detection:
    candidates = steam.find_exe_candidates(path_arg)
    if not candidates:
        if path_arg:
            raise CliError(f"could not find Super Hexagon executable under: {path_arg}")
        raise CliError("could not find Super Hexagon through local paths or Steam. Pass --path.")

    failures: list[str] = []
    for candidate in candidates:
        try:
            return detect_file(candidate, forced_build)
        except CliError as exc:
            failures.append(str(exc))

    joined = "\n  ".join(failures)
    raise CliError(f"found executable candidates, but none matched a supported build:\n  {joined}")


def print_detection(detection: Detection) -> None:
    print(f"Executable: {detection.path}")
    print(f"Detected build: {detection.backend.label}")
    print(detection.backend.module.format_state(detection.state))


def validate_patch_refresh_hz(refresh_hz: int) -> None:
    if refresh_hz < MIN_PATCH_REFRESH_HZ or refresh_hz % REFRESH_HZ_STEP:
        raise CliError(
            f"refresh must be a multiple of {REFRESH_HZ_STEP} greater than or equal to {MIN_PATCH_REFRESH_HZ}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Patch Super Hexagon Neo and pre-Neo builds for high refresh rendering.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--path",
        help="Path to the executable or to the Super Hexagon install folder.",
    )
    parser.add_argument(
        "--build",
        choices=("auto", "neo", "pre-neo"),
        default="auto",
        help="Force a build backend instead of auto-detecting. Default: auto.",
    )

    subparsers = parser.add_subparsers(dest="command")

    status = subparsers.add_parser("status", help="Show patch state.")
    status.add_argument("--path", default=argparse.SUPPRESS)
    status.add_argument("--build", choices=("auto", "neo", "pre-neo"), default=argparse.SUPPRESS)
    status.set_defaults(command="status")

    patch = subparsers.add_parser("patch", help="Apply or update the high refresh patch.")
    patch.add_argument("--path", default=argparse.SUPPRESS)
    patch.add_argument("--build", choices=("auto", "neo", "pre-neo"), default=argparse.SUPPRESS)
    patch.add_argument(
        "--hz",
        "--fps",
        dest="refresh_hz",
        type=int,
        default=240,
        help="Render refresh. Must be a multiple of 60 and at least 120. Default: 240.",
    )
    patch.add_argument("--force", action="store_true")
    patch.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create or migrate the stable .bak copy before patching.",
    )
    patch.set_defaults(command="patch")

    restore = subparsers.add_parser("restore", help="Restore the original executable layout.")
    restore.add_argument("--path", default=argparse.SUPPRESS)
    restore.add_argument("--build", choices=("auto", "neo", "pre-neo"), default=argparse.SUPPRESS)
    restore.set_defaults(command="restore")

    diagnose = subparsers.add_parser(
        "diagnose",
        help="Temporarily instrument update/draw/swap and measure real runtime rates.",
    )
    diagnose.add_argument("--path", default=argparse.SUPPRESS)
    diagnose.add_argument("--build", choices=("auto", "neo", "pre-neo"), default=argparse.SUPPRESS)
    diagnose.add_argument(
        "--hz",
        "--fps",
        dest="refresh_hz",
        type=int,
        default=240,
        help="Diagnostic render refresh. Must be a multiple of 60 and at least 120. Default: 240.",
    )
    diagnose.add_argument("--seconds", type=float, default=5.0)
    diagnose.add_argument("--warmup", type=float, default=2.0)
    diagnose.add_argument("--force", action="store_true")
    diagnose.set_defaults(command="diagnose")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "status"
    path_arg = getattr(args, "path", None)
    forced_build = getattr(args, "build", "auto")

    try:
        detection = resolve_detection(path_arg, forced_build)

        if command == "status":
            print_detection(detection)
            return 0 if getattr(detection.state, "status", "") != "unsupported" else 2

        if command == "patch":
            validate_patch_refresh_hz(args.refresh_hz)
            state = detection.backend.module.patch_file(
                detection.path,
                refresh_hz=args.refresh_hz,
                force=args.force,
                backup=not args.no_backup,
            )
            print(f"Executable: {detection.path}")
            print(f"Detected build: {detection.backend.label}")
            print(detection.backend.module.format_state(state))
            print("High refresh patch applied. You can launch the game from Steam.")
            return 0

        if command == "restore":
            state = detection.backend.module.unpatch_file(detection.path)
            print(f"Executable: {detection.path}")
            print(f"Detected build: {detection.backend.label}")
            print(detection.backend.module.format_state(state))
            if getattr(state, "status", "") == "original":
                print("Patch removed. Steam will launch the original executable layout.")
            return 0

        if command == "diagnose":
            validate_patch_refresh_hz(args.refresh_hz)
            if args.seconds <= 0:
                raise CliError("--seconds must be greater than zero")
            if args.warmup < 0:
                raise CliError("--warmup must not be negative")
            result = detection.backend.module.diagnose_file(
                detection.path,
                refresh_hz=args.refresh_hz,
                duration_seconds=args.seconds,
                warmup_seconds=args.warmup,
                force=args.force,
            )
            print(f"Executable: {detection.path}")
            print(f"Detected build: {detection.backend.label}")
            print(detection.backend.module.format_diagnostic_result(result))
            print("Executable restored to its pre-diagnostic bytes.")
            return 0

        parser.error(f"unknown command: {command}")
        return 2
    except (CliError, neo.PatchError, pre_neo.PatchError) as exc:
        print(f"Error: {exc}")
        return 1
