#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回归测试统一入口

@input tests/test_*.py
@output 每个用例 PASS/FAIL/ERROR/SKIP 行、总计与耗时；有失败时退出码为 1
@pos 日常改完代码后唯一需要执行的命令：python tests/run_checks.py

用法：
    python tests/run_checks.py                    # 跑全部
    python tests/run_checks.py tests.test_config_parse   # 只跑指定模块
"""

import argparse
import logging
import os
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# GUI 测试离屏运行，禁止弹窗阻塞；必须在导入 PyQt5 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _ReportingResult(unittest.TextTestResult):
    """逐用例打印 [PASS]/[FAIL]/[ERROR]/[SKIP] 及耗时"""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self._started_at = 0.0

    def startTest(self, test):
        self._started_at = time.perf_counter()
        super().startTest(test)

    def _report(self, status, test):
        elapsed = time.perf_counter() - self._started_at
        self.stream.writeln("[%-5s] %s  (%.2fs)" % (status, test.id(), elapsed))
        self.stream.flush()

    def addSuccess(self, test):
        super().addSuccess(test)
        self._report("PASS", test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._report("FAIL", test)

    def addError(self, test, err):
        super().addError(test, err)
        self._report("ERROR", test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._report("SKIP", test)


def _build_suite(loader, names):
    if names:
        return loader.loadTestsFromNames(names)
    return loader.discover(str(TESTS_DIR), pattern="test_*.py", top_level_dir=str(PROJECT_ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description="AutoTest 回归测试入口")
    parser.add_argument("names", nargs="*", help="可选的测试模块名，如 tests.test_config_parse")
    args = parser.parse_args(argv)

    # 测试会刻意触发 warning/error 分支，屏蔽日志避免淹没结果；断言失败仍由 unittest 打印堆栈
    logging.disable(logging.CRITICAL)

    loader = unittest.TestLoader()
    suite = _build_suite(loader, args.names)
    total_planned = suite.countTestCases()

    runner = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=0,
        resultclass=_ReportingResult,
    )

    started = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - started

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print("")
    print("=" * 64)
    print("总计: %d   通过: %d   失败: %d   错误: %d   跳过: %d"
          % (total, passed, failures, errors, skipped))
    if total_planned != total:
        print("警告: 计划用例数 %d 与实际执行 %d 不一致" % (total_planned, total))
    print("耗时: %.2f 秒" % elapsed)
    print("结果: %s" % ("PASS" if result.wasSuccessful() else "FAIL"))
    print("=" * 64)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
