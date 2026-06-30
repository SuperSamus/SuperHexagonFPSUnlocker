#!/usr/bin/env python3
"""Experimental FPS unlocker for the Pre-Neo Windows build of Super Hexagon.

This is intentionally separate from the Neo patcher. The Pre-Neo executable is
an older GLUT/openFrameworks build with a different timing loop.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


GAME_DIR_NAME = "Super Hexagon"
EXE_CANDIDATES = ("superhexagon.exe",)

ORIGINAL_REFRESH_HZ = 60
DEFAULT_REFRESH_HZ = 240
MIN_PATCH_REFRESH_HZ = 120
REFRESH_HZ_STEP = 60

SUPPORTED_PRE_NEO_SHA256 = (
    "69411cb275202b21c3e0428a5c27704e97663a17723497b61bd7dfeaa1534bdd"
)
SUPPORTED_PRE_NEO_SIZE = 2_698_240
IMAGE_BASE = 0x400000

PATCH_SECTION_NAME = b".shfps\x00"
# The Pre-Neo patch stores transient render-coordinate snapshots in the
# injected section so draw can interpolate visible wall positions.
PATCH_SECTION_SIZE = 0x4000
PATCH_SECTION_CHARACTERISTICS = 0xE0000020  # code, execute, read, write

PRE_NEO_MAGIC = b"SHPRENEO"
PRE_NEO_VERSION = 5

# The original Pre-Neo openFrameworks loop uses a 16 ms fixed frame interval.
# Keep that simulation cadence and only lower the render wait interval.
SIM_INTERVAL_US = 16_000

INIT_INTERVAL_OFFSET = 0xAAD41
INIT_INTERVAL_VA = 0x4AB941
INIT_INTERVAL_RETURN_VA = 0x4AB947
INIT_INTERVAL_ORIGINAL = bytes.fromhex("dd 05 28 7d 5e 00")

UPDATE_CALL_OFFSET = 0xAA945
UPDATE_CALL_VA = 0x4AB545
UPDATE_CALL_ORIGINAL = bytes.fromhex("e8 16 56 fe ff")
UPDATE_EVENT_VA = 0x490B60
SUPERHEX_INSTANCE_PTR_VA = 0x694B00
SUPERHEX_OBJECT_SIZE = 0x43310
INTERPOLATION_FIELDS: tuple[int, ...] = ()
GEOMETRY_ID_OFFSET = 0x4618
GEOMETRY_ARRAY_OFFSETS = (0x4AC8, 0x4F78)
GEOMETRY_ARRAY_DWORDS = 0x4B0 // 4
GEOMETRY_ARRAY_BYTES = GEOMETRY_ARRAY_DWORDS * 4
GEOMETRY_ID_BYTES = GEOMETRY_ARRAY_BYTES
GEOMETRY_STORAGE_BYTES = len(GEOMETRY_ARRAY_OFFSETS) * GEOMETRY_ARRAY_BYTES

SUPERHEX_DRAW_OFFSET = 0x3F4B0
SUPERHEX_DRAW_VA = 0x4400B0
SUPERHEX_DRAW_ORIGINAL = bytes.fromhex(
    "56 8b f1 e8 08 ca 04 00 89 86 08 33 04 00 8b ce 5e e9 3a fd ff ff"
)
SUPERHEX_DRAW_BODY_VA = 0x43FE00
SUPERHEX_DRAW_TIMESTAMP_OFFSET = 0x43308
TIME_GET_TIME_WRAPPER_VA = 0x48CAC0
GEOMETRY_INTERPOLATION_OFFSET = 0x3F28E
GEOMETRY_INTERPOLATION_VA = 0x43FE8E
GEOMETRY_INTERPOLATION_RETURN_VA = 0x43FE96
GEOMETRY_INTERPOLATION_ORIGINAL = bytes.fromhex("33 c0 89 86 5c 89 01 00")
INTERPOLATION_VALUE_LIMIT = 100_000
INTERPOLATION_DIFF_LIMIT = 768

DISPLAY_HOOK_OFFSET = 0xAA550
DISPLAY_HOOK_VA = 0x4AB150
DISPLAY_HOOK_RETURN_VA = 0x4AB159
DISPLAY_HOOK_ORIGINAL = bytes.fromhex("55 8b ec 51 a1 90 4b 69 00")

SWAP_CALL_OFFSET = 0xAA6FE
SWAP_CALL_VA = 0x4AB2FE
SWAP_CALL_ORIGINAL = bytes.fromhex("e8 63 34 0c 00")
GLUT_SWAP_BUFFERS_WRAPPER_VA = 0x56E766

SLEEP_ARG_OFFSET = 0xAA993
SLEEP_ARG_VA = 0x4AB593
SLEEP_ARG_ORIGINAL = bytes.fromhex("8b 45 f4 50")
SLEEP_ARG_PATCHED = bytes.fromhex("6a 00 90 90")


class PatchError(RuntimeError):
    """Raised when the executable cannot be patched safely."""


@dataclass(frozen=True)
class Section:
    index: int
    name: bytes
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_pointer: int
    characteristics: int

    def name_text(self) -> str:
        return self.name.split(b"\x00", 1)[0].decode("ascii", errors="replace")


@dataclass(frozen=True)
class PEInfo:
    pe_offset: int
    optional_header_offset: int
    section_table_offset: int
    number_of_sections: int
    image_base: int
    section_alignment: int
    file_alignment: int
    size_of_image: int
    size_of_headers: int
    sections: tuple[Section, ...]


@dataclass(frozen=True)
class PatchSite:
    name: str
    offset: int
    virtual_address: int
    original: bytes
    replacement: bytes


@dataclass(frozen=True)
class ImageState:
    status: str
    sha256: str
    size: int
    supported_signatures: bool
    refresh_hz: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DiagnosticResult:
    duration_seconds: float
    update_count: int
    draw_count: int
    swap_count: int


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def checked_rel32(source_va: int, target_va: int, instruction_length: int = 5) -> bytes:
    rel = target_va - (source_va + instruction_length)
    if not -(2**31) <= rel <= 2**31 - 1:
        raise PatchError(f"relative branch out of range: {source_va:#x} -> {target_va:#x}")
    return struct.pack("<i", rel)


def jmp(source_va: int, target_va: int) -> bytes:
    return b"\xe9" + checked_rel32(source_va, target_va)


def call(source_va: int, target_va: int) -> bytes:
    return b"\xe8" + checked_rel32(source_va, target_va)


def jump_patch(source_va: int, target_va: int, length: int) -> bytes:
    if length < 5:
        raise PatchError("jump patch length must be at least 5 bytes")
    return jmp(source_va, target_va) + (b"\x90" * (length - 5))


def slice_at(data: bytes | bytearray, offset: int, size: int) -> bytes:
    if len(data) < offset + size:
        return b""
    return bytes(data[offset : offset + size])


def validate_refresh_hz(refresh_hz: int) -> None:
    if not is_supported_refresh_hz(refresh_hz):
        raise PatchError(
            f"FPS must be {ORIGINAL_REFRESH_HZ} or a multiple of "
            f"{REFRESH_HZ_STEP} greater than or equal to {MIN_PATCH_REFRESH_HZ}"
        )


def is_supported_refresh_hz(refresh_hz: int | None) -> bool:
    if refresh_hz is None:
        return False
    return refresh_hz == ORIGINAL_REFRESH_HZ or (
        refresh_hz >= MIN_PATCH_REFRESH_HZ and refresh_hz % REFRESH_HZ_STEP == 0
    )


def render_interval_us(refresh_hz: int) -> int:
    return round(1_000_000 / refresh_hz)


def render_interval_ms(refresh_hz: int) -> float:
    return 1000.0 / refresh_hz


def parse_pe(data: bytes | bytearray) -> PEInfo:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise PatchError("not a PE executable")

    pe_offset = read_u32(data, 0x3C)
    if len(data) < pe_offset + 0x18 or data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        raise PatchError("invalid PE header")

    number_of_sections = read_u16(data, pe_offset + 6)
    optional_header_size = read_u16(data, pe_offset + 20)
    optional_header_offset = pe_offset + 24
    if read_u16(data, optional_header_offset) != 0x10B:
        raise PatchError("only PE32 executables are supported")

    image_base = read_u32(data, optional_header_offset + 28)
    section_alignment = read_u32(data, optional_header_offset + 32)
    file_alignment = read_u32(data, optional_header_offset + 36)
    size_of_image = read_u32(data, optional_header_offset + 56)
    size_of_headers = read_u32(data, optional_header_offset + 60)
    section_table_offset = optional_header_offset + optional_header_size

    sections: list[Section] = []
    for index in range(number_of_sections):
        offset = section_table_offset + index * 40
        if len(data) < offset + 40:
            raise PatchError("truncated section table")
        sections.append(
            Section(
                index=index,
                name=bytes(data[offset : offset + 8]),
                virtual_size=read_u32(data, offset + 8),
                virtual_address=read_u32(data, offset + 12),
                raw_size=read_u32(data, offset + 16),
                raw_pointer=read_u32(data, offset + 20),
                characteristics=read_u32(data, offset + 36),
            )
        )

    return PEInfo(
        pe_offset=pe_offset,
        optional_header_offset=optional_header_offset,
        section_table_offset=section_table_offset,
        number_of_sections=number_of_sections,
        image_base=image_base,
        section_alignment=section_alignment,
        file_alignment=file_alignment,
        size_of_image=size_of_image,
        size_of_headers=size_of_headers,
        sections=tuple(sections),
    )


def section_va(info: PEInfo, section: Section) -> int:
    return info.image_base + section.virtual_address


def section_header_offset(info: PEInfo, index: int) -> int:
    return info.section_table_offset + index * 40


def patch_section(info: PEInfo) -> Section | None:
    expected = PATCH_SECTION_NAME.rstrip(b"\x00")
    for section in info.sections:
        if section.name.split(b"\x00", 1)[0] == expected:
            return section
    return None


def all_sites_match(data: bytes | bytearray, sites: Iterable[PatchSite], replacement: bool) -> bool:
    for site in sites:
        expected = site.replacement if replacement else site.original
        if slice_at(data, site.offset, len(expected)) != expected:
            return False
    return True


def write_patch_sites(data: bytes, sites: Iterable[PatchSite]) -> bytes:
    patched = bytearray(data)
    for site in sites:
        if slice_at(patched, site.offset, len(site.original)) not in {
            site.original,
            site.replacement,
        }:
            raise PatchError(f"{site.name} bytes do not match expected signature")
        patched[site.offset : site.offset + len(site.replacement)] = site.replacement
    return bytes(patched)


def restore_patch_sites(data: bytes, info: PEInfo, section: Section) -> bytes:
    refresh_hz = section_refresh_hz(data, section)
    if not is_supported_refresh_hz(refresh_hz):
        raise PatchError("patch section has no supported refresh value")
    diagnostics = section_is_diagnostic(data, section)
    _payload, labels = build_patch_section(
        section_va(info, section),
        refresh_hz,
        diagnostics=diagnostics,
    )
    restored = bytearray(data)
    for site in patched_sites(section_va(info, section), labels, diagnostics=diagnostics):
        current = slice_at(restored, site.offset, len(site.replacement))
        if current == site.replacement:
            restored[site.offset : site.offset + len(site.original)] = site.original
        elif slice_at(restored, site.offset, len(site.original)) != site.original:
            raise PatchError(f"{site.name} bytes do not match this patcher")
    return bytes(restored)


def inc_abs(counter_va: int) -> bytes:
    return bytes.fromhex("ff 05") + struct.pack("<I", counter_va)


class X86Code:
    def __init__(self, start_va: int) -> None:
        self.start_va = start_va
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str]] = []

    def va(self) -> int:
        return self.start_va + len(self.code)

    def emit(self, data: bytes) -> None:
        self.code += data

    def label(self, name: str) -> None:
        if name in self.labels:
            raise PatchError(f"duplicate asm label: {name}")
        self.labels[name] = self.va()

    def jmp(self, label: str) -> None:
        self.fixups.append((len(self.code) + 1, 5, label))
        self.emit(b"\xe9\x00\x00\x00\x00")

    def jcc(self, condition: int, label: str) -> None:
        self.fixups.append((len(self.code) + 2, 6, label))
        self.emit(bytes([0x0F, condition, 0, 0, 0, 0]))

    def call(self, target_va: int) -> None:
        self.emit(call(self.va(), target_va))

    def finish(self) -> bytes:
        for offset, instruction_length, label in self.fixups:
            if label not in self.labels:
                raise PatchError(f"missing asm label: {label}")
            source_va = self.start_va + offset - (instruction_length - 4)
            target_va = self.labels[label]
            self.code[offset : offset + 4] = checked_rel32(source_va, target_va, instruction_length)
        return bytes(self.code)


def make_init_interval_hook(start_va: int, render_interval_va: int) -> bytes:
    code = bytearray()
    code += bytes.fromhex("dd 05") + struct.pack("<I", render_interval_va)
    code += jmp(start_va + len(code), INIT_INTERVAL_RETURN_VA)
    return bytes(code)


def make_update_gate_hook(
    start_va: int,
    sim_acc_us_va: int,
    render_interval_us_value: int,
    has_snapshot_va: int,
    prev_fields_va: int,
    prev_identity_va: int,
    prev_geometry_va: int,
    update_counter_va: int | None,
) -> bytes:
    asm = X86Code(start_va)
    asm.emit(bytes.fromhex("50"))  # push eax
    asm.emit(bytes.fromhex("a1") + struct.pack("<I", sim_acc_us_va))
    asm.emit(bytes.fromhex("05") + struct.pack("<I", render_interval_us_value))
    asm.emit(bytes.fromhex("3d") + struct.pack("<I", SIM_INTERVAL_US))
    asm.jcc(0x83, "do_update")  # jae do_update
    asm.emit(bytes.fromhex("a3") + struct.pack("<I", sim_acc_us_va))
    asm.emit(bytes.fromhex("58"))  # pop eax
    asm.emit(bytes.fromhex("c3"))  # ret

    asm.label("do_update")
    asm.emit(bytes.fromhex("2d") + struct.pack("<I", SIM_INTERVAL_US))
    asm.emit(bytes.fromhex("a3") + struct.pack("<I", sim_acc_us_va))
    if update_counter_va is not None:
        asm.emit(inc_abs(update_counter_va))

    asm.emit(bytes.fromhex("60"))  # pushad
    asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", SUPERHEX_INSTANCE_PTR_VA))
    asm.emit(bytes.fromhex("85 f6"))  # test esi, esi
    asm.jcc(0x84, "snapshot_done")  # je snapshot_done
    for index, field_offset in enumerate(INTERPOLATION_FIELDS):
        asm.emit(bytes.fromhex("8b 86") + struct.pack("<I", field_offset))  # mov eax, [esi+field]
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", prev_fields_va + index * 4))
    asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", SUPERHEX_INSTANCE_PTR_VA))
    asm.emit(bytes.fromhex("81 c6") + struct.pack("<I", GEOMETRY_ID_OFFSET))
    asm.emit(bytes.fromhex("bf") + struct.pack("<I", prev_identity_va))
    asm.emit(bytes.fromhex("b9") + struct.pack("<I", GEOMETRY_ARRAY_DWORDS))
    asm.emit(bytes.fromhex("fc"))  # cld
    asm.emit(bytes.fromhex("f3 a5"))  # rep movsd
    for index, geometry_offset in enumerate(GEOMETRY_ARRAY_OFFSETS):
        asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", SUPERHEX_INSTANCE_PTR_VA))
        asm.emit(bytes.fromhex("81 c6") + struct.pack("<I", geometry_offset))
        asm.emit(bytes.fromhex("bf") + struct.pack("<I", prev_geometry_va + index * GEOMETRY_ARRAY_BYTES))
        asm.emit(bytes.fromhex("b9") + struct.pack("<I", GEOMETRY_ARRAY_DWORDS))
        asm.emit(bytes.fromhex("fc"))  # cld
        asm.emit(bytes.fromhex("f3 a5"))  # rep movsd
    asm.emit(bytes.fromhex("c7 05") + struct.pack("<I", has_snapshot_va) + struct.pack("<I", 1))
    asm.label("snapshot_done")
    asm.emit(bytes.fromhex("61"))  # popad

    asm.emit(bytes.fromhex("58"))  # pop eax
    asm.call(UPDATE_EVENT_VA)
    asm.emit(bytes.fromhex("c3"))
    return asm.finish()


def make_display_counter_hook(start_va: int, draw_counter_va: int) -> bytes:
    code = bytearray()
    code += inc_abs(draw_counter_va)
    code += DISPLAY_HOOK_ORIGINAL
    code += jmp(start_va + len(code), DISPLAY_HOOK_RETURN_VA)
    return bytes(code)


def make_swap_counter_hook(start_va: int, swap_counter_va: int) -> bytes:
    code = bytearray()
    code += inc_abs(swap_counter_va)
    code += call(start_va + len(code), GLUT_SWAP_BUFFERS_WRAPPER_VA)
    code += bytes.fromhex("c3")
    return bytes(code)


def emit_abs_eax_limit_check(asm: X86Code, limit: int, skip_label: str) -> None:
    asm.emit(bytes.fromhex("8b d0"))  # mov edx, eax
    asm.emit(bytes.fromhex("c1 fa 1f"))  # sar edx, 31
    asm.emit(bytes.fromhex("33 c2"))  # xor eax, edx
    asm.emit(bytes.fromhex("2b c2"))  # sub eax, edx
    asm.emit(bytes.fromhex("3d") + struct.pack("<I", limit))
    asm.jcc(0x87, skip_label)  # ja skip_label


def add_abs_dword_imm8(address_va: int, value: int) -> bytes:
    if not 0 <= value <= 0x7F:
        raise PatchError("absolute add immediate must fit in signed imm8")
    return bytes.fromhex("83 05") + struct.pack("<I", address_va) + bytes([value])


def validate_interpolation_fields() -> None:
    for field_offset in INTERPOLATION_FIELDS:
        if field_offset < 0 or field_offset + 4 > SUPERHEX_OBJECT_SIZE or field_offset % 4:
            raise PatchError(f"invalid interpolation field: {field_offset:#x}")


def emit_backup_fields(asm: X86Code, draw_object_va: int, backup_fields_va: int) -> None:
    asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", draw_object_va))  # mov esi, [draw_object]
    for index, field_offset in enumerate(INTERPOLATION_FIELDS):
        asm.emit(bytes.fromhex("8b 86") + struct.pack("<I", field_offset))  # mov eax, [esi+field]
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", backup_fields_va + index * 4))


def emit_restore_fields(asm: X86Code, draw_object_va: int, backup_fields_va: int) -> None:
    asm.emit(bytes.fromhex("8b 3d") + struct.pack("<I", draw_object_va))  # mov edi, [draw_object]
    for index, field_offset in enumerate(INTERPOLATION_FIELDS):
        asm.emit(bytes.fromhex("a1") + struct.pack("<I", backup_fields_va + index * 4))
        asm.emit(bytes.fromhex("89 87") + struct.pack("<I", field_offset))  # mov [edi+field], eax


def emit_interpolate_fields(
    asm: X86Code,
    sim_acc_us_va: int,
    draw_object_va: int,
    scratch_prev_va: int,
    scratch_cur_va: int,
    scratch_diff_va: int,
    prev_fields_va: int,
) -> None:
    asm.emit(bytes.fromhex("a1") + struct.pack("<I", sim_acc_us_va))  # mov eax, [sim_acc_us]
    asm.emit(bytes.fromhex("3d") + struct.pack("<I", SIM_INTERVAL_US))  # cmp eax, SIM_INTERVAL_US
    asm.jcc(0x86, "alpha_ok")  # jbe alpha_ok
    asm.emit(bytes.fromhex("b8") + struct.pack("<I", SIM_INTERVAL_US))  # mov eax, SIM_INTERVAL_US
    asm.label("alpha_ok")
    asm.emit(bytes.fromhex("33 d2"))  # xor edx, edx
    asm.emit(bytes.fromhex("c1 e0 10"))  # shl eax, 16
    asm.emit(bytes.fromhex("b9") + struct.pack("<I", SIM_INTERVAL_US))
    asm.emit(bytes.fromhex("f7 f1"))  # div ecx
    asm.emit(bytes.fromhex("8b e8"))  # mov ebp, eax
    asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", draw_object_va))  # mov esi, [draw_object]

    for index, field_offset in enumerate(INTERPOLATION_FIELDS):
        skip_label = f"skip_field_{index}"
        asm.emit(bytes.fromhex("a1") + struct.pack("<I", prev_fields_va + index * 4))
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("8b 8e") + struct.pack("<I", field_offset))  # mov ecx, [esi+field]
        asm.emit(bytes.fromhex("3b c1"))  # cmp eax, ecx
        asm.jcc(0x84, skip_label)  # je skip_field
        asm.emit(bytes.fromhex("89 0d") + struct.pack("<I", scratch_cur_va))

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_prev_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)
        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_cur_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_cur_va))
        asm.emit(bytes.fromhex("2b 05") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", scratch_diff_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_DIFF_LIMIT, skip_label)

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_diff_va))
        asm.emit(bytes.fromhex("f7 ed"))  # imul ebp
        asm.emit(bytes.fromhex("0f ac d0 10"))  # shrd eax, edx, 16
        asm.emit(bytes.fromhex("03 05") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("89 86") + struct.pack("<I", field_offset))  # mov [esi+field], eax

        asm.label(skip_label)


def emit_copy_geometry_to_storage(asm: X86Code, draw_object_va: int, storage_va: int) -> None:
    for index, geometry_offset in enumerate(GEOMETRY_ARRAY_OFFSETS):
        asm.emit(bytes.fromhex("8b 35") + struct.pack("<I", draw_object_va))  # mov esi, [draw_object]
        asm.emit(bytes.fromhex("81 c6") + struct.pack("<I", geometry_offset))
        asm.emit(bytes.fromhex("bf") + struct.pack("<I", storage_va + index * GEOMETRY_ARRAY_BYTES))
        asm.emit(bytes.fromhex("b9") + struct.pack("<I", GEOMETRY_ARRAY_DWORDS))
        asm.emit(bytes.fromhex("fc"))  # cld
        asm.emit(bytes.fromhex("f3 a5"))  # rep movsd


def emit_restore_geometry_from_storage(asm: X86Code, draw_object_va: int, storage_va: int) -> None:
    for index, geometry_offset in enumerate(GEOMETRY_ARRAY_OFFSETS):
        asm.emit(bytes.fromhex("be") + struct.pack("<I", storage_va + index * GEOMETRY_ARRAY_BYTES))
        asm.emit(bytes.fromhex("8b 3d") + struct.pack("<I", draw_object_va))  # mov edi, [draw_object]
        asm.emit(bytes.fromhex("81 c7") + struct.pack("<I", geometry_offset))
        asm.emit(bytes.fromhex("b9") + struct.pack("<I", GEOMETRY_ARRAY_DWORDS))
        asm.emit(bytes.fromhex("fc"))  # cld
        asm.emit(bytes.fromhex("f3 a5"))  # rep movsd


def emit_interpolate_geometry(
    asm: X86Code,
    sim_acc_us_va: int,
    draw_object_va: int,
    scratch_prev_va: int,
    scratch_cur_va: int,
    scratch_diff_va: int,
    scratch_prev_id_ptr_va: int,
    prev_identity_va: int,
    prev_geometry_va: int,
) -> None:
    asm.emit(bytes.fromhex("a1") + struct.pack("<I", sim_acc_us_va))  # mov eax, [sim_acc_us]
    asm.emit(bytes.fromhex("3d") + struct.pack("<I", SIM_INTERVAL_US))  # cmp eax, SIM_INTERVAL_US
    asm.jcc(0x86, "geometry_alpha_ok")  # jbe geometry_alpha_ok
    asm.emit(bytes.fromhex("b8") + struct.pack("<I", SIM_INTERVAL_US))  # mov eax, SIM_INTERVAL_US
    asm.label("geometry_alpha_ok")
    asm.emit(bytes.fromhex("33 d2"))  # xor edx, edx
    asm.emit(bytes.fromhex("c1 e0 10"))  # shl eax, 16
    asm.emit(bytes.fromhex("b9") + struct.pack("<I", SIM_INTERVAL_US))
    asm.emit(bytes.fromhex("f7 f1"))  # div ecx
    asm.emit(bytes.fromhex("8b e8"))  # mov ebp, eax

    for index, geometry_offset in enumerate(GEOMETRY_ARRAY_OFFSETS):
        loop_label = f"geometry_loop_{index}"
        skip_label = f"geometry_skip_{index}"
        id_delta = geometry_offset - GEOMETRY_ID_OFFSET
        pair_prev_delta = GEOMETRY_ARRAY_BYTES if index == 0 else -GEOMETRY_ARRAY_BYTES
        pair_cur_delta = GEOMETRY_ARRAY_OFFSETS[1 - index] - geometry_offset

        asm.emit(bytes.fromhex("be") + struct.pack("<I", prev_geometry_va + index * GEOMETRY_ARRAY_BYTES))
        asm.emit(bytes.fromhex("8b 3d") + struct.pack("<I", draw_object_va))  # mov edi, [draw_object]
        asm.emit(bytes.fromhex("81 c7") + struct.pack("<I", geometry_offset))
        asm.emit(bytes.fromhex("c7 05") + struct.pack("<I", scratch_prev_id_ptr_va) + struct.pack("<I", prev_identity_va))
        asm.emit(bytes.fromhex("bb") + struct.pack("<I", GEOMETRY_ARRAY_DWORDS))

        asm.label(loop_label)
        asm.emit(bytes.fromhex("8b 15") + struct.pack("<I", scratch_prev_id_ptr_va))  # mov edx, [prev_id_ptr]
        asm.emit(bytes.fromhex("8b 02"))  # mov eax, [edx]
        asm.emit(bytes.fromhex("3b 87") + struct.pack("<i", -id_delta))  # cmp eax, [edi-id_delta]
        asm.jcc(0x85, skip_label)  # jne skip

        asm.emit(bytes.fromhex("8b 86") + struct.pack("<i", pair_prev_delta))  # mov eax, paired previous
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", scratch_prev_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)
        asm.emit(bytes.fromhex("8b 8f") + struct.pack("<i", pair_cur_delta))  # mov ecx, paired current
        asm.emit(bytes.fromhex("89 0d") + struct.pack("<I", scratch_cur_va))
        asm.emit(bytes.fromhex("8b c1"))  # mov eax, ecx
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)
        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_cur_va))
        asm.emit(bytes.fromhex("2b 05") + struct.pack("<I", scratch_prev_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_DIFF_LIMIT, skip_label)

        asm.emit(bytes.fromhex("8b 06"))  # mov eax, [esi]
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("8b 0f"))  # mov ecx, [edi]
        asm.emit(bytes.fromhex("3b c1"))  # cmp eax, ecx
        asm.jcc(0x84, skip_label)  # je skip
        asm.emit(bytes.fromhex("89 0d") + struct.pack("<I", scratch_cur_va))

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_prev_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)
        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_cur_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_VALUE_LIMIT, skip_label)

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_cur_va))
        asm.emit(bytes.fromhex("2b 05") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("a3") + struct.pack("<I", scratch_diff_va))
        emit_abs_eax_limit_check(asm, INTERPOLATION_DIFF_LIMIT, skip_label)

        asm.emit(bytes.fromhex("a1") + struct.pack("<I", scratch_diff_va))
        asm.emit(bytes.fromhex("f7 ed"))  # imul ebp
        asm.emit(bytes.fromhex("0f ac d0 10"))  # shrd eax, edx, 16
        asm.emit(bytes.fromhex("03 05") + struct.pack("<I", scratch_prev_va))
        asm.emit(bytes.fromhex("89 07"))  # mov [edi], eax

        asm.label(skip_label)
        asm.emit(add_abs_dword_imm8(scratch_prev_id_ptr_va, 4))
        asm.emit(bytes.fromhex("83 c6 04"))  # add esi, 4
        asm.emit(bytes.fromhex("83 c7 04"))  # add edi, 4
        asm.emit(bytes.fromhex("4b"))  # dec ebx
        asm.jcc(0x85, loop_label)  # jne loop


def make_geometry_interpolation_hook(
    start_va: int,
    sim_acc_us_va: int,
    has_snapshot_va: int,
    draw_object_va: int,
    geometry_active_va: int,
    scratch_prev_va: int,
    scratch_cur_va: int,
    scratch_diff_va: int,
    scratch_prev_id_ptr_va: int,
    prev_identity_va: int,
    prev_geometry_va: int,
    backup_geometry_va: int,
) -> bytes:
    asm = X86Code(start_va)
    asm.emit(bytes.fromhex("60"))  # pushad
    asm.emit(bytes.fromhex("83 3d") + struct.pack("<I", has_snapshot_va) + b"\x00")
    asm.jcc(0x84, "skip_geometry_interpolation")  # je skip
    emit_copy_geometry_to_storage(asm, draw_object_va, backup_geometry_va)
    emit_interpolate_geometry(
        asm,
        sim_acc_us_va,
        draw_object_va,
        scratch_prev_va,
        scratch_cur_va,
        scratch_diff_va,
        scratch_prev_id_ptr_va,
        prev_identity_va,
        prev_geometry_va,
    )
    asm.emit(bytes.fromhex("c7 05") + struct.pack("<I", geometry_active_va) + struct.pack("<I", 1))
    asm.label("skip_geometry_interpolation")
    asm.emit(bytes.fromhex("61"))  # popad
    asm.emit(GEOMETRY_INTERPOLATION_ORIGINAL)
    asm.emit(jmp(asm.va(), GEOMETRY_INTERPOLATION_RETURN_VA))
    return asm.finish()


def make_superhex_draw_interpolation_hook(
    start_va: int,
    draw_object_va: int,
    geometry_active_va: int,
    backup_geometry_va: int,
) -> bytes:
    asm = X86Code(start_va)

    # Original superhex::draw stub prologue.
    asm.emit(bytes.fromhex("56"))  # push esi
    asm.emit(bytes.fromhex("8b f1"))  # mov esi, ecx
    asm.call(TIME_GET_TIME_WRAPPER_VA)
    asm.emit(bytes.fromhex("89 86") + struct.pack("<I", SUPERHEX_DRAW_TIMESTAMP_OFFSET))

    asm.emit(bytes.fromhex("89 35") + struct.pack("<I", draw_object_va))  # mov [draw_object], esi
    asm.emit(bytes.fromhex("c7 05") + struct.pack("<I", geometry_active_va) + struct.pack("<I", 0))

    # Match the original tail-call convention: restore ESI before the body.
    asm.emit(bytes.fromhex("8b ce"))  # mov ecx, esi
    asm.emit(bytes.fromhex("5e"))  # pop esi
    asm.call(SUPERHEX_DRAW_BODY_VA)

    asm.emit(bytes.fromhex("60"))  # pushad
    asm.emit(bytes.fromhex("83 3d") + struct.pack("<I", geometry_active_va) + b"\x00")
    asm.jcc(0x84, "skip_restore_geometry")  # je skip_restore_geometry
    emit_restore_geometry_from_storage(asm, draw_object_va, backup_geometry_va)
    asm.label("skip_restore_geometry")
    asm.emit(bytes.fromhex("61"))  # popad
    asm.emit(bytes.fromhex("c3"))  # ret

    return asm.finish()


def patch_header(refresh_hz: int, diagnostics: bool) -> bytes:
    header = bytearray()
    header += PRE_NEO_MAGIC
    header += struct.pack("<I", PRE_NEO_VERSION)
    header += struct.pack("<I", refresh_hz)
    header += struct.pack("<I", render_interval_us(refresh_hz))
    header += struct.pack("<I", 0)  # simulation accumulator, microseconds
    header += struct.pack("<I", 1 if diagnostics else 0)
    header += struct.pack("<I", 0)  # update counter
    header += struct.pack("<I", 0)  # draw counter
    header += struct.pack("<I", 0)  # swap counter
    header += struct.pack("<I", 0)  # has previous simulation snapshot
    header += struct.pack("<I", 0)  # current draw object pointer
    header += struct.pack("<i", 0)  # interpolation scratch: previous value
    header += struct.pack("<i", 0)  # interpolation scratch: current value
    header += struct.pack("<i", 0)  # interpolation scratch: delta value
    header += struct.pack("<I", 0)  # geometry arrays were interpolated this draw
    header += struct.pack("<I", 0)  # interpolation scratch: previous identity pointer
    header += struct.pack("<I", 0)  # reserved pointer scratch
    header += struct.pack("<d", render_interval_ms(refresh_hz))
    while len(header) % 16:
        header += b"\x00"
    return bytes(header)


def build_patch_section(section_virtual_address: int, refresh_hz: int, diagnostics: bool = False) -> tuple[bytes, dict[str, int]]:
    validate_refresh_hz(refresh_hz)
    validate_interpolation_fields()

    payload = bytearray(patch_header(refresh_hz, diagnostics))
    labels = {
        "magic": section_virtual_address,
        "version": section_virtual_address + 8,
        "refresh_hz": section_virtual_address + 12,
        "render_interval_us": section_virtual_address + 16,
        "sim_acc_us": section_virtual_address + 20,
        "diagnostics": section_virtual_address + 24,
        "update_counter": section_virtual_address + 28,
        "draw_counter": section_virtual_address + 32,
        "swap_counter": section_virtual_address + 36,
        "has_snapshot": section_virtual_address + 40,
        "draw_object": section_virtual_address + 44,
        "scratch_prev": section_virtual_address + 48,
        "scratch_cur": section_virtual_address + 52,
        "scratch_diff": section_virtual_address + 56,
        "geometry_active": section_virtual_address + 60,
        "scratch_prev_id_ptr": section_virtual_address + 64,
        "scratch_aux_ptr": section_virtual_address + 68,
        "render_interval_ms": section_virtual_address + 72,
    }

    field_storage_size = 4 * len(INTERPOLATION_FIELDS)
    labels["prev_fields"] = section_virtual_address + len(payload)
    payload += b"\x00" * field_storage_size
    labels["backup_fields"] = section_virtual_address + len(payload)
    payload += b"\x00" * field_storage_size
    labels["prev_identity"] = section_virtual_address + len(payload)
    payload += b"\x00" * GEOMETRY_ID_BYTES
    labels["prev_geometry"] = section_virtual_address + len(payload)
    payload += b"\x00" * GEOMETRY_STORAGE_BYTES
    labels["backup_geometry"] = section_virtual_address + len(payload)
    payload += b"\x00" * GEOMETRY_STORAGE_BYTES
    while len(payload) % 16:
        payload += b"\x00"

    start_va = section_virtual_address + len(payload)
    labels["init_interval"] = start_va
    payload += make_init_interval_hook(start_va, labels["render_interval_ms"])
    while len(payload) % 4:
        payload += b"\x90"

    start_va = section_virtual_address + len(payload)
    labels["update_gate"] = start_va
    payload += make_update_gate_hook(
        start_va,
        labels["sim_acc_us"],
        render_interval_us(refresh_hz),
        labels["has_snapshot"],
        labels["prev_fields"],
        labels["prev_identity"],
        labels["prev_geometry"],
        labels["update_counter"] if diagnostics else None,
    )
    while len(payload) % 4:
        payload += b"\x90"

    start_va = section_virtual_address + len(payload)
    labels["draw_interpolation"] = start_va
    payload += make_superhex_draw_interpolation_hook(
        start_va,
        labels["draw_object"],
        labels["geometry_active"],
        labels["backup_geometry"],
    )
    while len(payload) % 4:
        payload += b"\x90"

    start_va = section_virtual_address + len(payload)
    labels["geometry_interpolation"] = start_va
    payload += make_geometry_interpolation_hook(
        start_va,
        labels["sim_acc_us"],
        labels["has_snapshot"],
        labels["draw_object"],
        labels["geometry_active"],
        labels["scratch_prev"],
        labels["scratch_cur"],
        labels["scratch_diff"],
        labels["scratch_prev_id_ptr"],
        labels["prev_identity"],
        labels["prev_geometry"],
        labels["backup_geometry"],
    )
    while len(payload) % 4:
        payload += b"\x90"

    if diagnostics:
        start_va = section_virtual_address + len(payload)
        labels["display_counter"] = start_va
        payload += make_display_counter_hook(start_va, labels["draw_counter"])
        while len(payload) % 4:
            payload += b"\x90"

        start_va = section_virtual_address + len(payload)
        labels["swap_counter_hook"] = start_va
        payload += make_swap_counter_hook(start_va, labels["swap_counter"])
        while len(payload) % 4:
            payload += b"\x90"

    if len(payload) > PATCH_SECTION_SIZE:
        raise PatchError("internal patch payload does not fit in patch section")
    payload += b"\x00" * (PATCH_SECTION_SIZE - len(payload))
    return bytes(payload), labels


def patched_sites(section_virtual_address: int, labels: dict[str, int], diagnostics: bool = False) -> list[PatchSite]:
    sites = [
        PatchSite(
            "render interval init",
            INIT_INTERVAL_OFFSET,
            INIT_INTERVAL_VA,
            INIT_INTERVAL_ORIGINAL,
            jump_patch(INIT_INTERVAL_VA, labels["init_interval"], len(INIT_INTERVAL_ORIGINAL)),
        ),
        PatchSite(
            "update gate",
            UPDATE_CALL_OFFSET,
            UPDATE_CALL_VA,
            UPDATE_CALL_ORIGINAL,
            call(UPDATE_CALL_VA, labels["update_gate"]),
        ),
        PatchSite(
            "superhex draw interpolation",
            SUPERHEX_DRAW_OFFSET,
            SUPERHEX_DRAW_VA,
            SUPERHEX_DRAW_ORIGINAL,
            jump_patch(SUPERHEX_DRAW_VA, labels["draw_interpolation"], len(SUPERHEX_DRAW_ORIGINAL)),
        ),
        PatchSite(
            "geometry coordinate interpolation",
            GEOMETRY_INTERPOLATION_OFFSET,
            GEOMETRY_INTERPOLATION_VA,
            GEOMETRY_INTERPOLATION_ORIGINAL,
            jump_patch(
                GEOMETRY_INTERPOLATION_VA,
                labels["geometry_interpolation"],
                len(GEOMETRY_INTERPOLATION_ORIGINAL),
            ),
        ),
        PatchSite(
            "high refresh sleep yield",
            SLEEP_ARG_OFFSET,
            SLEEP_ARG_VA,
            SLEEP_ARG_ORIGINAL,
            SLEEP_ARG_PATCHED,
        ),
    ]
    if diagnostics:
        sites.append(
            PatchSite(
                "display counter",
                DISPLAY_HOOK_OFFSET,
                DISPLAY_HOOK_VA,
                DISPLAY_HOOK_ORIGINAL,
                jump_patch(DISPLAY_HOOK_VA, labels["display_counter"], len(DISPLAY_HOOK_ORIGINAL)),
            )
        )
        sites.append(
            PatchSite(
                "swap counter",
                SWAP_CALL_OFFSET,
                SWAP_CALL_VA,
                SWAP_CALL_ORIGINAL,
                call(SWAP_CALL_VA, labels["swap_counter_hook"]),
            )
        )
    return sites


def install_or_update_patch_section(
    data: bytes,
    refresh_hz: int,
    diagnostics: bool = False,
) -> tuple[bytes, PEInfo, Section]:
    info = parse_pe(data)
    existing = patch_section(info)
    if existing is not None:
        patched = bytearray(data)
        section_address = section_va(info, existing)
        payload, _labels = build_patch_section(section_address, refresh_hz, diagnostics=diagnostics)
        patched[existing.raw_pointer : existing.raw_pointer + len(payload)] = payload
        return bytes(patched), parse_pe(patched), existing

    last = info.sections[-1]
    raw_pointer = align_up(len(data), info.file_alignment)
    virtual_address = align_up(
        last.virtual_address + max(last.virtual_size, last.raw_size),
        info.section_alignment,
    )
    raw_size = align_up(PATCH_SECTION_SIZE, info.file_alignment)
    virtual_size = PATCH_SECTION_SIZE
    new_size_of_image = align_up(virtual_address + virtual_size, info.section_alignment)

    header_offset = section_header_offset(info, info.number_of_sections)
    if header_offset + 40 > info.size_of_headers:
        raise PatchError("not enough room in PE headers for a patch section")

    patched = bytearray(data)
    if len(patched) < raw_pointer:
        patched += b"\x00" * (raw_pointer - len(patched))
    patched += b"\x00" * raw_size

    write_u16(patched, info.pe_offset + 6, info.number_of_sections + 1)
    write_u32(patched, info.optional_header_offset + 56, new_size_of_image)

    patched[header_offset : header_offset + 8] = PATCH_SECTION_NAME.ljust(8, b"\x00")
    write_u32(patched, header_offset + 8, virtual_size)
    write_u32(patched, header_offset + 12, virtual_address)
    write_u32(patched, header_offset + 16, raw_size)
    write_u32(patched, header_offset + 20, raw_pointer)
    write_u32(patched, header_offset + 24, 0)
    write_u32(patched, header_offset + 28, 0)
    write_u16(patched, header_offset + 32, 0)
    write_u16(patched, header_offset + 34, 0)
    write_u32(patched, header_offset + 36, PATCH_SECTION_CHARACTERISTICS)

    new_info = parse_pe(patched)
    section = patch_section(new_info)
    if section is None:
        raise PatchError("failed to create patch section")
    payload, _labels = build_patch_section(section_va(new_info, section), refresh_hz, diagnostics=diagnostics)
    patched[section.raw_pointer : section.raw_pointer + len(payload)] = payload
    return bytes(patched), parse_pe(patched), section


def remove_patch_section(data: bytes) -> bytes:
    info = parse_pe(data)
    section = patch_section(info)
    if section is None:
        return data
    data = restore_patch_sites(data, info, section)
    info = parse_pe(data)
    section = patch_section(info)
    if section is None:
        return data
    if section.index != info.number_of_sections - 1:
        raise PatchError("patch section is not the last section; refusing to remove it")

    patched = bytearray(data[: section.raw_pointer])
    write_u16(patched, info.pe_offset + 6, info.number_of_sections - 1)
    previous = info.sections[-2]
    size_of_image = align_up(
        previous.virtual_address + max(previous.virtual_size, previous.raw_size),
        info.section_alignment,
    )
    write_u32(patched, info.optional_header_offset + 56, size_of_image)
    header_offset = section_header_offset(info, section.index)
    patched[header_offset : header_offset + 40] = b"\x00" * 40
    return bytes(patched)


def section_refresh_hz(data: bytes, section: Section) -> int | None:
    header = slice_at(data, section.raw_pointer, 16)
    if len(header) < 16 or header[:8] != PRE_NEO_MAGIC:
        return None
    version = struct.unpack_from("<I", header, 8)[0]
    refresh_hz = struct.unpack_from("<I", header, 12)[0]
    if version != PRE_NEO_VERSION:
        return None
    return refresh_hz


def section_is_diagnostic(data: bytes, section: Section) -> bool:
    value = slice_at(data, section.raw_pointer + 24, 4)
    return len(value) == 4 and struct.unpack("<I", value)[0] == 1


def analyze_image(data: bytes) -> ImageState:
    digest = sha256_bytes(data)
    known_hash = digest == SUPPORTED_PRE_NEO_SHA256 and len(data) == SUPPORTED_PRE_NEO_SIZE

    try:
        info = parse_pe(data)
    except PatchError as exc:
        return ImageState("unsupported", digest, len(data), False, reason=str(exc))

    if info.image_base != IMAGE_BASE:
        return ImageState(
            "unsupported",
            digest,
            len(data),
            False,
            reason=f"unexpected image base {info.image_base:#x}",
        )

    section = patch_section(info)
    if section is not None:
        refresh_hz = section_refresh_hz(data, section)
        if not is_supported_refresh_hz(refresh_hz):
            return ImageState(
                "conflict",
                digest,
                len(data),
                False,
                refresh_hz=refresh_hz,
                reason="patch section exists but does not look like this Pre-Neo patcher",
            )
        diagnostics = section_is_diagnostic(data, section)
        payload, labels = build_patch_section(section_va(info, section), refresh_hz, diagnostics=diagnostics)
        sites = patched_sites(section_va(info, section), labels, diagnostics=diagnostics)
        section_payload = slice_at(data, section.raw_pointer, len(payload))
        if section_payload == payload and all_sites_match(data, sites, replacement=True):
            return ImageState(
                "diagnostic" if diagnostics else "patched",
                digest,
                len(data),
                True,
                refresh_hz=refresh_hz,
            )
        return ImageState(
            "conflict",
            digest,
            len(data),
            False,
            refresh_hz=refresh_hz,
            reason="patch section or patch sites do not match this Pre-Neo patcher",
        )

    original_sites = [
        PatchSite("render interval init", INIT_INTERVAL_OFFSET, INIT_INTERVAL_VA, INIT_INTERVAL_ORIGINAL, b""),
        PatchSite("update gate", UPDATE_CALL_OFFSET, UPDATE_CALL_VA, UPDATE_CALL_ORIGINAL, b""),
        PatchSite("superhex draw interpolation", SUPERHEX_DRAW_OFFSET, SUPERHEX_DRAW_VA, SUPERHEX_DRAW_ORIGINAL, b""),
        PatchSite(
            "geometry coordinate interpolation",
            GEOMETRY_INTERPOLATION_OFFSET,
            GEOMETRY_INTERPOLATION_VA,
            GEOMETRY_INTERPOLATION_ORIGINAL,
            b"",
        ),
        PatchSite("display hook", DISPLAY_HOOK_OFFSET, DISPLAY_HOOK_VA, DISPLAY_HOOK_ORIGINAL, b""),
        PatchSite("swap call", SWAP_CALL_OFFSET, SWAP_CALL_VA, SWAP_CALL_ORIGINAL, b""),
        PatchSite("sleep argument", SLEEP_ARG_OFFSET, SLEEP_ARG_VA, SLEEP_ARG_ORIGINAL, b""),
    ]
    if all_sites_match(data, original_sites, replacement=False):
        return ImageState("original", digest, len(data), known_hash, refresh_hz=ORIGINAL_REFRESH_HZ)

    return ImageState(
        "unsupported",
        digest,
        len(data),
        False,
        reason="expected Pre-Neo patch signatures were not found",
    )


def patch_image(
    data: bytes,
    refresh_hz: int,
    force: bool = False,
    diagnostics: bool = False,
) -> tuple[bytes, ImageState, bool]:
    validate_refresh_hz(refresh_hz)
    if refresh_hz == ORIGINAL_REFRESH_HZ and not diagnostics:
        return unpatch_image(data)

    state = analyze_image(data)
    target_status = "diagnostic" if diagnostics else "patched"

    if state.status in {"patched", "diagnostic"}:
        data = remove_patch_section(data)
        state = analyze_image(data)

    if state.status != "original":
        raise PatchError(state.reason or f"cannot patch executable in state: {state.status}")

    if not state.supported_signatures and not force:
        raise PatchError(
            "unsupported executable hash/signatures. Re-run with --force only if this is "
            "the matching Pre-Neo Windows build and you accept patching by byte signatures."
        )

    with_section, info, section = install_or_update_patch_section(
        data,
        refresh_hz,
        diagnostics=diagnostics,
    )
    payload, labels = build_patch_section(section_va(info, section), refresh_hz, diagnostics=diagnostics)
    if slice_at(with_section, section.raw_pointer, len(payload)) != payload:
        raise PatchError("failed to write patch payload")
    patched = write_patch_sites(
        with_section,
        patched_sites(section_va(info, section), labels, diagnostics=diagnostics),
    )
    new_state = analyze_image(patched)
    if new_state.status != target_status:
        raise PatchError(new_state.reason or "failed to apply patch")
    return patched, new_state, True


def unpatch_image(data: bytes) -> tuple[bytes, ImageState, bool]:
    state = analyze_image(data)
    if state.status == "original":
        return data, state, False
    if state.status not in {"patched", "diagnostic"}:
        raise PatchError(state.reason or f"cannot unpatch executable in state: {state.status}")
    restored = remove_patch_section(data)
    return restored, analyze_image(restored), True


def backup_path_for(exe_path: Path) -> Path:
    return exe_path.with_name(f"{exe_path.name}.bak")


def write_image(path: Path, data: bytes) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def backup_is_valid_original(data: bytes, force: bool = False) -> bool:
    state = analyze_image(data)
    return state.status == "original" and (state.supported_signatures or force)


def original_image_for_backup(data: bytes, force: bool) -> bytes:
    state = analyze_image(data)
    if state.status == "original":
        if not state.supported_signatures and not force:
            raise PatchError(
                "refusing to back up unsupported original executable. Re-run with --force only "
                "if this is a layout-compatible Pre-Neo Windows build."
            )
        return data

    restored, restored_state, _changed = unpatch_image(data)
    if restored_state.status != "original" or (not restored_state.supported_signatures and not force):
        raise PatchError("could not reconstruct a valid original executable for backup")
    return restored


def legacy_backup_paths(exe_path: Path) -> list[Path]:
    return sorted(exe_path.parent.glob(f"{exe_path.name}.bak.*"))


def ensure_backup_file(exe_path: Path, current_data: bytes, force: bool) -> None:
    backup_path = backup_path_for(exe_path)
    if backup_path.exists():
        backup_data = backup_path.read_bytes()
        if backup_is_valid_original(backup_data, force=force):
            print(f"Backup already exists: {backup_path}")
            return
        try:
            replacement_data = original_image_for_backup(current_data, force=force)
        except PatchError as exc:
            raise PatchError(
                f"backup exists but is not valid for this build: {backup_path}. "
                f"Could not replace it safely: {exc}"
            ) from exc
        write_image(backup_path, replacement_data)
        print(f"Backup replaced: {backup_path}")
        return

    for legacy_path in legacy_backup_paths(exe_path):
        try:
            legacy_data = legacy_path.read_bytes()
        except OSError:
            continue
        if backup_is_valid_original(legacy_data, force=force):
            shutil.copy2(legacy_path, backup_path)
            print(f"Backup migrated: {backup_path} (from {legacy_path.name})")
            return

    write_image(backup_path, original_image_for_backup(current_data, force=force))
    print(f"Backup written: {backup_path}")


def patch_file(exe_path: Path, refresh_hz: int, force: bool, backup: bool) -> ImageState:
    original = exe_path.read_bytes()
    if backup:
        ensure_backup_file(exe_path, original, force=force)
    patched, state, changed = patch_image(original, refresh_hz=refresh_hz, force=force)
    if changed:
        write_image(exe_path, patched)
    return state


TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", ctypes.c_void_p),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


def ensure_windows_diagnostics() -> None:
    if sys.platform != "win32":
        raise PatchError("runtime diagnostics are only supported on Windows")


def win_error(prefix: str) -> PatchError:
    error_code = ctypes.windll.kernel32.GetLastError()
    return PatchError(f"{prefix}: {ctypes.WinError(error_code)}")


def find_process_module_base(process_id: int, module_name: str) -> int:
    ensure_windows_diagnostics()
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32FirstW.restype = wintypes.BOOL
    kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
        process_id,
    )
    if snapshot == wintypes.HANDLE(-1).value:
        raise win_error("CreateToolhelp32Snapshot failed")

    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32W)
        if not kernel32.Module32FirstW(snapshot, ctypes.byref(entry)):
            raise win_error("Module32FirstW failed")

        expected = module_name.lower()
        while True:
            if entry.szModule.lower() == expected:
                if entry.modBaseAddr is None:
                    raise PatchError(f"module base for {module_name} is null")
                return int(entry.modBaseAddr)
            if not kernel32.Module32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)

    raise PatchError(f"could not find module {module_name} in process {process_id}")


def read_process_u32s(process_id: int, addresses: Iterable[int]) -> list[int]:
    ensure_windows_diagnostics()
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.LPVOID,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, process_id)
    if not handle:
        raise win_error("OpenProcess failed")

    try:
        values: list[int] = []
        for address in addresses:
            value = ctypes.c_uint32()
            bytes_read = ctypes.c_size_t()
            ok = kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(value),
                ctypes.sizeof(value),
                ctypes.byref(bytes_read),
            )
            if not ok or bytes_read.value != ctypes.sizeof(value):
                raise win_error(f"ReadProcessMemory failed at {address:#x}")
            values.append(value.value)
        return values
    finally:
        kernel32.CloseHandle(handle)


def diagnostic_counter_rvas(data: bytes, refresh_hz: int) -> dict[str, int]:
    info = parse_pe(data)
    section = patch_section(info)
    if section is None:
        raise PatchError("diagnostic image has no patch section")
    _payload, labels = build_patch_section(section_va(info, section), refresh_hz, diagnostics=True)
    return {
        "update": labels["update_counter"] - info.image_base,
        "draw": labels["draw_counter"] - info.image_base,
        "swap": labels["swap_counter"] - info.image_base,
    }


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def diagnose_file(
    exe_path: Path,
    refresh_hz: int,
    duration_seconds: float,
    warmup_seconds: float,
    force: bool,
) -> DiagnosticResult:
    ensure_windows_diagnostics()
    original = exe_path.read_bytes()
    diagnostic_image, state, _changed = patch_image(
        original,
        refresh_hz=refresh_hz,
        force=force,
        diagnostics=True,
    )
    if state.status != "diagnostic":
        raise PatchError(state.reason or "failed to create diagnostic image")

    counter_rvas = diagnostic_counter_rvas(diagnostic_image, refresh_hz)
    write_image(exe_path, diagnostic_image)

    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
        warmup_deadline = time.perf_counter() + warmup_seconds
        while time.perf_counter() < warmup_deadline:
            if process.poll() is not None:
                raise PatchError(f"game exited during diagnostics with code {process.returncode}")
            time.sleep(0.1)

        module_base = find_process_module_base(process.pid, exe_path.name)
        addresses = [
            module_base + counter_rvas["update"],
            module_base + counter_rvas["draw"],
            module_base + counter_rvas["swap"],
        ]
        before = read_process_u32s(process.pid, addresses)
        start = time.perf_counter()
        deadline = start + duration_seconds
        while time.perf_counter() < deadline:
            if process.poll() is not None:
                raise PatchError(f"game exited during diagnostics with code {process.returncode}")
            time.sleep(0.1)
        end = time.perf_counter()
        after = read_process_u32s(process.pid, addresses)

        return DiagnosticResult(
            duration_seconds=end - start,
            update_count=(after[0] - before[0]) & 0xFFFFFFFF,
            draw_count=(after[1] - before[1]) & 0xFFFFFFFF,
            swap_count=(after[2] - before[2]) & 0xFFFFFFFF,
        )
    finally:
        if process is not None:
            terminate_process(process)
        write_image(exe_path, original)


def unpatch_file(exe_path: Path) -> ImageState:
    backup_path = backup_path_for(exe_path)
    if backup_path.exists():
        backup_data = backup_path.read_bytes()
        if backup_is_valid_original(backup_data):
            if exe_path.read_bytes() != backup_data:
                write_image(exe_path, backup_data)
            return analyze_image(backup_data)

        current_data = exe_path.read_bytes()
        try:
            restored_data = original_image_for_backup(current_data, force=False)
        except PatchError as exc:
            raise PatchError(
                f"backup exists but is not valid for this build: {backup_path}. "
                f"Could not restore without it: {exc}"
            ) from exc
        if current_data != restored_data:
            write_image(exe_path, restored_data)
        write_image(backup_path, restored_data)
        return analyze_image(restored_data)

    restored, state, changed = unpatch_image(exe_path.read_bytes())
    if changed:
        write_image(exe_path, restored)
    return state


def resolve_exe(path_arg: str | None) -> Path:
    candidates: list[Path] = []
    if path_arg:
        path = Path(path_arg)
        if path.is_file():
            candidates.append(path)
        else:
            candidates.extend(path / name for name in EXE_CANDIDATES)
    else:
        cwd = Path.cwd()
        candidates.extend(cwd / name for name in EXE_CANDIDATES)
        candidates.extend(cwd / GAME_DIR_NAME / name for name in EXE_CANDIDATES)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = "\n  ".join(str(candidate) for candidate in candidates)
    raise PatchError(f"could not find Pre-Neo superhexagon.exe. Searched:\n  {searched}")


def format_state(state: ImageState) -> str:
    lines = [
        f"State: {state.status}",
        f"SHA-256: {state.sha256}",
        f"Size: {state.size} bytes",
        f"Supported signatures: {'yes' if state.supported_signatures else 'no'}",
    ]
    if state.refresh_hz is not None:
        lines.append(f"Target FPS: {state.refresh_hz}")
    if state.reason:
        lines.append(f"Reason: {state.reason}")
    return "\n".join(lines)


def format_diagnostic_result(result: DiagnosticResult) -> str:
    duration = result.duration_seconds
    return "\n".join(
        [
            f"Measured seconds: {duration:.2f}",
            f"Update calls: {result.update_count} ({result.update_count / duration:.1f}/s)",
            f"Draw calls: {result.draw_count} ({result.draw_count / duration:.1f}/s)",
            f"Swap calls: {result.swap_count} ({result.swap_count / duration:.1f}/s)",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Patch the Pre-Neo Windows Super Hexagon build for higher FPS rendering.",
    )
    parser.add_argument(
        "--path",
        help="Path to superhexagon.exe or to the Pre-Neo Super Hexagon folder.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Show executable patch status.")

    patch = subparsers.add_parser("patch", help="Apply or update the Pre-Neo FPS patch.")
    patch.add_argument("--fps", type=int, dest="refresh_hz", metavar="FPS", default=DEFAULT_REFRESH_HZ)
    patch.add_argument("--force", action="store_true")
    patch.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create, migrate, or refresh the stable .bak copy.",
    )

    unpatch = subparsers.add_parser("unpatch", help="Restore the original executable layout.")
    unpatch.set_defaults(command="unpatch")

    diagnose = subparsers.add_parser("diagnose", help="Temporarily instrument and measure the game.")
    diagnose.add_argument("--fps", type=int, dest="refresh_hz", metavar="FPS", default=DEFAULT_REFRESH_HZ)
    diagnose.add_argument("--seconds", type=float, default=5.0)
    diagnose.add_argument("--warmup", type=float, default=1.0)
    diagnose.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "status"

    try:
        exe_path = resolve_exe(args.path)
        print(f"Executable: {exe_path}")

        if command == "status":
            state = analyze_image(exe_path.read_bytes())
            print(format_state(state))
            return 0 if state.status in {"original", "patched", "diagnostic"} else 2

        if command == "patch":
            state = patch_file(
                exe_path,
                refresh_hz=args.refresh_hz,
                force=args.force,
                backup=not args.no_backup,
            )
            print(format_state(state))
            if state.status == "patched":
                print("Pre-Neo high FPS patch applied.")
            return 0

        if command == "unpatch":
            state = unpatch_file(exe_path)
            print(format_state(state))
            if state.status == "original":
                print("Patch removed.")
            return 0

        if command == "diagnose":
            if args.seconds <= 0:
                raise PatchError("--seconds must be greater than zero")
            if args.warmup < 0:
                raise PatchError("--warmup must not be negative")
            result = diagnose_file(
                exe_path,
                refresh_hz=args.refresh_hz,
                duration_seconds=args.seconds,
                warmup_seconds=args.warmup,
                force=args.force,
            )
            print(format_diagnostic_result(result))
            print("Executable restored to its pre-diagnostic bytes.")
            return 0

        parser.error(f"unknown command: {command}")
        return 2

    except PatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
