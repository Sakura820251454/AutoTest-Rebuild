#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一错误提示文案

@input 异常对象 / 路径 / 动作
@output format_error()、describe_exception()
@pos GUI 弹窗与错误条的唯一文案入口：一句话原因 + 涉及的文件/路径 + 建议动作；
     堆栈不进入任何用户可见文案（由调用方单独写入日志页）

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import json

from src.exceptions import (
    AutoTestError,
    ConfigFileNotFoundError,
    ConfigPathError,
    ConfigValidationError,
    GelConfigError,
)


def format_error(reason: str, path=None, action=None) -> str:
    """拼成三段式文案：原因 / 路径 / 建议（缺省项自动省略）"""
    lines = [f"原因：{reason}"]
    if path:
        lines.append(f"路径：{path}")
    if action:
        lines.append(f"建议：{action}")
    return "\n".join(lines)


def describe_exception(exc, path=None, action=None) -> str:
    """把异常翻译成用户可读的三段式文案，不含 traceback / Python 英文原文"""
    reason, default_action = _explain(exc)
    return format_error(
        reason,
        path=path or _path_from_exception(exc),
        action=action or default_action,
    )


def _looks_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(text))


def _path_from_exception(exc):
    """尽量从异常里取一个可展示的路径"""
    filename = getattr(exc, "filename", None)
    if filename:
        return str(filename)

    details = getattr(exc, "details", None) or {}
    for key in ("path", "out_file", "field"):
        if details.get(key):
            return str(details[key])
    return None


def _explain(exc):
    """返回 (原因, 建议动作)"""
    if isinstance(exc, ConfigFileNotFoundError):
        return ("配置文件不存在",
                "请确认文件路径，或通过“文件 → 打开配置...”重新选择")
    if isinstance(exc, ConfigValidationError):
        return ("配置文件内容校验未通过",
                "请检查报错字段的取值后重新保存")
    if isinstance(exc, ConfigPathError):
        return ("配置中的路径无效",
                "请检查路径是否存在、是否有访问权限")
    if isinstance(exc, GelConfigError):
        return (exc.message, exc.suggestion)
    if isinstance(exc, json.JSONDecodeError):
        return (f"配置文件格式错误（第 {exc.lineno} 行第 {exc.colno} 列）",
                "请检查 JSON 是否缺少逗号、引号或括号，必要时改用“恢复默认”")
    if isinstance(exc, UnicodeDecodeError):
        return ("配置文件编码不是 UTF-8",
                "请用 UTF-8 编码重新保存配置文件")
    if isinstance(exc, PermissionError):
        return ("没有访问权限",
                "请关闭占用该文件的程序，或换一个有写入权限的目录")
    if isinstance(exc, FileNotFoundError):
        return ("找不到文件或目录",
                "请确认路径是否正确，必要时重新选择")
    if isinstance(exc, IsADirectoryError):
        return ("路径指向的是目录，不是文件",
                "请重新选择具体文件")
    if isinstance(exc, NotADirectoryError):
        return ("路径中有一段不是目录",
                "请检查路径拼写后重试")
    if isinstance(exc, OSError):
        return ("文件或目录操作失败",
                "请检查磁盘空间、路径长度与访问权限")
    if isinstance(exc, AutoTestError):
        return (str(getattr(exc, "message", exc)),
                "请根据提示修正后重试")

    text = str(exc).strip()
    if text and _looks_chinese(text):
        return (text, "请根据提示修正后重试")
    return (f"发生未预期的错误（{type(exc).__name__}）",
            "请打开“日志”页查看详细信息")
