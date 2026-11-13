# -*- coding: utf-8 -*-
"""
执行页用例预扫描测试

覆盖：工作区扫描结果（就绪/缺 .out/忽略无关目录）与面板填充/统计文案。
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from gui.widgets.execute_panel import ExecutePanel  # noqa: E402
from gui.workers.case_scanner import scan_cases  # noqa: E402


class ScanCasesTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _make_case(self, name, project=False, out=False):
        case = self.root / name
        case.mkdir()
        if project:
            (case / ".project").write_text("<project/>", encoding="utf-8")
        if out:
            (case / "Debug").mkdir()
            (case / "Debug" / f"{name}.out").write_text("", encoding="utf-8")
        return case

    def test_ready_and_missing_out(self):
        self._make_case("case_ready", project=True, out=True)
        self._make_case("case_missing", project=True)
        (self.root / "empty_dir").mkdir()
        (self.root / "note.txt").write_text("x", encoding="utf-8")

        rows = scan_cases(self.root)

        self.assertEqual([(n, s) for n, s, _ in rows],
                         [("case_missing", "missing_out"), ("case_ready", "ready")])
        self.assertIn("需先构建", rows[0][2])

    def test_missing_directory_returns_empty(self):
        self.assertEqual(scan_cases(self.root / "not_exist"), [])


class ScanPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = ExecutePanel()
        self.addCleanup(self.panel.deleteLater)

    def test_on_scan_finished_fills_table_and_summary(self):
        self.panel.on_scan_finished([
            ("case_a", "ready", "已找到 .out"),
            ("case_b", "missing_out", "缺少 .out，需先构建"),
        ])

        self.assertEqual(self.panel.case_table.get_all_cases(), ["case_a", "case_b"])
        self.assertEqual(self.panel.case_table.get_case_status("case_a"), "ready")
        self.assertEqual(self.panel.case_table.get_case_status("case_b"), "missing_out")
        self.assertIn("就绪 1", self.panel.stats_label.text())
        self.assertIn("缺 .out 1", self.panel.stats_label.text())

    def test_scan_result_does_not_override_running_pipeline(self):
        class RunningWorker:
            def isRunning(self):
                return True

        self.panel.worker = RunningWorker()
        self.panel.case_table.add_case("running_case")

        self.panel.on_scan_finished([("case_a", "ready", "")])

        self.assertEqual(self.panel.case_table.get_all_cases(), ["running_case"])


if __name__ == "__main__":
    unittest.main()
