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

    def test_execution_finished_message_survives_stage_detect(self):
        """结束提示不能被随后（或先前）的阶段检测文案覆盖"""
        window = self._make_window()
        window.execute_panel.stopped = False

        window.on_execution_finished(True)

        self.assertEqual(window.ready_label.text(), "执行完成")

    def test_stopped_execution_keeps_summary(self):
        """停止结束时保留工作线程的摘要文案"""
        window = self._make_window()
        window.execute_panel.stopped = True
        window.execute_panel.stats_label.setText("已停止（完成 1/3）| 成功: 1 | 失败: 0 | 跳过: 2")

        window.on_execution_finished(False)

        self.assertEqual(window.ready_label.text(),
                         "已停止（完成 1/3）| 成功: 1 | 失败: 0 | 跳过: 2")

    def test_mark_execute_tab_when_user_on_other_tab(self):
        """不在执行页时用页签标记结果并触发任务栏提醒，切回后清除"""
        window = self._make_window()
        window.execute_panel.stopped = False
        window.tab_widget.setCurrentWidget(window.log_panel)

        with mock.patch.object(QApplication, "alert") as alert:
            window.on_execution_finished(True)
            alert.assert_called_once()

        idx = window.tab_widget.indexOf(window.execute_panel)
        self.assertEqual(window.tab_widget.tabText(idx), "执行 ✓")

        window.tab_widget.setCurrentWidget(window.execute_panel)
        self.assertEqual(window.tab_widget.tabText(idx), "执行")


if __name__ == "__main__":
    unittest.main()
