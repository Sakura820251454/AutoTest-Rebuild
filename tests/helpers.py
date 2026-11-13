# -*- coding: utf-8 -*-
"""
回归测试公共工具

@output TempTestCase、make_config_dict()、make_config()、write_flash_dat()
@pos tests 包内部的公共夹具，保证每个用例使用独立临时目录、互不污染

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TempTestCase(unittest.TestCase):
    """每个用例一个独立临时目录，tearDown 时递归删除"""

    def setUp(self):
        super().setUp()
        self._tmp = Path(tempfile.mkdtemp(prefix="autotest_regr_"))
        self.addCleanup(self._cleanup_tmp)

    def _cleanup_tmp(self):
        shutil.rmtree(str(self._tmp), ignore_errors=True)

    @property
    def tmp(self) -> Path:
        return self._tmp

    def make_dir(self, *parts) -> Path:
        path = self.tmp.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, rel, text, encoding="utf-8") -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(text)
        return path

    def write_json(self, rel, data) -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path


def make_config_dict(base, generation_mode="template", test=None, extra_paths=None):
    """
    构造一份新格式配置字典，所有路径默认落在 base 目录内（不触碰真实工程目录）

    Args:
        base: 临时根目录
        generation_mode: template / manual
        test: 覆盖 test 分组的字段
        extra_paths: 覆盖 paths 分组的字段
    """
    base = Path(base)
    test_group = {
        "test_timeout": 45000,
        "test_batch_size": 10,
        "result_addr": "0x7625",
        "success_val": "0xCCCC",
        "error_val": "0xEEEE",
        "device": "",
        "cpu": "",
        "do_test": True,
        "auto_resume": True,
        "max_retries": 5,
        "retry_delay": 10,
        "encrypt_flash_dat": False,
        "flash_encrypt_verify": False,
        "copy_project": True,
    }
    if test:
        test_group.update(test)

    paths = {
        "template_dir": "templates",
        "source_dir": "source",
        "generate_dir": "workspace",
        "result_dir": "result",
        "results_dir": "results",
        "ccs_workspace": "workspace",
    }
    if extra_paths:
        paths.update(extra_paths)

    return {
        "paths": {k: str(base / v) for k, v in paths.items()},
        "tools": {
            "ccs_executable": str(base / "tools" / "ccs.exe"),
            "ccs_dss": str(base / "tools" / "dss.bat"),
            "ccxml": str(base / "tools" / "target.ccxml"),
        },
        "build": {
            "build_config": "Debug",
            "build_timeout": 600,
            "max_build_threads": 4,
            "do_generate": True,
            "do_build": True,
        },
        "test": test_group,
        "generation": {"generation_mode": generation_mode},
    }


def make_config(base, generation_mode="template", test=None, extra_paths=None,
                config_path=None, raw_extra=None):
    """构造 Config 对象（config_path 只用于确定相对路径基准，不要求文件存在）"""
    from src.config import Config

    data = make_config_dict(base, generation_mode, test, extra_paths)
    if raw_extra:
        data.update(raw_extra)
    cfg_path = Path(config_path) if config_path else (Path(base) / "config" / "config.json")
    return Config(data, cfg_path)


def make_case(base, name="case1", dat_dir=None, segments=None, export_points=None,
              out=None, is_flash=None):
    """构造 executor / config 使用的用例字典"""
    base = Path(base)
    case = {
        "name": name,
        "out": str(out if out is not None else base / "workspace" / name / "Debug" / f"{name}.out"),
        "dat_dir": str(dat_dir if dat_dir is not None else base / "results" / name),
        "segments": segments if segments is not None else [],
        "export_points": export_points if export_points is not None else [
            {"when": "after_run", "enabled": True, "subdir": "memory"}
        ],
    }
    if is_flash is not None:
        case["is_flash"] = is_flash
    return case


def flash_words(count=65536):
    """生成确定性的 64-bit 词序列（覆盖 0、全 1、有符号边界附近的值）"""
    special = [0x0000000000000000, 0xFFFFFFFFFFFFFFFF, 0x5A5A5A5A5A5A5A5A,
               0xA5A5A5A5A5A5A5A5, 0x00000000FFFFFFFF, 0xFFFFFFFF00000000]
    return [special[i % len(special)] if i % 97 == 0 else
            ((i * 0x0101010101010101) & 0xFFFFFFFFFFFFFFFF) for i in range(count)]


def write_flash_dat(path, words=None):
    """按加密脚本要求的格式写 FLASH.dat：每行 16 个十六进制字符"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    words = flash_words() if words is None else words
    with open(path, "w", encoding="ascii", newline="") as f:
        for word in words:
            f.write("%016X\n" % word)
    return path
