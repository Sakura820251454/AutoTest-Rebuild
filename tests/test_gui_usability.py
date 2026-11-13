# -*- coding: utf-8 -*-
"""
GUI 易用性回归测试（不连板、不启动 DSS）

覆盖：启动配置选择优先级（-c / config.json / 上次使用 / 空态）、统一错误文案、
日志页转义与换行与级别过滤与内存上限、未加载配置的禁用态与 tooltip、
执行页错误条与结果目录提示、用例表右键路径解析、worker 日志真实级别。
"""

import json
import logging
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

_APP = QApplication.instance() or QApplication([])

from tests.helpers import TempTestCase, make_config  # noqa: E402
from src.exceptions import ConfigFileNotFoundError  # noqa: E402
from gui.main_window import resolve_startup_config  # noqa: E402
from gui.utils.error_messages import describe_exception, format_error  # noqa: E402
from gui.widgets import log_panel as log_panel_module  # noqa: E402
from gui.widgets.log_panel import LogPanel, format_log_html  # noqa: E402
from gui.widgets.execute_panel import ExecutePanel  # noqa: E402
from gui.widgets.hardware_panel import HardwarePanel  # noqa: E402
from gui.widgets.config_panel import ConfigPanel  # noqa: E402
from gui.widgets.case_table import CaseTable  # noqa: E402
from gui.workers.pipeline_worker import GUILogHandler, PipelineWorker  # noqa: E402


class FakeWorker:
    """只实现 ExecutePanel 用到的接口"""

    def __init__(self, running=False, stop_requested=False, summary=""):
        self._running = running
        self.stop_requested = stop_requested
        self.final_summary = summary

    def isRunning(self):
        return self._running

    def stop(self):
        self._running = False


class StartupConfigTest(TempTestCase):
    """启动配置选择：显式 > 默认 > 上次使用 > 空态"""

    def test_explicit_wins(self):
        explicit = self.write_text("explicit.json", "{}")
        default = self.write_text("config/config.json", "{}")
        self.assertEqual(resolve_startup_config(explicit, default, None), explicit)

    def test_default_wins_over_last(self):
        default = self.write_text("config/config.json", "{}")
        last = self.write_text("last.json", "{}")
        self.assertEqual(resolve_startup_config(None, default, last), default)

    def test_last_used_when_default_missing(self):
        last = self.write_text("last.json", "{}")
        missing = self.tmp / "config" / "config.json"
        self.assertEqual(resolve_startup_config(None, missing, last), last)

    def test_empty_state_when_nothing_exists(self):
        self.assertIsNone(resolve_startup_config(
            None, self.tmp / "config" / "config.json", self.tmp / "last.json"))

    def test_missing_explicit_falls_back(self):
        default = self.write_text("config/config.json", "{}")
        self.assertEqual(
            resolve_startup_config(self.tmp / "gone.json", default, None), default)


class ErrorMessageTest(TempTestCase):
    """统一错误文案：原因 + 路径 + 建议，不含 traceback / Python 原文"""

    def test_format_error_sections(self):
        text = format_error("目录不可写", path="D:/out", action="请换一个目录")
        self.assertIn("原因：目录不可写", text)
        self.assertIn("路径：D:/out", text)
        self.assertIn("建议：请换一个目录", text)
        self.assertEqual(text.count("\n"), 2)

    def test_json_error_is_readable(self):
        try:
            json.loads("{bad json}")
        except json.JSONDecodeError as exc:
            text = describe_exception(exc, path="D:/cfg/config.json")
        self.assertIn("配置文件格式错误", text)
        self.assertIn("第 1 行", text)
        self.assertIn("路径：D:/cfg/config.json", text)
        self.assertIn("建议：", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("json.decoder", text)

    def test_file_not_found_uses_filename(self):
        text = describe_exception(FileNotFoundError(2, "No such file", "D:/a/b.json"))
        self.assertIn("找不到文件或目录", text)
        self.assertIn("D:/a/b.json", text)

    def test_config_exception_is_chinese(self):
        text = describe_exception(ConfigFileNotFoundError("D:/cfg/config.json"))
        self.assertIn("配置文件不存在", text)
        self.assertIn("D:/cfg/config.json", text)
        self.assertNotIn("[E1001]", text)


class LogPanelTest(TempTestCase):
    """日志页：转义、换行、级别过滤、内存上限"""

    def setUp(self):
        super().setUp()
        self.panel = LogPanel()

    def tearDown(self):
        self.panel.deleteLater()
        super().tearDown()

    def test_html_is_escaped(self):
        self.panel.append_log("<b>粗体</b> & <script>", "INFO")
        text = self.panel.log_text.toPlainText()
        self.assertIn("<b>粗体</b> & <script>", text)

    def test_multiline_kept_separate(self):
        self.panel.append_log("第一行 D:/results/a.dat\n第二行 D:/results/b.dat", "INFO")
        text = self.panel.log_text.toPlainText()
        self.assertIn("第一行", text)
        self.assertIn("第二行", text)
        self.assertNotIn("第一行 D:/results/a.dat第二行", text)

    def test_format_log_html_escapes_and_breaks(self):
        html = format_log_html("2026-11-13 10:00:00", "ERROR", "a<b>\nC:\\x")
        self.assertIn("&lt;b&gt;", html)
        self.assertIn("<br/>", html)
        self.assertIn("white-space: pre-wrap", html)
        self.assertIn("ERROR", html)

    def test_level_filter(self):
        self.panel.append_log("信息内容", "INFO")
        self.panel.append_log("错误内容", "ERROR")
        self.panel.filter_logs("错误")
        text = self.panel.log_text.toPlainText()
        self.assertIn("错误内容", text)
        self.assertNotIn("信息内容", text)

        # 过滤生效时新增的非匹配日志不显示
        self.panel.append_log("新信息", "INFO")
        self.assertNotIn("新信息", self.panel.log_text.toPlainText())

    def test_level_normalized(self):
        self.panel.append_log("小写级别", "error")
        self.assertEqual(self.panel.logs[-1]["level"], "ERROR")

    def test_memory_limit(self):
        original = log_panel_module.MAX_LOG_ENTRIES
        log_panel_module.MAX_LOG_ENTRIES = 5
        try:
            for i in range(8):
                self.panel.append_log(f"m{i}", "INFO")
        finally:
            log_panel_module.MAX_LOG_ENTRIES = original

        self.assertEqual(len(self.panel.logs), 5)
        messages = [entry["message"] for entry in self.panel.logs]
        self.assertEqual(messages, ["m3", "m4", "m5", "m6", "m7"])
        self.assertNotIn("m0", self.panel.log_text.toPlainText())


class ConfigAvailabilityTest(TempTestCase):
    """未加载配置时禁用入口并给出 tooltip 原因"""

    def test_execute_start_disabled_without_config(self):
        panel = ExecutePanel()
        panel.set_config_available(False, "尚未加载配置：请先选择目录")
        self.assertFalse(panel.start_btn.isEnabled())
        self.assertIn("尚未加载配置", panel.start_btn.toolTip())

    def test_execute_start_enabled_after_config(self):
        panel = ExecutePanel()
        panel.set_config_available(False, "尚未加载配置")
        panel.set_config(make_config(self.tmp))
        self.assertTrue(panel.start_btn.isEnabled())
        self.assertEqual(panel.start_btn.toolTip(), "")

    def test_hardware_check_disabled_without_config(self):
        panel = HardwarePanel()
        panel.set_config_available(False, "尚未加载配置：请先选择目录")
        self.assertFalse(panel.check_btn.isEnabled())
        self.assertIn("尚未加载配置", panel.check_btn.toolTip())

        panel.set_config(make_config(self.tmp))
        self.assertTrue(panel.check_btn.isEnabled())

    def test_config_panel_empty_guide(self):
        panel = ConfigPanel()
        panel.set_config_loaded(False)
        self.assertFalse(panel.empty_guide.isHidden())
        panel.set_config_loaded(True)
        self.assertTrue(panel.empty_guide.isHidden())


class ErrorBarTest(TempTestCase):
    """执行失败：顶部错误条（原因/路径/建议）+ 结果目录提示"""

    def _panel(self):
        panel = ExecutePanel()
        panel.set_config(make_config(self.tmp))
        panel.run_timestamp = "2026-11-13-10-00"
        panel.worker = FakeWorker(
            running=False, stop_requested=False,
            summary="测试完成: 0/2 成功 | 失败: 2 | 跳过: 0")
        return panel

    def test_failure_shows_error_bar_and_result_hint(self):
        panel = self._panel()
        panel.on_execution_finished(False)
        self.assertFalse(panel.error_bar.isHidden())
        text = panel.error_label.text()
        self.assertIn("原因：", text)
        self.assertIn("建议：", text)
        self.assertIn("查看日志", panel.error_log_btn.text())
        self.assertFalse(panel.result_hint.isHidden())
        self.assertIn("打开结果目录", panel.open_results_btn.text())

    def test_error_bar_closable(self):
        panel = self._panel()
        panel.on_execution_finished(False)
        panel.hide_error_bar()
        self.assertTrue(panel.error_bar.isHidden())

    def test_success_hides_error_bar(self):
        panel = self._panel()
        panel.worker.final_summary = ""
        panel.on_execution_finished(True)
        self.assertTrue(panel.error_bar.isHidden())
        self.assertFalse(panel.result_hint.isHidden())

    def test_stopped_is_not_an_error(self):
        panel = self._panel()
        panel.worker.stop_requested = True
        panel.worker.final_summary = "已停止（完成 0/2） | 成功: 0 | 失败: 0 | 跳过: 2"
        panel.on_execution_finished(False)
        self.assertTrue(panel.error_bar.isHidden())
        self.assertIn("已停止", panel.stats_label.text())


class CaseTablePathTest(TempTestCase):
    """用例表右键：dat 目录解析与复制路径"""

    def test_provider_and_copy_path(self):
        table = CaseTable()
        table.set_dat_dir_provider(lambda name: self.tmp / "results" / name)
        expected = self.tmp / "results" / "case1"
        self.assertEqual(table._case_dat_dir("case1"), expected)

        table.copy_case_path("case1")
        self.assertEqual(QApplication.clipboard().text(), str(expected))

    def test_no_provider_returns_none(self):
        table = CaseTable()
        self.assertIsNone(table._case_dat_dir("case1"))


class WorkerLogLevelTest(TempTestCase):
    """worker 日志按真实级别上报"""

    def test_gui_handler_forwards_level(self):
        events = []

        class Collector:
            def emit(self, message, level):
                events.append((message, level))

        handler = GUILogHandler(Collector())
        record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "boom", None, None)
        handler.emit(record)
        self.assertEqual(events, [("boom", "ERROR")])

    def test_failed_case_is_error_and_success_is_info(self):
        worker = PipelineWorker(make_config(self.tmp), "test")
        events = []

        def collect(message, level):
            events.append((level, message))

        def collect_info(message):
            events.append(("INFO", message))

        worker.log_entry.connect(collect)
        worker.log_message.connect(collect_info)

        worker._handle_case_finished("case1", "success", 1.0)
        worker._handle_case_finished("case2", "failed", 1.0)
        worker._handle_case_finished("case3", "skipped", 0.0)

        self.assertEqual(events[-3][0], "INFO")
        self.assertEqual(events[-2][0], "ERROR")
        self.assertIn("用例失败", events[-2][1])
        self.assertEqual(events[-1][0], "WARNING")


if __name__ == "__main__":
    unittest.main()
