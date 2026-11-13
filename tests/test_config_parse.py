# -*- coding: utf-8 -*-
"""
config 解析回归测试

覆盖：新/旧格式、字段默认值、相对路径基准、环境变量、工作区单一真源、
用例继承默认值、注释字段处理与 validate 校验分支。
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import TempTestCase
from src.config import Config, DEFAULT_MEMORY_SEGMENTS
from src.exceptions import (ConfigFileNotFoundError, ConfigPathError,
                            ConfigValidationError)


def _new_format(root: str = ""):
    """新格式配置骨架；路径均为相对配置文件目录的写法"""
    return {
        "paths": {
            "template_dir": "templates",
            "source_dir": "source",
            "generate_dir": "workspace",
            "result_dir": "result",
            "results_dir": "out_results",
            "ccs_workspace": "workspace",
        },
        "tools": {
            "ccs_executable": "tools/ccs.exe",
            "ccs_dss": "tools/dss.bat",
            "ccxml": "tools/target.ccxml",
        },
        "build": {
            "build_config": "Release",
            "build_timeout": 120,
            "max_build_threads": 8,
            "do_generate": False,
            "do_build": False,
        },
        "test": {
            "test_timeout": 1234,
            "test_batch_size": 3,
            "result_addr": "0x7625",
            "success_val": "0xCCCC",
            "error_val": "0xEEEE",
            "device": "F28379D",
            "cpu": "C28xx_CPU1",
            "do_test": False,
            "auto_resume": False,
            "max_retries": 2,
            "retry_delay": 7,
            "encrypt_flash_dat": True,
            "flash_encrypt_verify": True,
            "copy_project": False,
        },
        "generation": {"generation_mode": "template"},
    }


class NewFormatParseTest(TempTestCase):
    """新格式（分组）解析"""

    def test_parses_all_groups_with_paths_relative_to_config_dir(self):
        data = _new_format()
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        base = path.parent

        self.assertEqual(cfg.paths.template_dir, (base / "templates").resolve())
        self.assertEqual(cfg.paths.source_dir, (base / "source").resolve())
        self.assertEqual(cfg.paths.generate_dir, (base / "workspace").resolve())
        self.assertEqual(cfg.paths.results_dir, (base / "out_results").resolve())
        self.assertEqual(cfg.paths.ccs_dss, (base / "tools" / "dss.bat").resolve())
        self.assertEqual(cfg.build.build_config, "Release")
        self.assertEqual(cfg.build.build_timeout, 120)
        self.assertEqual(cfg.build.max_build_threads, 8)
        self.assertEqual(cfg.test.test_timeout, 1234)
        self.assertEqual(cfg.test.test_batch_size, 3)
        self.assertEqual(cfg.test.device, "F28379D")
        self.assertEqual(cfg.test.cpu, "C28xx_CPU1")
        self.assertTrue(cfg.test.encrypt_flash_dat)
        self.assertTrue(cfg.test.flash_encrypt_verify)
        self.assertFalse(cfg.test.copy_project)

    def test_absolute_path_is_preserved(self):
        target = self.make_dir("abs_workspace")
        data = {"paths": {"generate_dir": str(target)}}
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        self.assertEqual(cfg.paths.generate_dir, target.resolve())

    def test_env_vars_in_paths_are_expanded(self):
        ws = self.make_dir("env_workspace")
        ccxml = self.tmp / "env" / "target.ccxml"
        data = {
            "paths": {"generate_dir": "${AUTOTEST_WS}"},
            "tools": {"ccxml": "%AUTOTEST_CCXML%"},
            "generation": {"generation_mode": "manual"},
        }
        path = self.write_json("config/config.json", data)
        with mock.patch.dict(os.environ, {"AUTOTEST_WS": str(ws),
                                          "AUTOTEST_CCXML": str(ccxml)}):
            cfg = Config.load(path)
        self.assertEqual(cfg.paths.generate_dir, ws.resolve())
        self.assertEqual(cfg.paths.ccxml, ccxml.resolve())

    def test_generate_dir_wins_over_conflicting_ccs_workspace(self):
        data = {
            "paths": {"generate_dir": "ws_new", "ccs_workspace": "ws_old"},
        }
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        self.assertEqual(cfg.paths.generate_dir, (path.parent / "ws_new").resolve())
        self.assertEqual(cfg.paths.ccs_workspace, cfg.paths.generate_dir)

    def test_generate_dir_falls_back_to_ccs_workspace(self):
        data = {"paths": {"ccs_workspace": "ws_old"}}
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        self.assertEqual(cfg.paths.generate_dir, (path.parent / "ws_old").resolve())
        self.assertEqual(cfg.paths.ccs_workspace, cfg.paths.generate_dir)

    def test_missing_paths_default_results_dir_is_sibling_results(self):
        path = self.write_json("config/config.json", {"paths": {}})
        cfg = Config.load(path)
        self.assertEqual(cfg.paths.results_dir, (path.parent / ".." / "results").resolve())

    def test_missing_fields_fall_back_to_defaults(self):
        path = self.write_json("config/config.json", {"paths": {}})
        cfg = Config.load(path)

        self.assertEqual(cfg.build.build_config, "Debug")
        self.assertEqual(cfg.build.build_timeout, 600)
        self.assertEqual(cfg.build.max_build_threads, 4)
        self.assertEqual(cfg.test.test_timeout, 45000)
        self.assertEqual(cfg.test.test_batch_size, 10)
        self.assertEqual(cfg.test.result_addr, "0x7625")
        self.assertEqual(cfg.test.max_retries, 5)
        self.assertEqual(cfg.test.retry_delay, 10)
        self.assertFalse(cfg.test.encrypt_flash_dat)
        self.assertFalse(cfg.test.flash_encrypt_verify)
        self.assertTrue(cfg.test.copy_project)

        self.assertEqual([s.name for s in cfg.memory_segments],
                         [s["name"] for s in DEFAULT_MEMORY_SEGMENTS])
        self.assertEqual(len(cfg.export_points), 1)
        self.assertEqual(cfg.export_points[0].when, "after_run")
        self.assertTrue(cfg.export_points[0].enabled)
        self.assertEqual(cfg.result_check.method, "breakpoint")
        self.assertEqual(cfg.result_check.success_label, "Right")
        self.assertEqual(cfg.result_check.fail_label, "IDLE")

    def test_comment_keys_stripped_for_parse_but_kept_in_raw(self):
        data = {
            "_comment": "顶层注释",
            "paths": {"generate_dir": "ws", "_comment": "路径注释"},
            "test": {"_comment": "测试注释", "test_timeout": 9000},
            "generation": {"generation_mode": "manual"},
        }
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)

        self.assertEqual(cfg.test.test_timeout, 9000)
        self.assertIn("_comment", cfg._raw)
        self.assertIn("_comment", cfg._raw["paths"])
        self.assertNotIn("_comment", cfg.to_dict())


class CasesParseTest(TempTestCase):
    """用例解析与默认值继承"""

    def test_case_explicit_fields(self):
        data = _new_format()
        data["cases"] = [{
            "name": "case_a",
            "out": "workspace/case_a/Debug/case_a.out",
            "dat_dir": "results/case_a",
            "is_flash": True,
            "segments": [{"name": "FLASH", "addr": "0x80000", "len": "0x80000",
                          "width": 15, "page": 0}],
            "export_points": [{"when": "before_run", "enabled": False, "subdir": "pre"}],
            "result_check": {"method": "memory", "check_addr": "0x7625",
                             "check_width": 16, "success_val": "0xCCCC",
                             "fail_val": "0xEEEE"},
        }]
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)

        self.assertEqual(len(cfg.cases), 1)
        case = cfg.cases[0]
        self.assertEqual(case.name, "case_a")
        self.assertEqual(case.out, (path.parent / "workspace/case_a/Debug/case_a.out").resolve())
        self.assertEqual(case.dat_dir, "results/case_a")
        self.assertTrue(case.is_flash)
        self.assertEqual([s.name for s in case.segments], ["FLASH"])
        self.assertEqual(case.export_points[0].when, "before_run")
        self.assertFalse(case.export_points[0].enabled)
        self.assertEqual(case.export_points[0].subdir, "pre")
        self.assertEqual(case.result_check.method, "memory")
        self.assertEqual(case.result_check.check_addr, "0x7625")
        self.assertEqual(case.result_check.check_width, 16)

    def test_case_inherits_global_segments_and_result_check(self):
        data = _new_format()
        data["memory_segments"] = {
            "segments": [{"name": "M0", "addr": "0x0", "len": "0x10", "width": 15, "page": 0}],
            "export_points": [{"when": "after_run", "enabled": True, "subdir": "memory"}],
        }
        data["test"]["result_check"] = {"method": "expression",
                                        "expression": "result == 1",
                                        "expected_val": "1"}
        data["cases"] = [{"name": "c1", "out": "c1.out", "dat_dir": "d1"}]
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)

        case = cfg.cases[0]
        self.assertEqual([s.name for s in case.segments], ["M0"])
        self.assertEqual(case.result_check.method, "expression")
        self.assertEqual(case.result_check.expression, "result == 1")
        self.assertEqual(case.result_check.expected_val, "1")
        self.assertEqual(len(case.export_points), 1)
        self.assertEqual(case.export_points[0].when, "after_run")
        self.assertIsNone(case.is_flash)

    def test_is_flash_false_and_absent(self):
        data = _new_format()
        data["cases"] = [
            {"name": "ram", "out": "a.out", "dat_dir": "a", "is_flash": False},
            {"name": "auto", "out": "b.out", "dat_dir": "b"},
        ]
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        self.assertFalse(cfg.cases[0].is_flash)
        self.assertIsNone(cfg.cases[1].is_flash)


class LegacyFormatParseTest(TempTestCase):
    """旧格式（扁平）解析与兼容字段"""

    def test_legacy_flat_fields_and_aliases(self):
        data = {
            "template_dir": "templates",
            "source_dir": "source",
            "ccs_workspace": "ws",
            "ccs_executable": "tools/ccs.exe",
            "ccs_dss": "tools/dss.bat",
            "ccxml": "tools/t.ccxml",
            "build_config": "Debug",
            "timeout": 7777,
            "max_threads": 6,
            "encrypt_flash_dat": True,
            "copy_project": False,
        }
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)

        self.assertEqual(cfg.test.test_timeout, 7777)
        self.assertEqual(cfg.build.max_build_threads, 6)
        self.assertTrue(cfg.test.encrypt_flash_dat)
        self.assertFalse(cfg.test.copy_project)
        self.assertEqual(cfg.paths.generate_dir, (path.parent / "ws").resolve())

    def test_legacy_case_segments_become_global_segments(self):
        data = {
            "generate_dir": "ws",
            "cases": [{
                "name": "c1",
                "out": "c1.out",
                "dat_dir": "d1",
                "segments": [{"name": "X0", "addr": "0x1000", "len": "0x20", "width": 15}],
            }],
        }
        path = self.write_json("config/config.json", data)
        cfg = Config.load(path)
        self.assertEqual([s.name for s in cfg.memory_segments], ["X0"])
        self.assertEqual([s.name for s in cfg.cases[0].segments], ["X0"])


class LoadAndValidateTest(TempTestCase):
    """文件加载异常与 validate 分支"""

    def test_missing_config_file_raises(self):
        with self.assertRaises(ConfigFileNotFoundError):
            Config.load(self.tmp / "nope.json")

    def _manual_config_with_existing_paths(self):
        base = self.tmp / "cfg"
        (base / "workspace").mkdir(parents=True, exist_ok=True)
        (base / "tools").mkdir(parents=True, exist_ok=True)
        (base / "tools" / "ccs.exe").write_text("", encoding="utf-8")
        (base / "tools" / "dss.bat").write_text("", encoding="utf-8")
        data = _new_format()
        data["generation"] = {"generation_mode": "manual"}
        return data, self.write_json("cfg/config.json", data)

    def test_validate_passes_for_valid_manual_config(self):
        data, path = self._manual_config_with_existing_paths()
        cfg = Config.load(path)
        cfg.validate()  # 不抛异常即通过

    def test_validate_rejects_zero_build_timeout(self):
        data, path = self._manual_config_with_existing_paths()
        data["build"]["build_timeout"] = 0
        path = self.write_json("cfg/config.json", data)
        cfg = Config.load(path)
        with self.assertRaises(ConfigValidationError):
            cfg.validate()

    def test_validate_rejects_bad_hex_address(self):
        data, path = self._manual_config_with_existing_paths()
        data["test"]["result_addr"] = "0xZZZZ"
        path = self.write_json("cfg/config.json", data)
        cfg = Config.load(path)
        with self.assertRaises(ConfigValidationError):
            cfg.validate()

    def test_validate_rejects_missing_ccs_executable(self):
        data, path = self._manual_config_with_existing_paths()
        data["tools"]["ccs_executable"] = "tools/missing.exe"
        path = self.write_json("cfg/config.json", data)
        cfg = Config.load(path)
        with self.assertRaises(ConfigPathError):
            cfg.validate()


if __name__ == "__main__":
    unittest.main()
