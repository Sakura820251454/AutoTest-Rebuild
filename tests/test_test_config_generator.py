# -*- coding: utf-8 -*-
"""
test_config_generator 回归测试

覆盖：从工作区扫描 .out 生成用例、无产物时的空结果、优先使用配置内用例、
dat_dir 为绝对正斜杠路径、is_flash / segments / result_check 的传递。
生成文件全部写入临时目录，不覆盖工程根目录的 full_regr.json。
"""

import json
import unittest
from pathlib import Path

from tests.helpers import TempTestCase, make_config
from src.runtime_paths import to_posix
from src.test_config_generator import generate_test_config


TS = "2026-11-12-10-00"


class GenerateFromWorkspaceTest(TempTestCase):
    """工作区扫描分支"""

    def _make_workspace(self, cfg, names):
        ws = cfg.paths.generate_dir
        for name in names:
            out = ws / name / "Debug" / f"{name}.out"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00")
        return ws

    def test_generates_case_per_out_file(self):
        cfg = make_config(self.tmp, generation_mode="manual")
        self._make_workspace(cfg, ["case_a", "case_b"])
        out_path = self.make_dir("out") / "full_regr.json"

        result = generate_test_config(cfg, TS, out_path)

        self.assertEqual(result, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        names = sorted(c["name"] for c in data["cases"])
        self.assertEqual(names, ["case_a", "case_b"])
        for case in data["cases"]:
            self.assertTrue(Path(case["dat_dir"]).is_absolute())
            self.assertNotIn("\\", case["dat_dir"])
            self.assertNotIn("\\", case["out"])
            expected_dir = to_posix(cfg.paths.results_dir / TS / case["name"])
            self.assertEqual(case["dat_dir"], expected_dir)
        self.assertEqual(data["ccxml"], to_posix(cfg.paths.ccxml))
        self.assertEqual(data["timeout"], cfg.test.test_timeout)
        self.assertEqual(data["result_addr"], cfg.test.result_addr)

    def test_returns_none_when_workspace_missing(self):
        cfg = make_config(self.tmp, generation_mode="manual")
        out_path = self.make_dir("out") / "full_regr.json"

        result = generate_test_config(cfg, TS, out_path)

        self.assertIsNone(result)
        self.assertFalse(out_path.exists())

    def test_returns_none_when_no_out_files(self):
        cfg = make_config(self.tmp, generation_mode="manual")
        self.make_dir("workspace", "empty_case", "Debug")
        out_path = self.make_dir("out") / "full_regr.json"

        result = generate_test_config(cfg, TS, out_path)

        self.assertIsNone(result)
        self.assertFalse(out_path.exists())


class GenerateFromCasesTest(TempTestCase):
    """配置内已有用例分支"""

    def test_uses_explicit_cases_and_dat_dir(self):
        custom_dat = to_posix(self.tmp / "custom_dat")
        cases = [{
            "name": "c1",
            "out": str(self.tmp / "workspace" / "c1" / "Debug" / "c1.out"),
            "dat_dir": custom_dat,
            "is_flash": True,
            "segments": [{"name": "FLASH", "addr": "0x80000", "len": "0x80000",
                          "width": 15, "page": 0}],
            "export_points": [{"when": "before_run", "enabled": True, "subdir": "pre"}],
            "result_check": {"method": "memory", "check_addr": "0x1000",
                             "success_val": "0x1", "fail_val": "0x0"},
        }]
        cfg = make_config(self.tmp, generation_mode="manual", raw_extra={"cases": cases})
        out_path = self.make_dir("out") / "full_regr.json"

        generate_test_config(cfg, TS, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        case = data["cases"][0]

        self.assertEqual(case["name"], "c1")
        self.assertEqual(case["dat_dir"], custom_dat)
        self.assertTrue(case["is_flash"])
        self.assertEqual([s["name"] for s in case["segments"]], ["FLASH"])
        self.assertEqual(case["export_points"][0]["subdir"], "pre")
        self.assertEqual(case["result_check"]["method"], "memory")
        self.assertEqual(case["result_check"]["check_addr"], "0x1000")

    def test_empty_dat_dir_falls_back_to_results_dir(self):
        cases = [{
            "name": "c2",
            "out": str(self.tmp / "workspace" / "c2" / "Debug" / "c2.out"),
            "dat_dir": "",
        }]
        cfg = make_config(self.tmp, raw_extra={"cases": cases})
        out_path = self.make_dir("out") / "full_regr.json"

        generate_test_config(cfg, TS, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(data["cases"][0]["dat_dir"],
                         to_posix(cfg.paths.results_dir / TS / "c2"))

    def test_is_flash_omitted_when_auto(self):
        cases = [{
            "name": "c3",
            "out": str(self.tmp / "workspace" / "c3" / "Debug" / "c3.out"),
            "dat_dir": str(self.tmp / "dat_c3"),
        }]
        cfg = make_config(self.tmp, raw_extra={"cases": cases})
        out_path = self.make_dir("out") / "full_regr.json"

        generate_test_config(cfg, TS, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertNotIn("is_flash", data["cases"][0])

    def test_case_without_segments_uses_global_segments(self):
        cases = [{
            "name": "c4",
            "out": str(self.tmp / "workspace" / "c4" / "Debug" / "c4.out"),
            "dat_dir": str(self.tmp / "dat_c4"),
        }]
        cfg = make_config(self.tmp, raw_extra={"cases": cases})
        out_path = self.make_dir("out") / "full_regr.json"

        generate_test_config(cfg, TS, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(len(data["cases"][0]["segments"]), len(cfg.memory_segments))
        self.assertEqual(data["cases"][0]["segments"][0]["name"], cfg.memory_segments[0].name)


if __name__ == "__main__":
    unittest.main()
