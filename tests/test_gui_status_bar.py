# -*- coding: utf-8 -*-
"""
状态栏测试

覆盖：状态消息只出现在右侧“就绪”位置，不在左侧重复，也不挤掉硬件/阶段信息。
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gui.main_window import MainWindow  # noqa: E402


class StatusBarTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_window(self):
        # 跳过启动配置加载，避免依赖本机配置/弹窗
        with mock.patch.object(MainWindow, "_load_startup_config"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        return window

    def test_status_message_not_shown_on_both_sides(self):
        window = self._make_window()

        window.set_status("配置已加载")

        self.assertEqual(window.ready_label.text(), "配置已加载")
        self.assertEqual(window.status_bar.currentMessage(), "")

    def test_hardware_and_stage_labels_stay_visible(self):
        window = self._make_window()
        window.hw_status_label.setText("硬件: 已连接")
        window.stage_label.setText("阶段: 构建")

        window.set_status("执行中...")

        self.assertEqual(window.hw_status_label.text(), "硬件: 已连接")
        self.assertEqual(window.stage_label.text(), "阶段: 构建")
        self.assertFalse(window.hw_status_label.isHidden())
        self.assertFalse(window.stage_label.isHidden())


if __name__ == "__main__":
    unittest.main()
