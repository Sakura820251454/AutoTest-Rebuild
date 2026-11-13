# -*- coding: utf-8 -*-
"""
report_generator 回归测试

覆盖：未开加密时 CSV 两列、开启加密时三列、无 dat_dir 时回落到配置的导出根目录、
空结果不产生文件。
"""

import unittest

from tests.helpers import TempTestCase
from src.report_generator import TestResult, generate_summary_report


TS = "2026-11-12-10-00"


class SummaryReportTest(TempTestCase):

    def _run_dir(self):
        run_dir = self.make_dir("results", TS)
        return run_dir

    def test_two_columns_without_encryption(self):
        run_dir = self._run_dir()
        results = [
            TestResult("case_a", "Success", dat_dir=run_dir / "case_a"),
            TestResult("case_b", "Error", dat_dir=run_dir / "case_b"),
        ]

        generate_summary_report(TS, [], results, None)

        lines = (run_dir / "summary.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["case_a,Success", "case_b,Error"])

    def test_three_columns_with_encryption(self):
        run_dir = self._run_dir()
        results = [
            TestResult("case_a", "Success", dat_dir=run_dir / "case_a"),
            TestResult("case_b", "Success", dat_dir=run_dir / "case_b"),
        ]
        states = {
            "case_a": {"result": "success", "text": "成功（FLASH0~3.dat）"},
            "case_b": {"result": "skip", "text": "不适用（无 FLASH 段）"},
        }

        generate_summary_report(TS, [], results, states)

        lines = (run_dir / "summary.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, [
            "case_a,Success,成功（FLASH0~3.dat）",
            "case_b,Success,不适用（无 FLASH 段）",
        ])
        for line in lines:
            self.assertEqual(len(line.split(",")), 3)

    def test_missing_dat_dir_falls_back_to_results_root(self):
        root = self.make_dir("configured_results")
        results = [TestResult("case_a", "Success", dat_dir=None)]

        generate_summary_report(TS, [], results, None, results_root=root)

        summary = root / TS / "summary.csv"
        self.assertTrue(summary.exists())
        self.assertEqual(summary.read_text(encoding="utf-8").strip(), "case_a,Success")

    def test_empty_results_writes_nothing(self):
        root = self.make_dir("empty_results")
        generate_summary_report(TS, [], [], None, results_root=root)
        self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
