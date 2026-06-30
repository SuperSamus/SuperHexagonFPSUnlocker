from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable


APP_ID = "221640"
GAME_DIR_NAME = "Super Hexagon"
EXE_CANDIDATES = ("SuperHexagon.exe", "superhexagon.exe")


def decode_vdf_path(value: str) -> str:
    return value.replace("\\\\", "\\")


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        normalized = str(path.expanduser()).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path.expanduser())
    return unique


def parse_steam_libraryfolders(text: str) -> list[Path]:
    paths: list[Path] = []

    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        paths.append(Path(decode_vdf_path(match.group(1))))

    # Older Steam VDF format: "1" "D:\\SteamLibrary"
    for match in re.finditer(r'"\d+"\s+"([^"]+)"', text):
        value = match.group(1)
        if ":" in value or value.startswith("\\\\"):
            paths.append(Path(decode_vdf_path(value)))

    return unique_paths(paths)


def parse_manifest_installdir(text: str) -> str | None:
    match = re.search(r'"installdir"\s+"([^"]+)"', text, flags=re.IGNORECASE)
    if not match:
        return None
    return decode_vdf_path(match.group(1))


def registry_steam_roots() -> list[Path]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except ImportError:
        return []

    roots: list[Path] = []
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam"),
    ]
    values = ("SteamPath", "InstallPath")
    for hive, key_name in keys:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                for value_name in values:
                    try:
                        value, _ = winreg.QueryValueEx(key, value_name)
                    except OSError:
                        continue
                    if value:
                        roots.append(Path(str(value)))
        except OSError:
            continue
    return unique_paths(roots)


def default_steam_roots() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value) / "Steam")
    return unique_paths(candidates)


def steam_libraries() -> list[Path]:
    roots = unique_paths(registry_steam_roots() + default_steam_roots())
    libraries: list[Path] = []
    for root in roots:
        libraries.append(root)
        vdf_path = root / "steamapps" / "libraryfolders.vdf"
        if vdf_path.exists():
            try:
                libraries.extend(parse_steam_libraryfolders(vdf_path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
    return unique_paths(libraries)


def exe_candidates_in_dir(path: Path) -> list[Path]:
    candidates: list[Path] = []
    for name in EXE_CANDIDATES:
        candidates.append(path / name)
        candidates.append(path / GAME_DIR_NAME / name)
    return unique_paths(candidates)


def steam_exe_candidates() -> list[Path]:
    candidates: list[Path] = []
    for library in steam_libraries():
        steamapps = library / "steamapps"
        manifest = steamapps / f"appmanifest_{APP_ID}.acf"
        install_dirs = [GAME_DIR_NAME]
        if manifest.exists():
            try:
                install_dir = parse_manifest_installdir(
                    manifest.read_text(encoding="utf-8", errors="ignore")
                )
            except OSError:
                install_dir = None
            if install_dir:
                install_dirs.insert(0, install_dir)

        for install_dir in install_dirs:
            install_root = steamapps / "common" / install_dir
            candidates.extend(exe_candidates_in_dir(install_root))
    return unique_paths(candidates)


def local_exe_candidates() -> list[Path]:
    package_root = Path(__file__).resolve().parents[2]
    repo_root = package_root.parent
    roots = unique_paths([Path.cwd(), repo_root])
    candidates: list[Path] = []
    for root in roots:
        candidates.extend(exe_candidates_in_dir(root))
    return unique_paths(candidates)


def find_exe_candidates(path_arg: str | None) -> list[Path]:
    if path_arg:
        path = Path(path_arg).expanduser()
        if path.is_file():
            return [path.resolve()]
        candidates = [candidate for candidate in exe_candidates_in_dir(path) if candidate.exists()]
        return [candidate.resolve() for candidate in candidates]

    candidates = [path for path in local_exe_candidates() + steam_exe_candidates() if path.exists()]
    return unique_paths(path.resolve() for path in candidates)

