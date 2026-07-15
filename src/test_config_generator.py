"""
测试配置生成模块

负责从配置或工作空间生成测试配置文件（full_regr.json）

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import json
from pathlib import Path
from typing import Optional

from .config import Config, DEFAULT_EXPORT_POINTS, DEFAULT_RESULT_CHECK
from .logger import get_logger, LogContext

logger = get_logger(__name__)


def generate_test_config(config: Config, run_timestamp: str, output_path: Optional[Path] = None) -> Path:
    """
    生成测试配置文件（full_regr.json）

    生成规则：
    1. 优先使用配置中已有的用例（config.cases）
    2. 否则从工作空间搜索 .out 文件自动生成

    Args:
        config: 配置对象
        run_timestamp: 运行时间戳
        output_path: 输出文件路径，默认为 full_regr.json

    Returns:
        生成的配置文件路径
    """
    with LogContext(logger, "生成测试配置"):
        # 优先使用配置中已有的用例
        if config.cases:
            logger.info(f"使用配置中的 {len(config.cases)} 个用例")
            return _generate_from_cases(config, run_timestamp, output_path)

        # 否则从工作空间搜索 .out 文件
        return _generate_from_workspace(config, run_timestamp, output_path)


def _generate_from_cases(config: Config, run_timestamp: str, output_path: Optional[Path] = None) -> Path:
    """
    从配置中的用例生成测试配置

    Args:
        config: 配置对象
        run_timestamp: 运行时间戳
        output_path: 输出文件路径

    Returns:
        生成的配置文件路径
    """
    cases = []
    for case in config.cases:
        # 确保 dat_dir 有有效值
        if case.dat_dir:
            dat_dir = case.dat_dir
        else:
            dat_dir = f"5_result_dat/{run_timestamp}/{case.name}"

        # 获取导出时间点配置
        export_points = [
            {"when": ep.when, "enabled": ep.enabled, "subdir": ep.subdir}
            for ep in (case.export_points if case.export_points else config.export_points)
        ]

        # 获取结果判断配置
        rc = case.result_check if case.result_check else config.result_check
        result_check = {
            "method": rc.method,
            "success_label": rc.success_label,
            "fail_label": rc.fail_label,
            "check_addr": rc.check_addr,
            "check_width": rc.check_width,
            "success_val": rc.success_val,
            "fail_val": rc.fail_val,
            "expression": rc.expression,
            "expected_val": rc.expected_val
        }

        case_config = {
            "name": case.name,
            "out": str(case.out).replace("\\", "/"),
            "dat_dir": dat_dir,
            "segments": [
                {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width, "page": s.page}
                for s in (case.segments if case.segments else config.memory_segments)
            ],
            "export_points": export_points,
            "result_check": result_check
        }

        # 添加 is_flash 字段（仅当显式指定时）
        if case.is_flash is not None:
            case_config["is_flash"] = case.is_flash

        cases.append(case_config)

    test_config = {
        "ccxml": str(config.paths.ccxml).replace("\\", "/"),
        "device": config.test.device,
        "cpu": config.test.cpu,
        "timeout": config.test.test_timeout,
        "result_addr": config.test.result_addr,
        "success_val": config.test.success_val,
        "error_val": config.test.error_val,
        "cases": cases
    }

    if output_path is None:
        output_path = Path("full_regr.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_config, f, ensure_ascii=False, indent=2)

    logger.info(f"测试配置已保存: {output_path}")
    return output_path


def _generate_from_workspace(config: Config, run_timestamp: str, output_path: Optional[Path] = None) -> Path:
    """
    从工作空间搜索 .out 文件生成测试配置

    Args:
        config: 配置对象
        run_timestamp: 运行时间戳
        output_path: 输出文件路径

    Returns:
        生成的配置文件路径
    """
    workspace = config.paths.ccs_workspace

    out_files = sorted(workspace.rglob("*.out"))

    if not out_files:
        logger.warning(f"工作空间中没有找到 .out 文件: {workspace}")
        return None

    logger.info(f"找到 {len(out_files)} 个 .out 文件")

    cases = []
    for out_file in out_files:
        case_name = out_file.stem
        dat_dir = f"5_result_dat/{run_timestamp}/{case_name}"

        # 获取导出时间点配置
        export_points = [
            {"when": ep.when, "enabled": ep.enabled, "subdir": ep.subdir}
            for ep in config.export_points
        ]

        # 获取结果判断配置
        rc = config.result_check
        result_check = {
            "method": rc.method,
            "success_label": rc.success_label,
            "fail_label": rc.fail_label,
            "check_addr": rc.check_addr,
            "check_width": rc.check_width,
            "success_val": rc.success_val,
            "fail_val": rc.fail_val,
            "expression": rc.expression,
            "expected_val": rc.expected_val
        }

        cases.append({
            "name": case_name,
            "out": str(out_file.resolve()).replace("\\", "/"),
            "dat_dir": dat_dir,
            "segments": [
                {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width, "page": s.page}
                for s in config.memory_segments
            ],
            "export_points": export_points,
            "result_check": result_check
        })

    test_config = {
        "ccxml": str(config.paths.ccxml).replace("\\", "/"),
        "device": config.test.device,
        "cpu": config.test.cpu,
        "timeout": config.test.test_timeout,
        "result_addr": config.test.result_addr,
        "success_val": config.test.success_val,
        "error_val": config.test.error_val,
        "cases": cases
    }

    if output_path is None:
        output_path = Path("full_regr.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_config, f, ensure_ascii=False, indent=2)

    logger.info(f"测试配置已保存: {output_path}")
    return output_path
