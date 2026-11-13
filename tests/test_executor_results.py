# -*- coding: utf-8 -*-
"""
executor 结果判读与断点续测回归测试

覆盖：_read_case_result 的状态/耗时解析、_collect_results 的 summary.csv 汇总、
_find_last_completed_batch 的批次完成判定。全部使用合成 summary.csv 与临时结果目录，
不启动 DSS、不依赖板卡。

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import TempTestCase, make_case, make_config
from src.executor import TestExecutor


TS = "2026-11-12-10-00"


class ExecutorResultsBase(TempTestCase):

    def _executor(self, batch_size=10):
        cfg = make_config(self.tmp, generation_mode="manual",
                          test={"test_batch_size": batch_size})
        return TestExecutor(cfg, run_timestamp=TS)

    def _case(self, name, dat_dir=None):
        return make_case(self.tmp, name=name,
                         dat_dir=dat_dir if dat_dir is not None else self.tmp / "results" / name)

    def _time_case(self, name):
        """用例目录统一放在 <tmp>/results/<TS>/<name>，保证时间戳目录一致"""
        return self._case(name, dat_dir=self.tmp / "results" / TS / name)

    def _write_summary(self, dat_dir, text):
        path = Path(dat_dir) / "summary.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class ReadCaseResultTest(ExecutorResultsBase):
    """_read_case_result：单用例结果文件解析"""

    def test_success_with_duration(self):
        executor = self._executor()
        case = self._case("case1")
        self._write_summary(case["dat_dir"], "case1,Success,1234\n")

        result = executor._read_case_result(case)

        self.assertIsNotNone(result)
        self.assertEqual(result.case_name, "case1")
        self.assertEqual(result.status, "Success")
        self.assertEqual(result.duration_ms, 1234)
        self.assertEqual(Path(result.dat_dir), Path(case["dat_dir"]))

    def test_two_column_old_format_has_no_duration(self):
        executor = self._executor()
        case = self._case("case1")
        self._write_summary(case["dat_dir"], "case1,Failed\n")

        result = executor._read_case_result(case)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "Failed")
        self.assertIsNone(result.duration_ms)

    def test_abnormal_status_is_reported_verbatim(self):
        executor = self._executor()
        case = self._case("case1")
        self._write_summary(case["dat_dir"], "case1,Error\n")

        result = executor._read_case_result(case)

        self.assertEqual(result.status, "Error")

    def test_missing_summary_returns_none(self):
        executor = self._executor()
        case = self._case("missing")

        self.assertIsNone(executor._read_case_result(case))

    def test_empty_summary_returns_none(self):
        executor = self._executor()
        case = self._case("empty")
        self._write_summary(case["dat_dir"], "   \n")

        self.assertIsNone(executor._read_case_result(case))

    def test_single_column_summary_returns_none(self):
        executor = self._executor()
        case = self._case("broken")
        self._write_summary(case["dat_dir"], "case1\n")

        self.assertIsNone(executor._read_case_result(case))

    def test_unparseable_duration_keeps_status(self):
        """耗时列不合法时只丢耗时字段，用例状态必须照常返回"""
        executor = self._executor()
        case = self._case("case1")
        self._write_summary(case["dat_dir"], "case1,Success,not-a-number\n")

        result = executor._read_case_result(case)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "Success")
        self.assertIsNone(result.duration_ms)

    def test_duration_with_unit_suffix_keeps_status(self):
        """耗时写成 1.2s / 12ms 时状态仍正确，耗时留空"""
        for raw in ["1.2s", "12ms", " 3.5 s "]:
            with self.subTest(duration=raw):
                executor = self._executor()
                case = self._case("case1")
                self._write_summary(case["dat_dir"], f"case1,Failed,{raw}\n")

                result = executor._read_case_result(case)

                self.assertIsNotNone(result)
                self.assertEqual(result.status, "Failed")
                self.assertIsNone(result.duration_ms)

    def test_empty_duration_keeps_status(self):
        """第三列为空串时状态仍正确，耗时留空"""
        executor = self._executor()
        case = self._case("case1")
        self._write_summary(case["dat_dir"], "case1,Success,\n")

        result = executor._read_case_result(case)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "Success")
        self.assertIsNone(result.duration_ms)

    def test_extreme_numeric_durations_do_not_affect_status(self):
        """负数/超大值仍按整数解析，不影响状态判定"""
        for raw, expected in [("-5", -5), ("999999999999", 999999999999)]:
            with self.subTest(duration=raw):
                executor = self._executor()
                case = self._case("case1")
                self._write_summary(case["dat_dir"], f"case1,Success,{raw}\n")

                result = executor._read_case_result(case)

                self.assertIsNotNone(result)
                self.assertEqual(result.status, "Success")
                self.assertEqual(result.duration_ms, expected)

    def test_relative_dat_dir_is_resolved_against_app_path(self):
        executor = self._executor()
        case = self._case("case_rel", dat_dir="results/case_rel")
        self._write_summary(self.tmp / "results" / "case_rel", "case_rel,Success\n")

        with mock.patch("src.executor.app_path",
                        side_effect=lambda rel="": self.tmp / rel):
            result = executor._read_case_result(case)

        self.assertIsNotNone(result)
        self.assertEqual(Path(result.dat_dir), self.tmp / "results" / "case_rel")


class CollectResultsTest(ExecutorResultsBase):
    """_collect_results：时间戳目录下 summary.csv 的汇总解析"""

    def test_empty_cases_returns_empty(self):
        self.assertEqual(self._executor()._collect_results([]), [])

    def test_missing_time_dir_marks_all_no_result(self):
        executor = self._executor()
        cases = [self._time_case("c1"), self._time_case("c2")]

        results = executor._collect_results(cases)

        self.assertEqual([r.status for r in results], ["NoResult", "NoResult"])
        for result in results:
            self.assertIn("时间戳目录不存在", result.error)

    def test_reads_rows_and_matches_each_case_dat_dir(self):
        executor = self._executor()
        cases = [self._time_case("c1"), self._time_case("c2")]
        self.make_dir("results", TS)
        self._write_summary(self.tmp / "results" / TS, "c1,Success\nc2,Failed\n")

        results = executor._collect_results(cases)

        by_name = {r.case_name: r for r in results}
        self.assertEqual(sorted(by_name), ["c1", "c2"])
        self.assertEqual(by_name["c1"].status, "Success")
        self.assertEqual(by_name["c2"].status, "Failed")
        self.assertEqual(Path(by_name["c1"].dat_dir), Path(cases[0]["dat_dir"]))
        self.assertEqual(Path(by_name["c2"].dat_dir), Path(cases[1]["dat_dir"]))

    def test_unknown_row_falls_back_to_first_dat_dir(self):
        """记录现状：summary 中出现未配置的用例名时，dat_dir 落到第一个用例"""
        executor = self._executor()
        cases = [self._time_case("c1")]
        self.make_dir("results", TS)
        self._write_summary(self.tmp / "results" / TS, "ghost,Success\n")

        results = executor._collect_results(cases)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].case_name, "ghost")
        self.assertEqual(Path(results[0].dat_dir), Path(cases[0]["dat_dir"]))

    def test_missing_summary_marks_all_no_result(self):
        executor = self._executor()
        cases = [self._time_case("c1"), self._time_case("c2")]
        self.make_dir("results", TS)

        results = executor._collect_results(cases)

        self.assertEqual([r.status for r in results], ["NoResult", "NoResult"])
        for result in results:
            self.assertEqual(result.error, "汇总文件不存在")

    def test_empty_summary_yields_no_results(self):
        """记录现状：summary 存在但为空时返回空列表，而不是逐用例 NoResult"""
        executor = self._executor()
        cases = [self._time_case("c1")]
        self.make_dir("results", TS)
        self._write_summary(self.tmp / "results" / TS, "")

        self.assertEqual(executor._collect_results(cases), [])

    def test_incomplete_summary_only_returns_listed_cases(self):
        executor = self._executor()
        cases = [self._time_case("c1"), self._time_case("c2")]
        self.make_dir("results", TS)
        self._write_summary(self.tmp / "results" / TS, "c1,Success\n")

        results = executor._collect_results(cases)

        self.assertEqual([r.case_name for r in results], ["c1"])

    def test_malformed_rows_are_skipped(self):
        executor = self._executor()
        cases = [self._time_case("c1"), self._time_case("c2")]
        self.make_dir("results", TS)
        self._write_summary(self.tmp / "results" / TS, "c1,Success\nbroken-line\nc2,Failed\n")

        results = executor._collect_results(cases)

        self.assertEqual([r.case_name for r in results], ["c1", "c2"])


class FindLastCompletedBatchTest(ExecutorResultsBase):
    """_find_last_completed_batch：断点续测起点判定"""

    def _cases(self, names):
        return [self._time_case(name) for name in names]

    def _mark_success(self, name):
        self._write_summary(self.tmp / "results" / TS / name, f"{name},Success\n")

    def test_all_batches_complete_returns_batch_count(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2", "c3", "c4"])
        for name in ["c1", "c2", "c3", "c4"]:
            self._mark_success(name)

        self.assertEqual(executor._find_last_completed_batch(cases), 2)

    def test_single_batch_all_complete(self):
        executor = self._executor(batch_size=10)
        cases = self._cases(["c1", "c2"])
        self._mark_success("c1")
        self._mark_success("c2")

        self.assertEqual(executor._find_last_completed_batch(cases), 1)

    def test_empty_cases_returns_zero(self):
        self.assertEqual(self._executor(batch_size=2)._find_last_completed_batch([]), 0)

    def test_first_batch_with_failed_case_returns_zero(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self._mark_success("c1")
        self._write_summary(self.tmp / "results" / TS / "c2", "c2,Failed\n")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_missing_summary_marks_batch_incomplete(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self._mark_success("c1")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_directory_without_summary_is_incomplete(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self.make_dir("results", TS, "c1")  # 目录在，但没有 summary.csv
        self._mark_success("c2")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_empty_summary_marks_batch_incomplete(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self._write_summary(self.tmp / "results" / TS / "c1", "")
        self._mark_success("c2")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_single_column_summary_marks_batch_incomplete(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self._write_summary(self.tmp / "results" / TS / "c1", "c1\n")
        self._mark_success("c2")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_non_success_status_marks_batch_incomplete(self):
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2"])
        self._write_summary(self.tmp / "results" / TS / "c1", "c1,Error\n")
        self._mark_success("c2")

        self.assertEqual(executor._find_last_completed_batch(cases), 0)

    def test_stops_at_first_incomplete_batch(self):
        """多批次：第一、二批完整，第三批缺结果 → 从第三批续测（索引 2）"""
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2", "c3", "c4", "c5", "c6"])
        for name in ["c1", "c2", "c3", "c4"]:
            self._mark_success(name)
        self._mark_success("c5")  # c6 没有结果

        self.assertEqual(executor._find_last_completed_batch(cases), 2)

    def test_later_complete_batches_do_not_override_earlier_incomplete(self):
        """中间的批次不完整、最后一批完整时，仍从中间批次续测"""
        executor = self._executor(batch_size=2)
        cases = self._cases(["c1", "c2", "c3", "c4", "c5", "c6"])
        for name in ["c1", "c2", "c5", "c6"]:
            self._mark_success(name)
        self.make_dir("results", TS, "c3")  # c3/c4 只有目录

        self.assertEqual(executor._find_last_completed_batch(cases), 1)


if __name__ == "__main__":
    unittest.main()
