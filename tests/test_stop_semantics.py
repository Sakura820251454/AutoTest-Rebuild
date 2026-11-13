# -*- coding: utf-8 -*-
"""
停止语义回归测试（不连板、不启动 DSS）

覆盖：停止后剩余用例标记为已跳过并通知 GUI、跳过用例不参与 FLASH 加密校验与失败统计、
结束摘要区分“已停止/测试完成”且成功/失败/跳过口径自洽、点击停止立即有反馈、
正常跑完的结束文案保持不变。
"""

import json
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from tests.helpers import TempTestCase, make_case, make_config  # noqa: E402
from src.executor import TestExecutor  # noqa: E402
from gui.widgets import execute_panel as execute_panel_module  # noqa: E402
from gui.widgets.execute_panel import ExecutePanel  # noqa: E402
from gui.workers.pipeline_worker import format_execution_summary  # noqa: E402


TS = "2026-11-13-10-00"
FLASH_SEGMENTS = [{"name": "FLASH", "addr": "0x80000", "len": "0x80000",
                   "width": 15, "page": 0}]


class FakeWorker:
    """只实现 ExecutePanel 用到的接口，避免真的启动线程"""

    def __init__(self, running=True, stop_requested=True, summary=""):
        self._running = running
        self.stop_requested = stop_requested
        self.final_summary = summary
        self.stop_called = 0

    def isRunning(self):
        return self._running

    def stop(self):
        self.stop_called += 1
        self._running = False


class ExecutorSkippedTest(TempTestCase):
    """executor：跳过标记与加密排除"""

    def _executor(self):
        cfg = make_config(self.tmp, generation_mode="manual",
                          test={"encrypt_flash_dat": True, "copy_project": False})
        return TestExecutor(cfg, run_timestamp=TS)

    def _case(self, name):
        return make_case(self.tmp, name=name,
                         dat_dir=self.tmp / "results" / TS / name,
                         segments=FLASH_SEGMENTS)

    def test_mark_remaining_writes_summary_and_notifies_once(self):
        executor = self._executor()
        events = []
        executor.on_case_finished = lambda n, s, d: events.append((n, s, d))
        c1, c2 = self._case("c1"), self._case("c2")

        executor._mark_remaining_batches_as_skipped([[c1, c2]])
        executor._mark_remaining_batches_as_skipped([[c1]])

        self.assertEqual(executor.skipped_case_names, {"c1", "c2"})
        self.assertEqual(events, [("c1", "Skipped", 0), ("c2", "Skipped", 0)])
        self.assertEqual((Path(c1["dat_dir"]) / "summary.csv").read_text(encoding="utf-8"),
                         "c1,Skipped\n")

    def test_skipped_case_is_not_encrypted_and_not_a_failure(self):
        executor = self._executor()
        case = self._case("c_skip")
        Path(case["dat_dir"]).mkdir(parents=True, exist_ok=True)
        executor.skipped_case_names.add("c_skip")

        executor._encrypt_flash_dats([case])

        self.assertEqual(executor.encrypt_failures, [])
        self.assertEqual(executor.encrypt_status["c_skip"]["result"], "skipped")
        self.assertIn("未执行", executor.encrypt_status["c_skip"]["text"])
        for i in range(4):
            self.assertFalse((Path(case["dat_dir"]) / "memory" / f"FLASH{i}.dat").exists())

    def test_stop_before_first_batch_skips_all_and_reports_no_encrypt_failure(self):
        cfg = make_config(self.tmp, generation_mode="manual",
                          test={"encrypt_flash_dat": True, "copy_project": False,
                                "test_batch_size": 2})
        self.make_dir("tools")
        (self.tmp / "tools" / "dss.bat").write_text("", encoding="utf-8")

        executor = TestExecutor(cfg, run_timestamp=TS)
        cases = []
        for name in ("c1", "c2", "c3", "c4", "c5"):
            case = make_case(self.tmp, name=name,
                             dat_dir=self.tmp / "results" / TS / name,
                             segments=FLASH_SEGMENTS)
            Path(case["dat_dir"]).mkdir(parents=True, exist_ok=True)
            cases.append(case)

        config_path = self.tmp / "full_regr.json"
        config_path.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")

        events = []
        executor.on_case_finished = lambda n, s, d: events.append((n, s))
        executor.should_stop = lambda: True

        with mock.patch("src.executor.app_path", side_effect=lambda rel="": self.tmp / rel):
            results = executor.run_all(test_config_path=config_path)

        self.assertTrue(executor.stopped)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r.status == "Skipped" for r in results))
        self.assertEqual(events, [(name, "Skipped") for name in ("c1", "c2", "c3", "c4", "c5")])
        self.assertEqual(executor.encrypt_failures, [])
        for case in cases:
            for i in range(4):
                self.assertFalse((Path(case["dat_dir"]) / "memory" / f"FLASH{i}.dat").exists())


class ExecutionSummaryTest(unittest.TestCase):
    """结束摘要文案：停止与正常完成分开，口径自洽"""

    def test_stopped_summary_has_success_failure_skipped(self):
        percent, text = format_execution_summary(True, 5, 0, 39, 44)

        self.assertEqual(percent, 11)
        self.assertEqual(text, "已停止（完成 5/44） | 成功: 5 | 失败: 0 | 跳过: 39")
        self.assertNotIn("测试完成", text)

    def test_normal_success_summary_unchanged(self):
        self.assertEqual(format_execution_summary(False, 44, 0, 0, 44),
                         (100, "测试完成: 44/44 成功"))

    def test_failure_reason_is_visible_without_logs(self):
        _, text = format_execution_summary(False, 43, 1, 0, 44,
                                           failure_reasons=["c1: 未生成结果文件"])

        self.assertIn("失败: 1", text)
        self.assertIn("失败原因: c1: 未生成结果文件", text)

    def test_encrypt_failure_count_is_appended(self):
        _, text = format_execution_summary(False, 44, 0, 0, 44, encrypt_failure_count=2)
        self.assertIn("FLASH 加密失败 2 处", text)

        _, stopped_text = format_execution_summary(True, 5, 0, 39, 44,
                                                   encrypt_failure_count=1)
        self.assertTrue(stopped_text.startswith("已停止"))


class ExecutePanelStopTest(TempTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ExecutePanel()
        self.addCleanup(self.panel.deleteLater)
        app_root = self.make_dir("app_root")
        patcher = mock.patch.object(execute_panel_module, "app_path",
                                    side_effect=lambda rel="": app_root / rel)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stop_click_shows_immediate_feedback(self):
        fake = FakeWorker(running=True)
        self.panel.worker = fake
        self.panel.stats_label.setText("执行中...")

        self.panel.stop_execution()

        self.assertEqual(self.panel.stats_label.text(), "正在停止…")
        self.assertEqual(fake.stop_called, 1)
        self.assertFalse(self.panel.stop_btn.isEnabled())
        self.assertTrue(self.panel.stopping)

    def test_finished_after_stop_shows_stopped_summary(self):
        self.panel.worker = FakeWorker(
            running=False, stop_requested=True,
            summary="已停止（完成 5/44） | 成功: 5 | 失败: 0 | 跳过: 39")
        self.panel.stopping = True

        self.panel.on_execution_finished(False)

        text = self.panel.stats_label.text()
        self.assertIn("已停止（完成 5/44）", text)
        self.assertNotIn("测试完成", text)
        self.assertTrue(self.panel.stopped)
        self.assertFalse(self.panel.stopping)

    def test_finished_normally_still_reports_completed(self):
        self.panel.worker = FakeWorker(running=False, stop_requested=False)

        self.panel.on_execution_finished(True)

        self.assertEqual(self.panel.stats_label.text(), "执行完成")
        self.assertEqual(self.panel.progress_bar.value(), 100)
        self.assertFalse(self.panel.stopped)

    def test_case_finished_during_stop_keeps_stopping_text(self):
        self.panel.case_table.add_case("c1", "running")
        self.panel.stopping = True
        self.panel.stats_label.setText("正在停止… 已跳过 0/1")

        self.panel.on_case_finished("c1", "skipped", 0.0)

        self.assertEqual(self.panel.stats_label.text(), "正在停止… 已跳过 0/1")
        self.assertEqual(self.panel.case_table.item(0, 1).text(), "已跳过")
        self.assertEqual(self.panel.case_table.item(0, 2).text(), "--")

    def test_case_finished_counts_skipped_separately(self):
        self.panel.case_table.add_case("c1", "success")
        self.panel.case_table.add_case("c2", "pending")

        self.panel.on_case_finished("c2", "skipped", 0.0)

        text = self.panel.stats_label.text()
        self.assertIn("成功: 1", text)
        self.assertIn("失败: 0", text)
        self.assertIn("跳过: 1", text)
        self.assertEqual(self.panel.case_table.get_skipped_count(), 1)


if __name__ == "__main__":
    unittest.main()
