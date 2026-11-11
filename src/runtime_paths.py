# -*- coding: utf-8 -*-
"""
运行时路径解析模块

@input sys (frozen / _MEIPASS)
@output is_frozen(), app_root(), bundle_root(), app_path(), resource_path()
@pos 基础模块，所有可写目录与只读资源的唯一路径入口，兼容源码运行与 PyInstaller 打包运行

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包产物中"""
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """
    程序目录，同时是所有数据目录（logs/5_result_dat/6_result_dat_logs/full_regr.json 等）的根

    - 源码模式：项目根目录
    - 打包模式：exe 所在目录
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundle_root() -> Path:
    """
    打包资源根目录

    - 源码模式：与 app_root 相同
    - 打包模式：sys._MEIPASS（onedir 下即 _internal）
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return app_root()


def app_path(rel: str = "") -> Path:
    """
    可写路径：一律以程序目录为基准，不受当前工作目录与快捷方式“起始位置”影响

    Args:
        rel: 相对程序目录的路径，空串表示程序目录本身

    Returns:
        绝对路径
    """
    return (app_root() / rel).resolve()


def resource_path(rel: str) -> Path:
    """
    只读资源路径：外部优先（便于现场替换），打包资源兜底

    Args:
        rel: 相对资源路径，如 "templates/dss_test.js.tmpl"

    Returns:
        存在的路径；均不存在时返回程序目录下的候选路径，由调用方报错
    """
    for base in (app_root(), bundle_root()):
        candidate = base / rel
        if candidate.exists():
            return candidate
    return app_root() / rel
