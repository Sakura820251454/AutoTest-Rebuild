# -*- coding: utf-8 -*-
"""
流水线状态位回归测试（不连板）

覆盖：测试阶段“压根没跑起来”的三种情形必须让 finished 为 False：
  1. 工作区不存在
  2. 工作区没有 .out
  3. 结果目录被拒绝访问（Config.load 抛可读的 ConfigPathError，而不是原生 PermissionError）
"""

import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication          # noqa: E402

from tests.helpers import TempTestCase, make_config   # noqa: E402
from gui.workers import pipeline_worker as pipeline_module  # noqa: E402
from gui.workers.pipeline_worker import PipelineWorker      # noqa: E402


class PipelineStatusTest(TempTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.log_dir = self.make_dir("logs", "2026-01-01")
        patcher = mock.patch.object(pipeline_module, "setup_logger",
                                    side_effect=lambda: str(self.log_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run_worker(self, cfg):
        worker = PipelineWorker(cfg, "test")
        state = {"finished": None, "logs": [], "progress": []}
        def collect_entry(message, level):
            # 失败/异常走 log_entry（带真实级别），与 INFO 一起纳入日志断言
            state["logs"].append(message)

        worker.finished.connect(lambda ok: state.__setitem__("finished", bool(ok)))
        worker.log_message.connect(state["logs"].append)
        worker.log_entry.connect(collect_entry)
        worker.stage_progress.connect(
            lambda stage, p, m: state["progress"].append((stage, p, m)))
        worker.run()
        return state

    def test_missing_workspace_reports_failure(self):
        cfg = make_config(self.tmp)          # workspace 未创建
        state = self._run_worker(cfg)

        self.assertIs(state["finished"], False)
        self.assertTrue(any("工作区目录不存在" in m for m in state["logs"]))
        self.assertTrue(any(stage == "test" and p == 0 for stage, p, _ in state["progress"]))
        self.assertFalse(any(p >= 100 for _, p, _ in state["progress"]))

    def test_workspace_without_out_reports_failure(self):
        cfg = make_config(self.tmp)
        self.make_dir("workspace")
        state = self._run_worker(cfg)

        self.assertIs(state["finished"], False)
        self.assertTrue(any("没有找到任何 .out" in m for m in state["logs"]))
        self.assertTrue(any(stage == "test" and p == 0 for stage, p, _ in state["progress"]))
        self.assertFalse(any(p >= 100 for _, p, _ in state["progress"]))

    def test_all_steps_success_reports_pipeline_success(self):
        """三步都成功时，流水线必须整体返回成功（避免 final_finished 收到 None 误报失败）"""
        cfg = make_config(self.tmp)
        worker = PipelineWorker(cfg, "generate")
        with mock.patch.object(pipeline_module.Config, "load", return_value=cfg), \
                mock.patch.object(worker, "_execute_generate", return_value=True), \
                mock.patch.object(worker, "_execute_build", return_value=True), \
                mock.patch.object(worker, "_execute_test", return_value=(True, 1)):
            self.assertTrue(worker._execute_pipeline("ignored.json", worker._get_steps()))

    def test_unreadable_results_dir_reports_failure_with_readable_message(self):
        cfg = make_config(self.tmp)
        target = str(cfg.paths.results_dir)
        original_resolve = Path.resolve

        def fake_resolve(self, *args, **kwargs):
            if str(self) == target:
                raise PermissionError(13, "拒绝访问")
            return original_resolve(self, *args, **kwargs)

        with mock.patch.object(Path, "resolve", fake_resolve):
            state = self._run_worker(cfg)

        self.assertIs(state["finished"], False)
        self.assertTrue(any("路径配置错误" in m and "权限拒绝" in m for m in state["logs"]))
        self.assertFalse(any(p >= 100 for _, p, _ in state["progress"]))


if __name__ == "__main__":
    unittest.main()
