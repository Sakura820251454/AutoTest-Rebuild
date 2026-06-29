"""
配置管理模块

@input os.environ, json (环境变量和JSON解析)
@output Config类, PathConfig类, BuildConfig类, TestConfig类, MemorySegment类, TestCase类
@pos 核心基础模块，配置加载/验证/保存，支持新旧格式兼容、环境变量、相对路径

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import os
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from .exceptions import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    ConfigPathError
)


DEFAULT_MEMORY_SEGMENTS = [
    {"name": "M0",  "addr": "0x0000", "len": "0x200",  "width": 15},
    {"name": "M1",  "addr": "0x0400", "len": "0x200",  "width": 15},
    {"name": "LS0", "addr": "0x8000", "len": "0x400",  "width": 15},
    {"name": "LS1", "addr": "0x8800", "len": "0x400",  "width": 15},
    {"name": "LS2", "addr": "0x9000", "len": "0x400",  "width": 15},
    {"name": "LS3", "addr": "0x9800", "len": "0x400",  "width": 15},
    {"name": "LS4", "addr": "0xa000", "len": "0x400",  "width": 15},
    {"name": "LS5", "addr": "0xa800", "len": "0x400",  "width": 15},
    {"name": "LS6", "addr": "0xb000", "len": "0x400",  "width": 15},
    {"name": "LS7", "addr": "0xb800", "len": "0x400",  "width": 15},
    {"name": "GS0", "addr": "0xc000", "len": "0x800",  "width": 15},
    {"name": "GS1", "addr": "0xd000", "len": "0x800",  "width": 15},
    {"name": "GS2", "addr": "0xe000", "len": "0x800",  "width": 15},
    {"name": "GS3", "addr": "0xf000", "len": "0x800",  "width": 15},
]

CONFIG_DEFAULTS = {
    "build_config": "Debug",
    "build_timeout": 600,
    "max_build_threads": 4,
    "test_timeout": 45000,
    "test_batch_size": 10,
    "result_addr": "0x7625",
    "success_val": "0xCCCC",
    "error_val": "0xEEEE",
    "log_retention_days": 30,
    "do_generate": True,
    "do_build": True,
    "do_test": True,
    "auto_resume": True,
    "max_retries": 5,
    "retry_delay": 10,
}


@dataclass
class PathConfig:
    """路径配置"""
    template_dir: Path
    source_dir: Path
    generate_dir: Path
    result_dir: Path
    ccs_workspace: Path
    ccs_executable: Path
    ccs_dss: Path
    ccxml: Path
    
    def validate(self, generation_mode: str = "template"):
        """验证路径配置
        
        Args:
            generation_mode: 生成模式，"template" 或 "manual"
                           template 模式需要 template_dir 和 source_dir
                           manual 模式只需要 generate_dir 中的工程
        """
        # 模板模式需要检查模板目录和源文件目录
        if generation_mode == "template":
            if not self.template_dir.exists():
                raise ConfigPathError("template_dir", str(self.template_dir), "模板工程目录不存在")
            if not self.source_dir.exists():
                raise ConfigPathError("source_dir", str(self.source_dir), "源文件目录不存在")
        
        # 手动模式需要检查生成目录
        if generation_mode == "manual":
            if not self.generate_dir.exists():
                raise ConfigPathError("generate_dir", str(self.generate_dir), "工程生成目录不存在")
        
        # 两种模式都需要检查工具路径
        if not self.ccs_executable.exists():
            raise ConfigPathError("ccs_executable", str(self.ccs_executable), "CCS 可执行文件不存在")
        if not self.ccs_dss.exists():
            raise ConfigPathError("ccs_dss", str(self.ccs_dss), "DSS 执行器不存在")


@dataclass
class BuildConfig:
    """构建配置"""
    build_config: str = "Debug"
    build_timeout: int = 600
    max_build_threads: int = 4
    do_generate: bool = True
    do_build: bool = True


@dataclass
class TestConfig:
    """测试配置"""
    test_timeout: int = 45000
    test_batch_size: int = 10
    result_addr: str = "0x7625"
    success_val: str = "0xCCCC"
    error_val: str = "0xEEEE"
    device: str = ""
    cpu: str = ""
    do_test: bool = True
    auto_resume: bool = True       # 断连后自动重连续测
    max_retries: int = 5           # 最大重试次数（0=不限制）
    retry_delay: int = 10          # 重试前等待秒数


@dataclass
class MemorySegment:
    """内存段配置"""
    name: str
    addr: str
    len: str
    width: int = 15


@dataclass
class ExportPoint:
    """内存导出时间点配置"""
    when: str  # after_load, before_run, after_run
    enabled: bool = True
    subdir: str = "Memory"  # 子目录名


# 默认导出时间点：仅在运行后导出
DEFAULT_EXPORT_POINTS = [
    ExportPoint(when="after_run", enabled=True, subdir="Memory")
]


@dataclass
class ResultCheck:
    """测试结果判断配置"""
    method: str = "breakpoint"  # 判断方式: breakpoint, memory, expression
    # breakpoint 方式参数
    success_label: str = "Right"  # 成功时停在的标签名
    fail_label: str = "IDLE"  # 失败时停在的标签名
    # memory 方式参数
    check_addr: str = ""  # 要检查的内存地址
    success_val: str = ""  # 成功时的值
    fail_val: str = ""  # 失败时的值
    # expression 方式参数
    expression: str = ""  # 要评估的表达式
    expected_val: str = ""  # 期望的值


# 默认结果判断配置（断点方式）
DEFAULT_RESULT_CHECK = ResultCheck(
    method="breakpoint",
    success_label="Right",
    fail_label="IDLE"
)


@dataclass
class TestCase:
    """测试用例配置"""
    name: str
    out: Path
    dat_dir: str
    segments: List[MemorySegment] = field(default_factory=list)
    export_points: List[ExportPoint] = field(default_factory=lambda: list(DEFAULT_EXPORT_POINTS))
    result_check: ResultCheck = field(default_factory=lambda: ResultCheck())


class Config:
    """
    配置管理类
    
    支持两种配置格式：
    1. 新格式（分组）：{ "paths": {...}, "tools": {...}, "build": {...}, "test": {...} }
    2. 旧格式（扁平）：{ "template_dir": "...", "source_dir": "...", ... }
    
    使用方法：
        config = Config.load("config.json")
        print(config.paths.template_dir)
        print(config.build.build_timeout)
    """
    
    def __init__(self, config_dict: Dict[str, Any], config_path: Path = None, raw_config_dict: Dict[str, Any] = None):
        self._raw = raw_config_dict if raw_config_dict is not None else config_dict
        self._config_path = config_path
        self._base_dir = config_path.parent if config_path else Path.cwd()
        
        self.paths: PathConfig = None
        self.build: BuildConfig = None
        self.test: TestConfig = None
        self.cases: List[TestCase] = []
        self.memory_segments: List[MemorySegment] = []
        self.export_points: List[ExportPoint] = list(DEFAULT_EXPORT_POINTS)
        self.result_check: ResultCheck = ResultCheck()

        self._parse(config_dict)
    
    @classmethod
    def load(cls, config_path: Union[str, Path]) -> "Config":
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径（支持 JSON 格式）
        
        Returns:
            Config 实例
        """
        config_path = Path(config_path).expanduser().resolve()
        
        if not config_path.exists():
            raise ConfigFileNotFoundError(str(config_path))
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        
        # 保留原始配置（包含注释）用于后续保存
        raw_config_dict = config_dict
        
        # 移除注释用于解析
        config_dict = cls._remove_comments(config_dict)
        
        return cls(config_dict, config_path, raw_config_dict)
    
    @staticmethod
    def _remove_comments(d: Dict) -> Dict:
        """移除配置中的注释字段（以 _ 开头的键）"""
        if isinstance(d, dict):
            result = {}
            for k, v in d.items():
                if not k.startswith("_"):
                    result[k] = Config._remove_comments(v)
            return result
        elif isinstance(d, list):
            return [Config._remove_comments(item) for item in d]
        else:
            return d
    
    def _parse(self, config_dict: Dict[str, Any] = None):
        """解析配置"""
        raw = config_dict if config_dict is not None else self._raw

        is_new_format = "paths" in raw or "tools" in raw or "build" in raw or "test" in raw or "memory_segments" in raw

        if is_new_format:
            self.paths = self._parse_paths_new(raw)
            self.build = self._parse_build_config_new(raw)
            self.test = self._parse_test_config_new(raw)
            self.memory_segments = self._parse_memory_segments_new(raw)
            self.export_points = self._parse_export_points_new(raw)
            self.result_check = self._parse_result_check_new(raw)
        else:
            self.paths = self._parse_paths_legacy(raw)
            self.build = self._parse_build_config_legacy(raw)
            self.test = self._parse_test_config_legacy(raw)
            self.memory_segments = self._parse_memory_segments_legacy(raw)
            self.export_points = self._parse_export_points_legacy(raw)
            self.result_check = self._parse_result_check_legacy(raw)

        self.cases = self._parse_cases(raw)
    
    def _resolve_path(self, path_str: str) -> Path:
        """
        解析路径，支持：
        1. 绝对路径
        2. 相对路径（相对于配置文件所在目录）
        3. 环境变量（${VAR} 或 %VAR%）
        """
        if not path_str:
            return Path("")
        
        env_var_pattern = r'\$\{([^}]+)\}|%([^%]+)%'
        
        def replace_env(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))
        
        resolved = re.sub(env_var_pattern, replace_env, path_str)
        
        path = Path(resolved)
        if path.is_absolute():
            return path.resolve()
        else:
            return (self._base_dir / path).resolve()
    
    def _parse_paths_new(self, raw: Dict) -> PathConfig:
        """解析新格式路径配置"""
        paths = raw.get("paths", {})
        tools = raw.get("tools", {})
        
        return PathConfig(
            template_dir=self._resolve_path(paths.get("template_dir", "")),
            source_dir=self._resolve_path(paths.get("source_dir", "")),
            generate_dir=self._resolve_path(paths.get("generate_dir", "")),
            result_dir=self._resolve_path(paths.get("result_dir", "")),
            ccs_workspace=self._resolve_path(paths.get("ccs_workspace", paths.get("generate_dir", ""))),
            ccs_executable=self._resolve_path(tools.get("ccs_executable", "")),
            ccs_dss=self._resolve_path(tools.get("ccs_dss", "")),
            ccxml=self._resolve_path(tools.get("ccxml", "")),
        )
    
    def _parse_paths_legacy(self, raw: Dict) -> PathConfig:
        """解析旧格式路径配置"""
        return PathConfig(
            template_dir=self._resolve_path(raw.get("template_dir", "")),
            source_dir=self._resolve_path(raw.get("source_dir", "")),
            generate_dir=self._resolve_path(raw.get("generate_dir", "")),
            result_dir=self._resolve_path(raw.get("result_dir", "")),
            ccs_workspace=self._resolve_path(raw.get("ccs_workspace", raw.get("generate_dir", ""))),
            ccs_executable=self._resolve_path(raw.get("ccs_executable", "")),
            ccs_dss=self._resolve_path(raw.get("ccs_dss", "")),
            ccxml=self._resolve_path(raw.get("ccxml", "")),
        )
    
    def _parse_build_config_new(self, raw: Dict) -> BuildConfig:
        """解析新格式构建配置"""
        build = raw.get("build", {})
        return BuildConfig(
            build_config=build.get("build_config", CONFIG_DEFAULTS["build_config"]),
            build_timeout=build.get("build_timeout", CONFIG_DEFAULTS["build_timeout"]),
            max_build_threads=build.get("max_build_threads", CONFIG_DEFAULTS["max_build_threads"]),
            do_generate=build.get("do_generate", CONFIG_DEFAULTS["do_generate"]),
            do_build=build.get("do_build", CONFIG_DEFAULTS["do_build"]),
        )
    
    def _parse_build_config_legacy(self, raw: Dict) -> BuildConfig:
        """解析旧格式构建配置"""
        return BuildConfig(
            build_config=raw.get("build_config", CONFIG_DEFAULTS["build_config"]),
            build_timeout=raw.get("build_timeout", CONFIG_DEFAULTS["build_timeout"]),
            max_build_threads=raw.get("max_build_threads", raw.get("max_threads", CONFIG_DEFAULTS["max_build_threads"])),
            do_generate=raw.get("do_generate", CONFIG_DEFAULTS["do_generate"]),
            do_build=raw.get("do_build", CONFIG_DEFAULTS["do_build"]),
        )
    
    def _parse_test_config_new(self, raw: Dict) -> TestConfig:
        """解析新格式测试配置"""
        test = raw.get("test", {})
        return TestConfig(
            test_timeout=test.get("test_timeout", CONFIG_DEFAULTS["test_timeout"]),
            test_batch_size=test.get("test_batch_size", CONFIG_DEFAULTS["test_batch_size"]),
            result_addr=test.get("result_addr", CONFIG_DEFAULTS["result_addr"]),
            success_val=test.get("success_val", CONFIG_DEFAULTS["success_val"]),
            error_val=test.get("error_val", CONFIG_DEFAULTS["error_val"]),
            device=test.get("device", ""),
            cpu=test.get("cpu", ""),
            do_test=test.get("do_test", CONFIG_DEFAULTS["do_test"]),
            auto_resume=test.get("auto_resume", CONFIG_DEFAULTS["auto_resume"]),
            max_retries=test.get("max_retries", CONFIG_DEFAULTS["max_retries"]),
            retry_delay=test.get("retry_delay", CONFIG_DEFAULTS["retry_delay"]),
        )
    
    def _parse_test_config_legacy(self, raw: Dict) -> TestConfig:
        """解析旧格式测试配置"""
        return TestConfig(
            test_timeout=raw.get("timeout", raw.get("test_timeout", CONFIG_DEFAULTS["test_timeout"])),
            test_batch_size=raw.get("test_batch_size", CONFIG_DEFAULTS["test_batch_size"]),
            result_addr=raw.get("result_addr", CONFIG_DEFAULTS["result_addr"]),
            success_val=raw.get("success_val", CONFIG_DEFAULTS["success_val"]),
            error_val=raw.get("error_val", CONFIG_DEFAULTS["error_val"]),
            device=raw.get("device", ""),
            cpu=raw.get("cpu", ""),
            do_test=raw.get("do_test", CONFIG_DEFAULTS["do_test"]),
            auto_resume=raw.get("auto_resume", CONFIG_DEFAULTS["auto_resume"]),
            max_retries=raw.get("max_retries", CONFIG_DEFAULTS["max_retries"]),
            retry_delay=raw.get("retry_delay", CONFIG_DEFAULTS["retry_delay"]),
        )
    
    def _parse_memory_segments_new(self, raw: Dict) -> List[MemorySegment]:
        """解析新格式内存段配置"""
        mem = raw.get("memory_segments", {})
        segments_data = mem.get("segments", DEFAULT_MEMORY_SEGMENTS)
        
        return [
            MemorySegment(
                name=s["name"],
                addr=s["addr"],
                len=s["len"],
                width=s.get("width", 15)
            )
            for s in segments_data
        ]
    
    def _parse_memory_segments_legacy(self, raw: Dict) -> List[MemorySegment]:
        """解析旧格式内存段配置"""
        if "cases" in raw and len(raw["cases"]) > 0 and "segments" in raw["cases"][0]:
            segments_data = raw["cases"][0]["segments"]
        else:
            segments_data = DEFAULT_MEMORY_SEGMENTS

        return [
            MemorySegment(
                name=s["name"],
                addr=s["addr"],
                len=s["len"],
                width=s.get("width", 15)
            )
            for s in segments_data
        ]

    def _parse_export_points_new(self, raw: Dict) -> List[ExportPoint]:
        """解析新格式导出时间点配置"""
        mem = raw.get("memory_segments", {})
        points_data = mem.get("export_points", None)

        # 如果没有配置导出时间点，使用默认值
        if points_data is None:
            return list(DEFAULT_EXPORT_POINTS)

        return [
            ExportPoint(
                when=p.get("when", "after_run"),
                enabled=p.get("enabled", True),
                subdir=p.get("subdir", "Memory")
            )
            for p in points_data
        ]

    def _parse_export_points_legacy(self, raw: Dict) -> List[ExportPoint]:
        """解析旧格式导出时间点配置"""
        # 旧格式默认只在运行后导出
        return list(DEFAULT_EXPORT_POINTS)

    def _parse_result_check_new(self, raw: Dict) -> ResultCheck:
        """解析新格式结果判断配置"""
        test = raw.get("test", {})
        rc_data = test.get("result_check", {})

        if not rc_data:
            return ResultCheck()

        return ResultCheck(
            method=rc_data.get("method", "breakpoint"),
            success_label=rc_data.get("success_label", "Right"),
            fail_label=rc_data.get("fail_label", "IDLE"),
            check_addr=rc_data.get("check_addr", ""),
            success_val=rc_data.get("success_val", ""),
            fail_val=rc_data.get("fail_val", ""),
            expression=rc_data.get("expression", ""),
            expected_val=rc_data.get("expected_val", "")
        )

    def _parse_result_check_legacy(self, raw: Dict) -> ResultCheck:
        """解析旧格式结果判断配置"""
        # 旧格式使用默认断点方式
        return ResultCheck()

    def _parse_cases(self, raw: Dict) -> List[TestCase]:
        """解析测试用例配置"""
        cases = []
        if "cases" in raw:
            for case_data in raw["cases"]:
                segments = [
                    MemorySegment(
                        name=s["name"],
                        addr=s["addr"],
                        len=s["len"],
                        width=s.get("width", 15)
                    )
                    for s in case_data.get("segments", self.memory_segments)
                ]
                # 解析导出时间点配置
                export_points_data = case_data.get("export_points", None)
                if export_points_data is not None:
                    export_points = [
                        ExportPoint(
                            when=p.get("when", "after_run"),
                            enabled=p.get("enabled", True),
                            subdir=p.get("subdir", "Memory")
                        )
                        for p in export_points_data
                    ]
                else:
                    export_points = list(self.export_points)

                # 解析结果判断配置
                rc_data = case_data.get("result_check", None)
                if rc_data is not None:
                    result_check = ResultCheck(
                        method=rc_data.get("method", "breakpoint"),
                        success_label=rc_data.get("success_label", "Right"),
                        fail_label=rc_data.get("fail_label", "IDLE"),
                        check_addr=rc_data.get("check_addr", ""),
                        success_val=rc_data.get("success_val", ""),
                        fail_val=rc_data.get("fail_val", ""),
                        expression=rc_data.get("expression", ""),
                        expected_val=rc_data.get("expected_val", "")
                    )
                else:
                    result_check = ResultCheck(self.result_check)

                cases.append(TestCase(
                    name=case_data.get("name", ""),
                    out=self._resolve_path(case_data.get("out", "")),
                    dat_dir=case_data.get("dat_dir", ""),
                    segments=segments,
                    export_points=export_points,
                    result_check=result_check,
                ))
        return cases
    
    def validate(self):
        """验证配置"""
        # 获取生成模式（默认为 template）
        generation_mode = self._raw.get("generation", {}).get("generation_mode", "template")
        self.paths.validate(generation_mode)
        
        if self.build.build_timeout <= 0:
            raise ConfigValidationError("build_timeout", "必须大于 0", self.build.build_timeout)
        if self.build.max_build_threads <= 0:
            raise ConfigValidationError("max_build_threads", "必须大于 0", self.build.max_build_threads)
        if self.test.test_timeout <= 0:
            raise ConfigValidationError("test_timeout", "必须大于 0", self.test.test_timeout)
        
        try:
            int(self.test.result_addr, 16)
        except ValueError:
            raise ConfigValidationError("result_addr", "必须是有效的十六进制地址", self.test.result_addr)
        
        try:
            int(self.test.success_val, 16)
        except ValueError:
            raise ConfigValidationError("success_val", "必须是有效的十六进制值", self.test.success_val)
        
        try:
            int(self.test.error_val, 16)
        except ValueError:
            raise ConfigValidationError("error_val", "必须是有效的十六进制值", self.test.error_val)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于生成 full_regr.json，使用旧格式）"""
        return {
            "template_dir": str(self.paths.template_dir),
            "source_dir": str(self.paths.source_dir),
            "generate_dir": str(self.paths.generate_dir),
            "result_dir": str(self.paths.result_dir),
            "ccs_workspace": str(self.paths.ccs_workspace),
            "ccs_executable": str(self.paths.ccs_executable),
            "ccs_dss": str(self.paths.ccs_dss),
            "ccxml": str(self.paths.ccxml),
            "build_config": self.build.build_config,
            "build_timeout": self.build.build_timeout,
            "max_build_threads": self.build.max_build_threads,
            "timeout": self.test.test_timeout,
            "test_batch_size": self.test.test_batch_size,
            "result_addr": self.test.result_addr,
            "success_val": self.test.success_val,
            "error_val": self.test.error_val,
            "device": self.test.device,
            "cpu": self.test.cpu,
            "do_generate": self.build.do_generate,
            "do_build": self.build.do_build,
            "do_test": self.test.do_test,
            "log_retention_days": self._raw.get("log_retention_days", CONFIG_DEFAULTS["log_retention_days"]),
            "cases": [
                {
                    "name": c.name,
                    "out": str(c.out),
                    "dat_dir": c.dat_dir,
                    "segments": [
                        {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width}
                        for s in c.segments
                    ],
                    "export_points": [
                        {"when": p.when, "enabled": p.enabled, "subdir": p.subdir}
                        for p in c.export_points
                    ],
                    "result_check": {
                        "method": c.result_check.method,
                        "success_label": c.result_check.success_label,
                        "fail_label": c.result_check.fail_label,
                        "check_addr": c.result_check.check_addr,
                        "success_val": c.result_check.success_val,
                        "fail_val": c.result_check.fail_val,
                        "expression": c.result_check.expression,
                        "expected_val": c.result_check.expected_val
                    }
                }
                for c in self.cases
            ]
        }
    
    def save(self, path: Union[str, Path]):
        """保存配置到文件（保留原始格式和注释）"""
        path = Path(path)
        
        # 获取当前配置字典（保留原始格式）
        config_dict = self._get_save_dict()
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
    
    def _get_save_dict(self) -> Dict[str, Any]:
        """
        获取用于保存的配置字典
        保留原始格式（新格式分组结构）和注释
        """
        # 从界面获取最新值
        config_dict = dict(self._raw)
        
        # 更新 paths 分组
        if "paths" not in config_dict:
            config_dict["paths"] = {}
        config_dict["paths"].update({
            "template_dir": str(self.paths.template_dir),
            "source_dir": str(self.paths.source_dir),
            "generate_dir": str(self.paths.generate_dir),
            "result_dir": str(self.paths.result_dir),
            "ccs_workspace": str(self.paths.ccs_workspace),
        })
        
        # 更新 tools 分组
        if "tools" not in config_dict:
            config_dict["tools"] = {}
        config_dict["tools"].update({
            "ccs_executable": str(self.paths.ccs_executable),
            "ccs_dss": str(self.paths.ccs_dss),
            "ccxml": str(self.paths.ccxml),
        })
        
        # 更新 build 分组
        if "build" not in config_dict:
            config_dict["build"] = {}
        config_dict["build"].update({
            "build_config": self.build.build_config,
            "build_timeout": self.build.build_timeout,
            "max_build_threads": self.build.max_build_threads,
            "do_generate": self.build.do_generate,
            "do_build": self.build.do_build,
        })
        
        # 更新 test 分组
        if "test" not in config_dict:
            config_dict["test"] = {}
        config_dict["test"].update({
            "test_timeout": self.test.test_timeout,
            "test_batch_size": self.test.test_batch_size,
            "result_addr": self.test.result_addr,
            "success_val": self.test.success_val,
            "error_val": self.test.error_val,
            "device": self.test.device,
            "cpu": self.test.cpu,
            "do_test": self.test.do_test,
        })
        
        # 更新 generation 分组
        generation_mode = config_dict.get("generation", {}).get("generation_mode", "template")
        if "generation" not in config_dict:
            config_dict["generation"] = {}
        config_dict["generation"]["generation_mode"] = generation_mode
        
        # 更新 memory_segments 分组
        if "memory_segments" not in config_dict:
            config_dict["memory_segments"] = {}
        config_dict["memory_segments"]["segments"] = [
            {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width}
            for s in self.memory_segments
        ]
        config_dict["memory_segments"]["export_points"] = [
            {"when": p.when, "enabled": p.enabled, "subdir": p.subdir}
            for p in self.export_points
        ]

        # 更新 test 分组中的 result_check
        if "test" not in config_dict:
            config_dict["test"] = {}
        config_dict["test"]["result_check"] = {
            "method": self.result_check.method,
            "success_label": self.result_check.success_label,
            "fail_label": self.result_check.fail_label,
            "check_addr": self.result_check.check_addr,
            "success_val": self.result_check.success_val,
            "fail_val": self.result_check.fail_val,
            "expression": self.result_check.expression,
            "expected_val": self.result_check.expected_val
        }

        # 更新 cases
        if self.cases:
            config_dict["cases"] = [
                {
                    "name": c.name,
                    "out": str(c.out),
                    "dat_dir": c.dat_dir,
                    "segments": [
                        {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width}
                        for s in c.segments
                    ],
                    "export_points": [
                        {"when": p.when, "enabled": p.enabled, "subdir": p.subdir}
                        for p in c.export_points
                    ],
                    "result_check": {
                        "method": c.result_check.method,
                        "success_label": c.result_check.success_label,
                        "fail_label": c.result_check.fail_label,
                        "check_addr": c.result_check.check_addr,
                        "success_val": c.result_check.success_val,
                        "fail_val": c.result_check.fail_val,
                        "expression": c.result_check.expression,
                        "expected_val": c.result_check.expected_val
                    }
                }
                for c in self.cases
            ]

        # 更新 log 分组
        if "log" not in config_dict:
            config_dict["log"] = {}
        config_dict["log"]["log_retention_days"] = config_dict.get("log", {}).get("log_retention_days", CONFIG_DEFAULTS["log_retention_days"])
        
        return config_dict
    
    def __repr__(self) -> str:
        return f"Config(paths={self.paths}, build={self.build}, test={self.test}, cases={len(self.cases)})"
