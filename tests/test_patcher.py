import struct
import unittest

import superhexagon_fps_unlocker as patcher


ORIGINAL_SIZE = patcher.SUPPORTED_EXE_SIZE


def write_section_header(data, offset, name, virtual_size, virtual_address, raw_size, raw_pointer, characteristics):
    data[offset : offset + 8] = name.ljust(8, b"\x00")
    struct.pack_into("<I", data, offset + 8, virtual_size)
    struct.pack_into("<I", data, offset + 12, virtual_address)
    struct.pack_into("<I", data, offset + 16, raw_size)
    struct.pack_into("<I", data, offset + 20, raw_pointer)
    struct.pack_into("<I", data, offset + 24, 0)
    struct.pack_into("<I", data, offset + 28, 0)
    struct.pack_into("<H", data, offset + 32, 0)
    struct.pack_into("<H", data, offset + 34, 0)
    struct.pack_into("<I", data, offset + 36, characteristics)


def fake_original_image() -> bytes:
    data = bytearray(b"\x00" * ORIGINAL_SIZE)

    pe_offset = 0x130
    optional_offset = pe_offset + 24
    section_table = optional_offset + 224
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset : pe_offset + 4] = b"PE\x00\x00"
    struct.pack_into("<H", data, pe_offset + 4, 0x14C)
    struct.pack_into("<H", data, pe_offset + 6, 6)
    struct.pack_into("<H", data, pe_offset + 20, 224)
    struct.pack_into("<H", data, optional_offset, 0x10B)
    struct.pack_into("<I", data, optional_offset + 28, 0x400000)
    struct.pack_into("<I", data, optional_offset + 32, 0x1000)
    struct.pack_into("<I", data, optional_offset + 36, 0x200)
    struct.pack_into("<I", data, optional_offset + 56, 0x16B000)
    struct.pack_into("<I", data, optional_offset + 60, 0x400)

    sections = [
        (b".text", 0xEE9C8, 0x1000, 0xEEA00, 0x400, 0x60000020),
        (b".rdata", 0x6C714, 0xF0000, 0x6C800, 0xEEE00, 0x40000040),
        (b".data", 0x2DEC, 0x15D000, 0x1A00, 0x15B600, 0xC0000040),
        (b"_RDATA", 0x5E0, 0x160000, 0x600, 0x15D000, 0x40000040),
        (b".rsrc", 0x2830, 0x161000, 0x2A00, 0x15D600, 0x40000040),
        (b".reloc", 0x6448, 0x164000, 0x6600, 0x160000, 0x42000040),
    ]
    for index, section in enumerate(sections):
        write_section_header(data, section_table + index * 40, *section)

    for site in patcher.original_patch_sites():
        data[site.offset : site.offset + len(site.original)] = site.original
    for site in patcher.original_patch_sites(include_draw_hook=False, include_diagnostics=True):
        if site.name.endswith("diagnostic hook"):
            data[site.offset : site.offset + len(site.original)] = site.original
    data[0x31A3F:0x31A41] = bytes.fromhex("6a 3c")
    data[patcher.TICK_THRESHOLD_OFFSET : patcher.TICK_THRESHOLD_OFFSET + 7] = bytes.fromhex(
        "83 be c8 0c 04 00 3c"
    )
    data[
        patcher.LEGACY_CALL_OFFSET : patcher.LEGACY_CALL_OFFSET
        + len(patcher.LEGACY_ORIGINAL_CALL_BYTES)
    ] = patcher.LEGACY_ORIGINAL_CALL_BYTES
    data[
        patcher.LEGACY_CAVE_OFFSET : patcher.LEGACY_CAVE_OFFSET
        + patcher.LEGACY_CAVE_SIZE
    ] = patcher.LEGACY_ORIGINAL_CAVE_BYTES
    return bytes(data)


def fake_legacy_render_only_image(refresh_hz=240) -> bytes:
    data, info, section, _labels = patcher.install_or_update_patch_section(
        fake_original_image(),
        refresh_hz,
    )
    section_address = patcher.section_va(info, section)
    payload, labels = patcher.build_patch_section(
        section_address,
        refresh_hz,
        include_draw_hook=False,
        include_update_hook=False,
        include_rotation_offset_interpolation=False,
    )
    legacy = bytearray(data)
    legacy[section.raw_pointer : section.raw_pointer + len(payload)] = payload
    for site in patcher.patched_sites(
        section_address,
        labels,
        refresh_hz,
        include_draw_hook=False,
        include_update_hook=False,
    ):
        legacy[site.offset : site.offset + len(site.replacement)] = site.replacement
    return bytes(legacy)


def fake_legacy_no_wall_angle_image(refresh_hz=240) -> bytes:
    data, info, section, _labels = patcher.install_or_update_patch_section(
        fake_original_image(),
        refresh_hz,
    )
    section_address = patcher.section_va(info, section)
    payload, labels = patcher.build_patch_section(
        section_address,
        refresh_hz,
        include_update_hook=False,
        include_wall_angle_interpolation=False,
        include_rotation_offset_interpolation=False,
    )
    legacy = bytearray(data)
    legacy[section.raw_pointer : section.raw_pointer + len(payload)] = payload
    for site in patcher.patched_sites(
        section_address,
        labels,
        refresh_hz,
        include_update_hook=False,
    ):
        legacy[site.offset : site.offset + len(site.replacement)] = site.replacement
    return bytes(legacy)


def fake_legacy_no_rotation_offset_image(refresh_hz=240) -> bytes:
    data, info, section, _labels = patcher.install_or_update_patch_section(
        fake_original_image(),
        refresh_hz,
    )
    section_address = patcher.section_va(info, section)
    payload, labels = patcher.build_patch_section(
        section_address,
        refresh_hz,
        include_update_hook=False,
        include_rotation_offset_interpolation=False,
    )
    legacy = bytearray(data)
    legacy[section.raw_pointer : section.raw_pointer + len(payload)] = payload
    for site in patcher.patched_sites(
        section_address,
        labels,
        refresh_hz,
        include_update_hook=False,
    ):
        legacy[site.offset : site.offset + len(site.replacement)] = site.replacement
    return bytes(legacy)


def fake_legacy_high_tick_image(refresh_hz=240) -> bytes:
    data, info, section, _labels = patcher.install_or_update_patch_section(
        fake_original_image(),
        refresh_hz,
    )
    section_address = patcher.section_va(info, section)
    payload, labels = patcher.build_patch_section(
        section_address,
        refresh_hz,
        include_draw_hook=False,
        include_update_hook=False,
        include_high_tick_legacy_hooks=True,
        include_rotation_offset_interpolation=False,
    )
    legacy = bytearray(data)
    legacy[section.raw_pointer : section.raw_pointer + len(payload)] = payload
    for site in patcher.patched_sites(
        section_address,
        labels,
        refresh_hz,
        include_draw_hook=False,
        include_update_hook=False,
        include_high_tick_legacy_sites=True,
    ):
        legacy[site.offset : site.offset + len(site.replacement)] = site.replacement
    return bytes(legacy)


class PatchImageTests(unittest.TestCase):
    def test_patch_240_adds_section_and_hooks_interpolated_rendering(self):
        patched, state, changed = patcher.patch_image(fake_original_image(), refresh_hz=240, force=True)

        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")
        self.assertEqual(state.refresh_hz, 240)
        self.assertGreater(len(patched), ORIGINAL_SIZE)

        # The simulation divisor and its 60-tick threshold must remain original.
        sim_divisor_push = patched[0x31A3F : 0x31A41]
        self.assertEqual(sim_divisor_push, bytes.fromhex("6a 3c"))
        sim_divisor_call = patched[
            patcher.LEGACY_CALL_OFFSET : patcher.LEGACY_CALL_OFFSET
            + len(patcher.LEGACY_ORIGINAL_CALL_BYTES)
        ]
        self.assertEqual(sim_divisor_call, patcher.LEGACY_ORIGINAL_CALL_BYTES)

        tick_threshold = patched[
            patcher.TICK_THRESHOLD_OFFSET : patcher.TICK_THRESHOLD_OFFSET + 7
        ]
        self.assertEqual(tick_threshold, bytes.fromhex("83 be c8 0c 04 00 3c"))

        draw_hook = patched[
            patcher.DRAW_HOOK_OFFSET : patcher.DRAW_HOOK_OFFSET
            + len(patcher.DRAW_HOOK_ORIGINAL_BYTES)
        ]
        self.assertNotEqual(draw_hook, patcher.DRAW_HOOK_ORIGINAL_BYTES)

        info = patcher.parse_pe(patched)
        section = patcher.patch_section(info)
        self.assertIsNotNone(section)
        self.assertTrue(section.characteristics & patcher.IMAGE_SCN_MEM_WRITE)

        update_hook = patched[
            patcher.UPDATE_HOOK_OFFSET : patcher.UPDATE_HOOK_OFFSET
            + len(patcher.UPDATE_HOOK_ORIGINAL_BYTES)
        ]
        self.assertNotEqual(update_hook, patcher.UPDATE_HOOK_ORIGINAL_BYTES)

    def test_draw_hook_preserves_draw_call_stack_contract(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]

        self.assertIn(bytes.fromhex("8b ce e8"), draw_hook)
        self.assertTrue(draw_hook.rstrip(b"\x00\x90").endswith(bytes.fromhex("5d 5e c3")))

    def test_draw_hook_uses_non_overlapping_local_slots(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]

        self.assertIn(bytes.fromhex("83 ec 18"), draw_hook)
        self.assertIn(bytes.fromhex("89 44 24 08"), draw_hook)
        self.assertIn(bytes.fromhex("f2 0f 11 44 24 10"), draw_hook)
        self.assertIn(bytes.fromhex("f2 0f 10 44 24 10"), draw_hook)
        self.assertNotIn(bytes.fromhex("f2 0f 11 44 24 08"), draw_hook)

    def test_draw_hook_interpolates_obstacle_segments_temporarily(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]

        self.assertIn(bytes.fromhex("8b 8e 20 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("8d 96 14 02 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 10 96 70 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 10 96 b0 54 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 10 96 68 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("29 02 29 42 04"), draw_hook)
        self.assertIn(bytes.fromhex("01 02 01 42 04"), draw_hook)

    def test_draw_hook_interpolates_wall_angle_temporarily(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]

        self.assertIn(bytes.fromhex("8b 86 b8 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("89 44 24 08"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 10 8e b8 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("f2 0f 59 86 50 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 11 8e b8 29 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("89 86 b8 29 00 00"), draw_hook)

    def test_draw_hook_interpolates_rotation_offset_from_previous_update(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        update_offset = labels["update"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]
        update_hook = payload[update_offset : update_offset + 0x80]

        previous_rva = labels["previous_rotation_offset"] - patcher.SUPPORTED_IMAGE_BASE
        float_360_rva = labels["float_360"] - patcher.SUPPORTED_IMAGE_BASE

        self.assertIn(bytes.fromhex("8b 86 a0 01 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("89 44 24 0c"), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 5c 8d") + struct.pack("<I", previous_rva), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 58 85") + struct.pack("<I", float_360_rva), draw_hook)
        self.assertIn(bytes.fromhex("f3 0f 11 86 a0 01 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("89 86 a0 01 00 00"), draw_hook)
        self.assertIn(bytes.fromhex("8b 91 a0 01 00 00"), update_hook)
        self.assertIn(bytes.fromhex("89 90") + struct.pack("<I", previous_rva), update_hook)

    def test_draw_hook_does_not_embed_unrelocated_absolute_addresses(self):
        payload, labels = patcher.build_patch_section(0x56B000, 240)
        draw_offset = labels["draw"] - 0x56B000
        draw_end = labels["update"] - 0x56B000
        draw_hook = payload[draw_offset:draw_end]

        self.assertNotIn(struct.pack("<I", patcher.TIMER_POINTER_VA), draw_hook)
        self.assertNotIn(struct.pack("<I", patcher.DOUBLE_ONE_VA), draw_hook)
        self.assertIn(struct.pack("<I", patcher.TIMER_POINTER_RVA), draw_hook)
        self.assertIn(struct.pack("<I", patcher.DOUBLE_ONE_RVA), draw_hook)
        self.assertIn(struct.pack("<I", patcher.FLOAT_ONE_RVA), draw_hook)
        self.assertIn(struct.pack("<I", patcher.DOUBLE_FIVE_RVA), draw_hook)
        self.assertIn(
            struct.pack("<I", labels["previous_rotation_offset"] - patcher.SUPPORTED_IMAGE_BASE),
            draw_hook,
        )

    def test_patch_can_update_refresh(self):
        patched, _, _ = patcher.patch_image(fake_original_image(), refresh_hz=240, force=True)
        updated, state, changed = patcher.patch_image(patched, refresh_hz=120)

        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")
        self.assertEqual(state.refresh_hz, 120)
        self.assertEqual(patcher.current_render_divisor(updated), 120)

    def test_diagnostic_patch_adds_runtime_counters_and_hooks(self):
        patched, state, changed = patcher.patch_image(
            fake_original_image(),
            refresh_hz=240,
            force=True,
            diagnostics=True,
        )

        self.assertTrue(changed)
        self.assertEqual(state.status, "diagnostic")
        self.assertEqual(state.refresh_hz, 240)

        info = patcher.parse_pe(patched)
        section = patcher.patch_section(info)
        self.assertIsNotNone(section)
        self.assertTrue(section.characteristics & patcher.IMAGE_SCN_MEM_WRITE)

        payload, labels = patcher.build_patch_section(
            patcher.section_va(info, section),
            240,
            include_diagnostics=True,
        )
        for name in patcher.DIAGNOSTIC_COUNTER_LABELS:
            self.assertIn(name, labels)
            offset = labels[name] - patcher.section_va(info, section)
            self.assertEqual(payload[offset : offset + 4], b"\x00\x00\x00\x00")

        self.assertNotEqual(
            patched[
                patcher.UPDATE_HOOK_OFFSET : patcher.UPDATE_HOOK_OFFSET
                + len(patcher.UPDATE_HOOK_ORIGINAL_BYTES)
            ],
            patcher.UPDATE_HOOK_ORIGINAL_BYTES,
        )
        self.assertNotEqual(
            patched[
                patcher.SWAP_HOOK_OFFSET : patcher.SWAP_HOOK_OFFSET
                + len(patcher.SWAP_HOOK_ORIGINAL_BYTES)
            ],
            patcher.SWAP_HOOK_ORIGINAL_BYTES,
        )

    def test_diagnostic_patch_can_return_to_normal_patch(self):
        diagnostic, _, _ = patcher.patch_image(
            fake_original_image(),
            refresh_hz=240,
            force=True,
            diagnostics=True,
        )
        normal, state, changed = patcher.patch_image(diagnostic, refresh_hz=240)

        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")
        info = patcher.parse_pe(normal)
        section = patcher.patch_section(info)
        self.assertIsNotNone(section)
        section_address = patcher.section_va(info, section)
        _payload, labels = patcher.build_patch_section(section_address, 240)
        normal_sites = patcher.patched_sites(section_address, labels, 240)
        update_site = next(site for site in normal_sites if site.name == "update hook")
        self.assertEqual(
            normal[
                patcher.UPDATE_HOOK_OFFSET : patcher.UPDATE_HOOK_OFFSET
                + len(patcher.UPDATE_HOOK_ORIGINAL_BYTES)
            ],
            update_site.replacement,
        )
        self.assertEqual(
            normal[
                patcher.SWAP_HOOK_OFFSET : patcher.SWAP_HOOK_OFFSET
                + len(patcher.SWAP_HOOK_ORIGINAL_BYTES)
            ],
            patcher.SWAP_HOOK_ORIGINAL_BYTES,
        )

        self.assertTrue(section.characteristics & patcher.IMAGE_SCN_MEM_WRITE)

    def test_patch_60_restores_original_layout(self):
        patched, _, _ = patcher.patch_image(fake_original_image(), refresh_hz=240, force=True)
        restored, state, changed = patcher.patch_image(patched, refresh_hz=60)

        self.assertTrue(changed)
        self.assertEqual(state.status, "original")
        self.assertEqual(len(restored), ORIGINAL_SIZE)
        self.assertIsNone(patcher.patch_section(patcher.parse_pe(restored)))

    def test_unpatch_restores_original_layout(self):
        original = fake_original_image()
        patched, _, _ = patcher.patch_image(original, refresh_hz=240, force=True)
        restored, state, changed = patcher.unpatch_image(patched)

        self.assertTrue(changed)
        self.assertEqual(state.status, "original")
        self.assertEqual(restored, original)

    def test_legacy_speed_patch_is_migrated(self):
        legacy = bytearray(fake_original_image())
        legacy[
            patcher.LEGACY_CALL_OFFSET : patcher.LEGACY_CALL_OFFSET
            + len(patcher.LEGACY_ORIGINAL_CALL_BYTES)
        ] = patcher.legacy_call_to_cave_bytes()
        legacy[
            patcher.LEGACY_CAVE_OFFSET : patcher.LEGACY_CAVE_OFFSET
            + patcher.LEGACY_CAVE_SIZE
        ] = (
            patcher.LEGACY_CAVE_PREFIX
            + struct.pack("<I", 240)
            + b"\xe9"
            + patcher.checked_rel32(patcher.LEGACY_CAVE_VA + 8, patcher.LEGACY_DIV_ROUTINE_VA)
        )

        state = patcher.analyze_image(bytes(legacy))
        self.assertEqual(state.status, "legacy-speedup")

        patched, state, changed = patcher.patch_image(bytes(legacy), refresh_hz=240)
        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")
        self.assertEqual(
            patched[
                patcher.LEGACY_CALL_OFFSET : patcher.LEGACY_CALL_OFFSET
                + len(patcher.LEGACY_ORIGINAL_CALL_BYTES)
            ],
            patcher.LEGACY_ORIGINAL_CALL_BYTES,
        )

    def test_legacy_render_only_patch_is_migrated(self):
        legacy = fake_legacy_render_only_image(refresh_hz=240)

        state = patcher.analyze_image(legacy)
        self.assertEqual(state.status, "legacy-render-only")

        patched, state, changed = patcher.patch_image(legacy, refresh_hz=240)
        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")

        tick_threshold = patched[
            patcher.TICK_THRESHOLD_OFFSET : patcher.TICK_THRESHOLD_OFFSET + 7
        ]
        self.assertEqual(tick_threshold, bytes.fromhex("83 be c8 0c 04 00 3c"))

        draw_hook = patched[
            patcher.DRAW_HOOK_OFFSET : patcher.DRAW_HOOK_OFFSET
            + len(patcher.DRAW_HOOK_ORIGINAL_BYTES)
        ]
        self.assertNotEqual(draw_hook, patcher.DRAW_HOOK_ORIGINAL_BYTES)

    def test_legacy_no_wall_angle_patch_is_migrated(self):
        legacy = fake_legacy_no_wall_angle_image(refresh_hz=240)

        state = patcher.analyze_image(legacy)
        self.assertEqual(state.status, "legacy-no-wall-angle")

        patched, state, changed = patcher.patch_image(legacy, refresh_hz=240)
        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")

        info = patcher.parse_pe(patched)
        section = patcher.patch_section(info)
        self.assertIsNotNone(section)
        payload, labels = patcher.build_patch_section(patcher.section_va(info, section), 240)
        draw_offset = labels["draw"] - patcher.section_va(info, section)
        draw_end = labels["update"] - patcher.section_va(info, section)
        draw_hook = payload[draw_offset:draw_end]
        self.assertIn(bytes.fromhex("f3 0f 11 8e b8 29 00 00"), draw_hook)

    def test_legacy_no_rotation_offset_patch_is_migrated(self):
        legacy = fake_legacy_no_rotation_offset_image(refresh_hz=240)

        state = patcher.analyze_image(legacy)
        self.assertEqual(state.status, "legacy-no-rotation-offset")

        patched, state, changed = patcher.patch_image(legacy, refresh_hz=240)
        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")

        info = patcher.parse_pe(patched)
        section = patcher.patch_section(info)
        self.assertIsNotNone(section)
        payload, labels = patcher.build_patch_section(patcher.section_va(info, section), 240)
        self.assertIn("previous_rotation_offset", labels)
        update_site = next(
            site for site in patcher.patched_sites(patcher.section_va(info, section), labels, 240)
            if site.name == "update hook"
        )
        self.assertEqual(
            patched[
                patcher.UPDATE_HOOK_OFFSET : patcher.UPDATE_HOOK_OFFSET
                + len(patcher.UPDATE_HOOK_ORIGINAL_BYTES)
            ],
            update_site.replacement,
        )

    def test_legacy_high_tick_patch_is_migrated(self):
        legacy = fake_legacy_high_tick_image(refresh_hz=240)

        state = patcher.analyze_image(legacy)
        self.assertEqual(state.status, "legacy-high-tick")

        patched, state, changed = patcher.patch_image(legacy, refresh_hz=240)
        self.assertTrue(changed)
        self.assertEqual(state.status, "patched")
        self.assertEqual(
            patched[
                patcher.LEGACY_CALL_OFFSET : patcher.LEGACY_CALL_OFFSET
                + len(patcher.LEGACY_ORIGINAL_CALL_BYTES)
            ],
            patcher.LEGACY_ORIGINAL_CALL_BYTES,
        )
        self.assertEqual(
            patched[patcher.TICK_THRESHOLD_OFFSET : patcher.TICK_THRESHOLD_OFFSET + 7],
            bytes.fromhex("83 be c8 0c 04 00 3c"),
        )

    def test_unknown_hash_requires_force(self):
        with self.assertRaises(patcher.PatchError):
            patcher.patch_image(fake_original_image(), refresh_hz=240, force=False)

    def test_invalid_refresh_is_rejected(self):
        with self.assertRaises(patcher.PatchError):
            patcher.patch_image(fake_original_image(), refresh_hz=144, force=True)


if __name__ == "__main__":
    unittest.main()
