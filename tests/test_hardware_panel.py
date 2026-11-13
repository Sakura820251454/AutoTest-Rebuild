# -*- coding: utf-8 -*-
"""
硬件检测面板测试

覆盖：关键行筛选、GEL 原始输出折叠、检测失败/无法检测时指示灯为“未连接”。
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gui.widgets.hardware_panel import HardwarePanel, is_key_line  # noqa: E402


def make_paths(ccxml="", ccs_exe="", ccs_dss=""):
    return SimpleNamespace(ccxml=ccxml, ccs_executable=ccs_exe, ccs_dss=ccs_dss)


class KeyLineTest(unittest.TestCase):

    def test_gel_noise_is_not_key_line(self):
        self.assertFalse(is_key_line("GEL: 正在连接目标设备..."))
        self.assertFalse(is_key_line("已停止现有调试会话"))
        self.assertFalse(is_key_line(""))

    def test_status_and_config_lines_are_key(self):
        for text in ("SUCCESS: 硬件连接成功", "FAILED: 连接异常",
                     "CCXML 文件: C:/x.ccxml", "设备名称: F28335",
                     "硬件连接检测成功", "错误: DSS 执行器不存在"):
            self.assertTrue(is_key_line(text), text)


class HardwarePanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = HardwarePanel()
        self.addCleanup(self.panel.deleteLater)

    def test_missing_tools_marks_indicators_as_not_connected(self):
        self.panel.config = SimpleNamespace(
            paths=make_paths("C:/no/x.ccxml", "C:/no/eclipsec.exe", "C:/no/dss.bat"),
            test=SimpleNamespace(device="F28335", cpu="C28xx"))
        self.panel._config_available = True

        with mock.patch("gui.widgets.hardware_panel.warning"):
            self.panel.start_check()

        self.assertEqual(self.panel.emulator_indicator.status_text.text(), "未连接")
        self.assertEqual(self.panel.target_indicator.status_text.text(), "未连接")
        self.assertIn("原因：", self.panel.result_text.toPlainText())

    def test_failed_check_uses_not_connected_instead_of_unknown(self):
        self.panel.emulator_indicator.set_checking()
        self.panel.target_indicator.set_checking()

        self.panel.on_check_completed(False, "硬件连接失败")

        self.assertEqual(self.panel.emulator_indicator.status_text.text(), "未连接")
        self.assertEqual(self.panel.target_indicator.status_text.text(), "未连接")

    def test_raw_output_is_folded_and_noise_hidden(self):
        self.panel.on_log_message("GEL: 初始化脚本环境...")
        self.panel.on_log_message("some java stack line")

        self.assertTrue(self.panel.raw_toggle.isVisible() or not self.panel.raw_toggle.isHidden())
        self.assertIn("初始化脚本环境", self.panel.raw_text.toPlainText())
        self.assertNotIn("初始化脚本环境", self.panel.result_text.toPlainText())
        self.assertTrue(self.panel.raw_text.isHidden())

        self.panel.raw_toggle.setChecked(True)
        self.assertFalse(self.panel.raw_text.isHidden())
        self.assertIn("隐藏 GEL 原始输出", self.panel.raw_toggle.text())

    def test_key_lines_shown_in_result_area(self):
        self.panel.on_log_message("SUCCESS: 硬件连接成功")

        self.assertIn("SUCCESS: 硬件连接成功", self.panel.result_text.toPlainText())
        self.assertIn("SUCCESS: 硬件连接成功", self.panel.raw_text.toPlainText())

    def test_raw_output_cleared_on_new_check(self):
        self.panel.on_log_message("GEL noise")
        self.panel.raw_toggle.setChecked(True)

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "x.ccxml").write_text("", encoding="utf-8")
        (root / "eclipsec.exe").write_text("", encoding="utf-8")
        (root / "dss.bat").write_text("", encoding="utf-8")
        self.panel.config = SimpleNamespace(
            paths=make_paths(str(root / "x.ccxml"), str(root / "eclipsec.exe"),
                             str(root / "dss.bat")),
            test=SimpleNamespace(device="F28335", cpu="C28xx"))
        self.panel._config_available = True

        # 只验证清理动作，不真正启动 DSS
        with mock.patch("gui.widgets.hardware_panel.HardwareChecker") as checker_cls:
            checker_cls.return_value = mock.Mock()
            self.panel.start_check()

        self.assertEqual(self.panel.raw_text.toPlainText(), "")
        self.assertFalse(self.panel.raw_toggle.isChecked())


if __name__ == "__main__":
    unittest.main()
