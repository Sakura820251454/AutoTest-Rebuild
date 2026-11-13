# -*- coding: utf-8 -*-
"""
执行页三步进度回归测试（Qt offscreen，不启动硬件/流水线）

覆盖：加权总进度计算、起始阶段决定参与阶段、步骤条状态、总进度只增不减、
测试阶段“第 x/N 批 + 当前用例 + 已用时间”明细。
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from gui.widgets.execute_panel import (  # noqa: E402
    ExecutePanel, compute_weighted_progress, stages_from, STAGE_WEIGHTS)


class WeightedProgressTest(unittest.TestCase):
    """加权进度：阶段内部 0→100，总进度按参与阶段归一化"""

    def test_start_from_stage_decides_stages(self):
        self.assertEqual(stages_from("generate"), ["generate", "build", "test"])
        self.assertEqual(stages_from("build"), ["build", "test"])
        self.assertEqual(stages_from("test"), ["test"])

    def test_zero_when_nothing_done(self):
        self.assertEqual(compute_weighted_progress(
            {"generate": 0, "build": 0, "test": 0}, stages_from("generate")), 0)

    def test_generate_done_is_weight_share(self):
        self.assertEqual(compute_weighted_progress(
            {"generate": 100, "build": 0, "test": 0}, stages_from("generate")),
            STAGE_WEIGHTS["generate"])

    def test_full_run_reaches_100_only_at_end(self):
        self.assertEqual(compute_weighted_progress(
            {"generate": 100, "build": 100, "test": 100}, stages_from("generate")), 100)
        self.assertLess(compute_weighted_progress(
            {"generate": 100, "build": 100, "test": 50}, stages_from("generate")), 100)

    def test_test_only_normalises_to_100(self):
        self.assertEqual(compute_weighted_progress(
            {"generate": 0, "build": 0, "test": 50}, stages_from("test")), 50)
        self.assertEqual(compute_weighted_progress(
            {"generate": 0, "build": 0, "test": 100}, stages_from("test")), 100)

    def test_build_start_ignores_generate(self):
        self.assertEqual(compute_weighted_progress(
            {"generate": 0, "build": 100, "test": 0}, stages_from("build")),
            int(round(STAGE_WEIGHTS["build"] / (STAGE_WEIGHTS["build"] + STAGE_WEIGHTS["test"]) * 100)))


class ExecutePanelProgressTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = ExecutePanel()
        self.addCleanup(self.panel.deleteLater)

    def test_step_bar_marks_unused_stage_as_skipped(self):
        self.panel._reset_progress("build")

        self.assertEqual(self.panel.step_labels["generate"].property("stepState"), "skipped")
        self.assertEqual(self.panel.step_labels["build"].property("stepState"), "pending")
        self.assertIn("—", self.panel.step_labels["generate"].text())

    def test_stage_progress_updates_step_state(self):
        self.panel._reset_progress("generate")
        self.panel.on_stage_progress("build", 40, "构建进度: 2/5 (40%)")

        self.assertEqual(self.panel.step_labels["build"].property("stepState"), "running")
        self.assertIn("构建进度", self.panel.stats_label.text())
        self.assertGreater(self.panel.progress_bar.value(), 0)

    def test_total_progress_never_goes_back(self):
        self.panel._reset_progress("generate")
        self.panel.on_stage_progress("generate", 100, "生成工程完成")
        after_generate = self.panel.progress_bar.value()

        # 构建/测试阶段都从 0 开始上报，总进度不应回退
        self.panel.on_stage_progress("build", 0, "正在构建...")
        self.panel.on_stage_progress("build", 50, "构建进度: 1/2 (50%)")
        mid = self.panel.progress_bar.value()
        self.panel.on_stage_progress("build", 10, "重试后进度回落")
        self.assertGreaterEqual(self.panel.progress_bar.value(), mid)
        self.assertGreaterEqual(mid, after_generate)

    def test_stop_marks_running_stage_stopped_without_rollback(self):
        class FakeWorker:
            stop_requested = True
            final_summary = "已停止（完成 1/4）"

            def isRunning(self):
                return False

        self.panel.worker = FakeWorker()
        self.panel._reset_progress("generate")
        self.panel.on_stage_progress("test", 25, "测试进度: 1/4 (25%)")
        before = self.panel.progress_bar.value()

        self.panel.on_execution_finished(False)

        self.assertEqual(self.panel.progress_bar.value(), before)
        self.assertEqual(self.panel.step_labels["test"].property("stepState"), "stopped")

    def test_test_detail_shows_batch_case_and_elapsed(self):
        self.panel._reset_progress("test")
        self.panel.on_test_batch_started(2, 5)
        self.panel.on_case_started("case_alpha")

        text = self.panel.test_detail_label.text()
        self.assertIn("第 2/5 批", text)
        self.assertIn("当前用例: case_alpha", text)
        self.assertIn("已用", text)
        self.assertTrue(self.panel.test_detail_label.isVisible() or text)


class StartStageComboTest(unittest.TestCase):
    """起始阶段下拉：替代重复的“完整执行/从生成开始”两个选项"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = ExecutePanel()
        self.addCleanup(self.panel.deleteLater)

    def test_three_options_and_default_generate(self):
        combo = self.panel.start_stage_combo
        self.assertEqual(combo.count(), 3)
        self.assertEqual([combo.itemData(i) for i in range(3)],
                         ["generate", "build", "test"])
        self.assertEqual(self.panel._get_selected_stage(), "generate")

    def test_detected_build_stage_selects_build_and_disables_test(self):
        self.panel.set_current_stage("build", "已构建")

        self.assertEqual(self.panel._get_selected_stage(), "build")
        index = self.panel.start_stage_combo.findData("test")
        self.assertFalse(self.panel.start_stage_combo.model().item(index).isEnabled())

    def test_detected_test_stage_allows_all(self):
        self.panel.set_current_stage("test", "已测试")

        self.assertEqual(self.panel._get_selected_stage(), "test")
        for stage in ("generate", "build", "test"):
            index = self.panel.start_stage_combo.findData(stage)
            self.assertTrue(self.panel.start_stage_combo.model().item(index).isEnabled())

    def test_resume_checkbox_switches_to_test(self):
        self.panel.on_resume_checkbox_changed(Qt.Checked)

        self.assertEqual(self.panel._get_selected_stage(), "test")


if __name__ == "__main__":
    unittest.main()
