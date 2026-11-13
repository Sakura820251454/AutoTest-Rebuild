#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建信息（版本号唯一来源）

@input gui/assets/build_info.json（打包时由 AutoTestGUI.spec 生成：commit/build_time）
@output VERSION、APP_NAME、APP_DESC、get_commit()、get_build_time()、runtime_lines()
@pos “帮助 → 关于”对话框的数据来源；版本号如需升级只改这里的 VERSION

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import json
import platform
import struct
import subprocess
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.runtime_paths import app_root, is_frozen, resource_path

# 日期版本：项目内没有其它统一版本来源，统一在此定义
VERSION = "2026.11"

APP_NAME = "AutoTest GUI"
APP_DESC = "TI C2000 DSP 工程生成、构建、硬件测试与内存导出的一体化自动化测试工具"


def _read_stamp() -> dict:
    """读取打包时写入的 build_info.json；源码模式可能不存在"""
    try:
        path = resource_path("gui/assets/build_info.json")
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def get_commit() -> str:
    """当前 git 提交短哈希；打包版取构建时写入的值，取不到显示 "-" """
    if is_frozen():
        return _read_stamp().get("commit") or "-"
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(app_root()), text=True, timeout=3).strip() or "-"
    except Exception:
        return _read_stamp().get("commit") or "-"


def get_build_time() -> str:
    """构建时间；打包版用 exe 修改时间，源码模式用 build_info.json（没有则 "-"）"""
    if is_frozen():
        try:
            from datetime import datetime
            return datetime.fromtimestamp(
                Path(sys.executable).stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "-"
    return _read_stamp().get("build_time") or "-"


def runtime_lines() -> List[str]:
    """运行环境关键信息（打包/源码、系统、Python/PyQt5/Qt、位数）"""
    from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    bits = struct.calcsize("P") * 8
    package = "打包版" if is_frozen() else "源码模式"
    return [
        f"运行: {package} · {platform.system()} {platform.release()} · {bits} 位",
        f"环境: Python {platform.python_version()} · PyQt5 {PYQT_VERSION_STR} · Qt {QT_VERSION_STR}",
    ]


def about_lines() -> List[str]:
    """关于对话框的正文（控制在十几行内，不写更新日志）"""
    return [
        APP_NAME,
        APP_DESC,
        f"版本: {VERSION}（日期版本，定义于 gui/utils/build_info.py）",
        f"构建: {get_build_time()}",
        f"提交: {get_commit()}",
    ] + runtime_lines()
