# -*- coding: utf-8 -*-
"""
执行面板 GUI 回归测试（Qt offscreen，不弹窗）

覆盖：断点续测复选框与起始批次联动、时间戳恢复（配置的结果目录 / 旧 5_result_dat / 无结果）。
app_path 已 monkeypatch 到临时目录，不会读取真实 logs 与 full_regr.json。
"""

import os
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt                      # noqa: E402
from PyQt5.QtWidgets import QApplication          # noqa: E402

from tests.helpers import TempTestCase, make_config   # noqa: E402
from gui.widgets import execute_panel as execute_panel_module  # noqa: E402
from gui.widgets.execute_panel import ExecutePanel   # noqa: E402


class ExecutePanelTest(TempTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ExecutePanel()
        self.addCleanup(self.panel.deleteLater)
        self.app_root = self.make_dir("app_root")
        patcher = mock.patch.object(execute_panel_module, "app_path",
                                    side_effect=lambda rel="": self.app_root / rel)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_resume_checkbox_toggles_batch_spin(self):
        self.assertFalse(self.panel.resume_batch_spin.isEnabled())

        self.panel.on_resume_checkbox_changed(Qt.Checked)
        self.assertTrue(self.panel.resume_batch_spin.isEnabled())

        self.panel.on_resume_checkbox_changed(Qt.Unchecked)
        self.assertFalse(self.panel.resume_batch_spin.isEnabled())

    def test_recovers_latest_timestamp_from_configured_results_dir(self):
        cfg = make_config(self.tmp)
        older = self.make_dir("results", "2026-01-01-08-00")
        newer = self.make_dir("results", "2026-02-02-09-30")
        now = time.time()
        os.utime(str(older), (now - 1000, now - 1000))
        os.utime(str(newer), (now, now))
        self.panel.set_config(cfg)

        self.assertEqual(self.panel._recover_timestamp_from_results(), "2026-02-02-09-30")

    def test_ignores_non_timestamp_directories(self):
        cfg = make_config(self.tmp)
        self.make_dir("results", "not-a-timestamp")
        self.panel.set_config(cfg)

        self.assertIsNone(self.panel._recover_timestamp_from_results())

    def test_falls_back_to_legacy_5_result_dat(self):
        cfg = make_config(self.tmp)
        self.make_dir("results")
        self.make_dir("app_root", "5_result_dat", "2025-12-31-23-59")
        self.panel.set_config(cfg)

        self.assertEqual(self.panel._recover_timestamp_from_results(), "2025-12-31-23-59")

    def test_returns_none_when_no_results_anywhere(self):
        cfg = make_config(self.tmp)
        self.make_dir("results")
        self.panel.set_config(cfg)

        self.assertIsNone(self.panel._recover_timestamp_from_results())


if __name__ == "__main__":
    unittest.main()
