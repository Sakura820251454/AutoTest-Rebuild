# -*- coding: utf-8 -*-
"""
应用图标与高 DPI 配置测试

覆盖：app.ico 存在且包含 16/32/48/256 多尺寸、spec 引用图标、
run_gui 的应用标识把图标设进 QApplication。
"""

import os
import struct
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from src.runtime_paths import resource_path  # noqa: E402


class AppIconTest(unittest.TestCase):

    def test_ico_has_required_sizes(self):
        path = resource_path("gui/assets/app.ico")
        self.assertTrue(path.is_file(), path)

        data = path.read_bytes()
        reserved, image_type, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, image_type), (0, 1))
        self.assertGreaterEqual(count, 4)

        sizes = set()
        for i in range(count):
            offset = 6 + i * 16
            width = data[offset] or 256
            height = data[offset + 1] or 256
            self.assertEqual(width, height)
            sizes.add(width)
        self.assertTrue({16, 32, 48, 256}.issubset(sizes), sizes)

    def test_spec_references_icon(self):
        from pathlib import Path

        spec_path = Path(__file__).resolve().parents[1] / "_packaging" / "AutoTestGUI.spec"
        text = spec_path.read_text(encoding="utf-8")
        self.assertIn('gui" / "assets" / "app.ico', text)
        self.assertIn("icon=str(PROJECT_ROOT", text)

    def test_apply_app_identity_sets_window_icon(self):
        from run_gui import _apply_app_identity

        app = QApplication.instance() or QApplication([])
        _apply_app_identity(app)

        self.assertFalse(app.windowIcon().isNull())
        self.assertEqual(app.organizationName(), "AutoTest")


if __name__ == "__main__":
    unittest.main()
