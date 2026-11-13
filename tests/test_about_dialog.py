# -*- coding: utf-8 -*-
"""
关于对话框与构建信息测试

覆盖：版本号单一来源、正文行数与关键字段、打包态读取构建信息、对话框尺寸紧凑。
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gui.dialogs.about_dialog import AboutDialog  # noqa: E402
from gui.utils import build_info  # noqa: E402


class BuildInfoTest(unittest.TestCase):

    def test_version_is_single_source_date_version(self):
        self.assertRegex(build_info.VERSION, r"^\d{4}\.\d{2}$")

    def test_about_lines_are_compact_and_contain_key_fields(self):
        lines = build_info.about_lines()
        self.assertLessEqual(len(lines), 9)
        text = "\n".join(lines)
        self.assertEqual(lines[0], build_info.APP_NAME)
        self.assertIn(f"版本: {build_info.VERSION}", text)
        self.assertIn("构建:", text)
        self.assertIn("提交:", text)
        self.assertIn("运行:", text)
        self.assertIn("环境:", text)
        self.assertNotIn("更新日志", text)

    def test_frozen_reads_embedded_build_stamp(self):
        stamp = {"commit": "abc1234", "build_time": "2026-11-13 18:00:00"}
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        stamp_path = Path(temp.name) / "build_info.json"
        stamp_path.write_text(json.dumps(stamp), encoding="utf-8")

        with mock.patch.object(build_info, "is_frozen", return_value=True), \
                mock.patch.object(build_info, "resource_path", return_value=stamp_path):
            self.assertEqual(build_info.get_commit(), "abc1234")
            # 打包态构建时间取 exe 修改时间，格式应为日期时间
            self.assertRegex(build_info.get_build_time(),
                             r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class AboutDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_is_compact(self):
        dialog = AboutDialog()
        self.addCleanup(dialog.deleteLater)

        self.assertTrue(dialog.isModal())
        self.assertLessEqual(dialog.width(), 480)
        self.assertLessEqual(dialog.height(), 420)
        self.assertIn("关于", dialog.windowTitle())

    def test_dialog_contains_version_and_commit(self):
        from PyQt5.QtWidgets import QLabel

        dialog = AboutDialog()
        self.addCleanup(dialog.deleteLater)

        text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        self.assertIn(build_info.VERSION, text)
        self.assertIn("提交:", text)
        self.assertIn("运行:", text)


if __name__ == "__main__":
    unittest.main()
