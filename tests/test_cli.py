from __future__ import annotations

import unittest

from superhexagon_fps_unlocker import cli


class CliTests(unittest.TestCase):
    def test_public_refresh_choices(self) -> None:
        self.assertEqual(cli.PATCH_REFRESH_CHOICES, (120, 180, 240, 300, 360))

    def test_backends_are_registered(self) -> None:
        self.assertEqual(set(cli.BACKENDS), {"neo", "pre-neo"})

    def test_parser_defaults_to_status(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.command)


if __name__ == "__main__":
    unittest.main()

