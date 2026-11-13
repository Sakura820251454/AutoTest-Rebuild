# -*- coding: utf-8 -*-
"""
配置字段完整性守卫（GUI Config -> _config_to_dict -> 临时 JSON -> Config.load）

背景：`gui/workers/pipeline_worker.py::_config_to_dict()` 先后漏过
`encrypt_flash_dat`、`flash_encrypt_verify`、`results_dir`，导致临时配置静默回退默认值、
输出落到错误目录。这里不逐字段补用例，而是建立一类通用守卫：

1. 以 dataclass 字段为唯一真源，断言临时配置覆盖所有字段名（含允许的刻意缺省名单）；
2. 给每个字段塞非默认哨兵值，走完整往返后逐字段比对值与类型；
3. 单独锁定 results_dir 自定义绝对路径的往返行为。

_blocker 说明：`_config_to_dict()` 只读取 `self.config` 与 `self.run_timestamp`，
不依赖 Qt 事件循环，因此可以直接用 PipelineWorker 实例调用，无需 QApplication；
若将来该方法引入其它实例状态，测试会以 AttributeError 明确报错，而不是静默通过。
"""

import dataclasses
import unittest
from pathlib import Path

from tests.helpers import TempTestCase
from src.config import (
    BuildConfig,
    Config,
    ExportPoint,
    MemorySegment,
    PathConfig,
    ResultCheck,
    TestCase,
    TestConfig,
)
from src.runtime_paths import to_posix
from gui.workers.pipeline_worker import PipelineWorker


TS = "2026-11-12-10-00"

# 刻意不写入临时配置的字段及其理由。
# 目前为空：所有 dataclass 字段都必须落盘，否则 Config.load() 会静默回退默认值。
# 若确需排除，格式为 (分组, 字段名): "理由"，并在下面用例中说明影响面。
DELIBERATE_OMISSIONS = {}


def _field_names(model):
    return [f.name for f in dataclasses.fields(model)]


def _rc_tuple(rc):
    return tuple(getattr(rc, name) for name in _field_names(ResultCheck))


def _seg_tuple(seg):
    return tuple(getattr(seg, name) for name in _field_names(MemorySegment))


def _export_tuple(point):
    return tuple(getattr(point, name) for name in _field_names(ExportPoint))


class _ConfigDictMixin:
    """构造哨兵配置并执行一次完整往返"""

    def sentinel_config(self):
        """所有字段都使用与默认值不同的绝对路径/标量，便于发现漏写与类型改写"""
        base = self.tmp / "sentinel"
        paths = {
            "template_dir": base / "tmpl",
            "source_dir": base / "src",
            "generate_dir": base / "ws",
            "result_dir": base / "result",
            "results_dir": base / "custom_results",
            "ccs_workspace": base / "ws_legacy",
        }
        data = {
            "paths": {k: str(v) for k, v in paths.items()},
            "tools": {
                "ccs_executable": str(base / "tools" / "ccs_sentinel.exe"),
                "ccs_dss": str(base / "tools" / "dss_sentinel.bat"),
                "ccxml": str(base / "tools" / "sentinel.ccxml"),
            },
            "build": {
                "build_config": "SentinelRelease",
                "build_timeout": 1234,
                "max_build_threads": 9,
                "do_generate": False,
                "do_build": False,
            },
            "test": {
                "test_timeout": 54321,
                "test_batch_size": 7,
                "result_addr": "0x1111",
                "success_val": "0xAAAA",
                "error_val": "0xBBBB",
                "device": "SENTINEL_DEV",
                "cpu": "SENTINEL_CPU",
                "do_test": False,
                "auto_resume": False,
                "max_retries": 1,
                "retry_delay": 2,
                "encrypt_flash_dat": True,
                "flash_encrypt_verify": True,
                "copy_project": False,
                "result_check": {
                    "method": "memory",
                    "success_label": "OK_S",
                    "fail_label": "NG_S",
                    "check_addr": "0x2000",
                    "check_width": 16,
                    "success_val": "0x1234",
                    "fail_val": "0x5678",
                    "expression": "SENTINEL_EXPR",
                    "expected_val": "42",
                },
            },
            "generation": {"generation_mode": "manual"},
            "log": {"log_retention_days": 7},
            "memory_segments": {
                "segments": [
                    {"name": "S0", "addr": "0x1000", "len": "0x100", "width": 15, "page": 1},
                    {"name": "S1", "addr": "0x2000", "len": "0x200", "width": 31, "page": 0},
                ],
                "export_points": [
                    {"when": "before_run", "enabled": False, "subdir": "pre_s"},
                    {"when": "after_run", "enabled": True, "subdir": "post_s"},
                ],
            },
            "cases": [{
                "name": "sentinel_case",
                "out": str(base / "ws" / "sentinel_case" / "Debug" / "sentinel_case.out"),
                "dat_dir": to_posix(base / "case_dat_sentinel"),
                "is_flash": True,
                "segments": [
                    {"name": "CS0", "addr": "0x3000", "len": "0x80", "width": 15, "page": 0},
                ],
                "export_points": [
                    {"when": "after_run", "enabled": False, "subdir": "case_sub"},
                ],
                "result_check": {
                    "method": "expression",
                    "success_label": "CASE_OK",
                    "fail_label": "CASE_NG",
                    "check_addr": "0x3000",
                    "check_width": 32,
                    "success_val": "0xCAFE",
                    "fail_val": "0xDEAD",
                    "expression": "case_expr",
                    "expected_val": "7",
                },
            }],
        }
        path = self.write_json("source/config.json", data)
        return Config.load(path)

    def config_dict(self, cfg):
        return PipelineWorker(cfg, "test", run_timestamp=TS)._config_to_dict()

    def roundtrip(self, cfg):
        """Config -> _config_to_dict -> 临时 JSON -> Config.load"""
        produced = self.config_dict(cfg)
        json_path = self.write_json("run/config.json", produced)
        return produced, Config.load(json_path), json_path

    def assert_field(self, label, expected, actual):
        self.assertEqual(actual, expected, label)
        if isinstance(expected, Path):
            self.assertIsInstance(actual, Path, label)
        else:
            self.assertIs(type(actual), type(expected),
                          "%s 类型被改写: %r -> %r" % (label, type(expected), type(actual)))


class FieldCompletenessTest(_ConfigDictMixin, TempTestCase):
    """字段名完整性：dataclass 是唯一真源"""

    FIELD_GROUPS = [
        ("paths", PathConfig, lambda d: set(d["paths"]) | set(d["tools"]),
         "PathConfig 中 ccs_executable/ccs_dss/ccxml 写入 tools 分组"),
        ("build", BuildConfig, lambda d: set(d["build"]), ""),
        ("test", TestConfig, lambda d: set(d["test"]),
         "result_check 子结构单独断言"),
        ("test.result_check", ResultCheck,
         lambda d: set(d["test"]["result_check"]), ""),
        ("memory_segments.segments", MemorySegment,
         lambda d: set(d["memory_segments"]["segments"][0]), ""),
        ("memory_segments.export_points", ExportPoint,
         lambda d: set(d["memory_segments"]["export_points"][0]), ""),
        ("cases", TestCase, lambda d: set(d["cases"][0]), ""),
    ]

    def test_every_dataclass_field_is_written(self):
        produced = self.config_dict(self.sentinel_config())
        missing = []
        for label, model, keys_of, _note in self.FIELD_GROUPS:
            keys = keys_of(produced)
            for name in _field_names(model):
                if (label, name) in DELIBERATE_OMISSIONS:
                    continue
                if name not in keys:
                    missing.append("%s.%s" % (label, name))
        self.assertEqual(missing, [], "临时配置漏写字段: " + ", ".join(missing))

    def test_omission_list_is_documented(self):
        for key, reason in DELIBERATE_OMISSIONS.items():
            self.assertTrue(str(reason).strip(), "缺省名单 %r 必须写明理由" % (key,))

    def test_top_level_groups_are_stable(self):
        produced = self.config_dict(self.sentinel_config())
        self.assertEqual(set(produced), {
            "paths", "tools", "build", "generation", "test",
            "memory_segments", "cases", "log",
        })


class ValueRoundtripTest(_ConfigDictMixin, TempTestCase):
    """值级往返：哨兵值不能被默认值或类型转换悄悄替换"""

    def test_paths_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        for name in _field_names(PathConfig):
            self.assert_field("paths." + name,
                              getattr(original.paths, name),
                              getattr(loaded.paths, name))

    def test_build_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        for name in _field_names(BuildConfig):
            self.assert_field("build." + name,
                              getattr(original.build, name),
                              getattr(loaded.build, name))

    def test_test_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        for name in _field_names(TestConfig):
            self.assert_field("test." + name,
                              getattr(original.test, name),
                              getattr(loaded.test, name))

    def test_result_check_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        for name in _field_names(ResultCheck):
            self.assert_field("result_check." + name,
                              getattr(original.result_check, name),
                              getattr(loaded.result_check, name))

    def test_memory_segments_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        self.assertEqual([_seg_tuple(s) for s in loaded.memory_segments],
                         [_seg_tuple(s) for s in original.memory_segments])
        self.assertEqual([type(s.width) for s in loaded.memory_segments],
                         [type(s.width) for s in original.memory_segments])

    def test_export_points_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        self.assertEqual([_export_tuple(p) for p in loaded.export_points],
                         [_export_tuple(p) for p in original.export_points])

    def test_cases_values_roundtrip(self):
        original = self.sentinel_config()
        _, loaded, _ = self.roundtrip(original)
        self.assertEqual(len(loaded.cases), len(original.cases))

        case, expected = loaded.cases[0], original.cases[0]
        for name in _field_names(TestCase):
            if name in ("segments", "export_points", "result_check"):
                continue
            self.assert_field("cases[0]." + name,
                              getattr(expected, name), getattr(case, name))
        self.assertEqual([_seg_tuple(s) for s in case.segments],
                         [_seg_tuple(s) for s in expected.segments])
        self.assertEqual([_export_tuple(p) for p in case.export_points],
                         [_export_tuple(p) for p in expected.export_points])
        self.assertEqual(_rc_tuple(case.result_check), _rc_tuple(expected.result_check))

    def test_log_group_roundtrip(self):
        original = self.sentinel_config()
        produced, loaded, _ = self.roundtrip(original)
        self.assertEqual(produced["log"]["log_retention_days"], 7)
        self.assertEqual(loaded._raw["log"]["log_retention_days"], 7)

    def test_generation_mode_roundtrip(self):
        original = self.sentinel_config()
        produced, loaded, _ = self.roundtrip(original)
        self.assertEqual(produced["generation"]["generation_mode"], "manual")
        self.assertEqual(loaded._raw["generation"]["generation_mode"], "manual")


class ResultsDirRegressionTest(_ConfigDictMixin, TempTestCase):
    """本次缺陷专项：results_dir 自定义绝对路径必须原样存活"""

    def test_custom_absolute_results_dir_survives_roundtrip(self):
        custom = self.make_dir("custom_results_root").resolve()
        original = self.sentinel_config()
        original.paths.results_dir = custom

        produced, loaded, json_path = self.roundtrip(original)

        self.assertEqual(produced["paths"]["results_dir"], str(custom),
                         "临时配置未写入 results_dir")
        self.assertEqual(loaded.paths.results_dir, custom)
        self.assertTrue(loaded.paths.results_dir.is_absolute())
        default_fallback = (json_path.parent / ".." / "results").resolve()
        self.assertNotEqual(loaded.paths.results_dir, default_fallback,
                            "results_dir 回退成了临时目录的相对默认值")


if __name__ == "__main__":
    unittest.main()
