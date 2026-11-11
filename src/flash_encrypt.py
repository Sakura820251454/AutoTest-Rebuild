# -*- coding: utf-8 -*-
"""
FLASH 段 dat 加密封装

@input encrypt_flash_dat.py（同事提供的加密脚本，优先取程序目录，打包时取包内资源）
@input 导出后的 FLASH.dat（65536 行 × 16 hex，CCS 文件头已去除）
@output FLASH0.dat ~ FLASH3.dat（与 FLASH.dat 同目录，原始 FLASH.dat 不改写）
@pos 导出后处理模块，供 executor 在批量结束后调用，源码/打包两种模式都能用（进程内调用，不依赖系统 Python）

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import importlib.util
import io
import threading
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .logger import get_logger
from .runtime_paths import resource_path

logger = get_logger(__name__)

SCRIPT_NAME = "encrypt_flash_dat.py"
ENCRYPT_TIMEOUT = 600  # 单个 FLASH.dat 的加密超时（秒）

_script_module = None


def script_path() -> Path:
    """加密脚本位置：程序目录优先，打包资源兜底"""
    return resource_path(SCRIPT_NAME)


def _load_script(path: Path):
    """按文件路径加载加密脚本模块（进程内复用，避免每次重新解析）"""
    global _script_module
    if _script_module is not None:
        return _script_module
    spec = importlib.util.spec_from_file_location("encrypt_flash_dat_tool", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载加密脚本: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _script_module = module
    return module


def _failure_detail(output: str, fallback: str) -> str:
    """从脚本输出中提取 ERROR 行，取不到则用兜底信息"""
    for line in reversed(output.strip().splitlines()):
        if line.strip().startswith("ERROR"):
            return line.strip()
    return fallback


def encrypt_flash_dat_file(flash_dat: Path, timeout: int = ENCRYPT_TIMEOUT,
                           verify: bool = False) -> Tuple[bool, str]:
    """
    把一个已导出的 FLASH.dat 拆分成 4 个实例加密文件

    Args:
        flash_dat: 待加密的 FLASH.dat 路径
        timeout: 超时秒数
        verify: 是否让脚本回读 4 个输出、解密重组后与输入逐行比对（对应 --verify，耗时约翻倍）

    Returns:
        (是否成功, 说明信息)；失败信息可直接展示给用户
    """
    flash_dat = Path(flash_dat)
    if not flash_dat.is_file():
        return False, f"FLASH.dat 不存在: {flash_dat}"

    sp = script_path()
    if not sp.is_file():
        return False, f"未找到加密脚本 {SCRIPT_NAME}（应放在程序目录下）"

    try:
        module = _load_script(sp)
    except Exception as e:
        return False, f"加载加密脚本失败: {e}"

    output = io.StringIO()
    result: Dict[str, Any] = {}

    def _worker():
        try:
            with redirect_stdout(output):
                module.split_file(
                    str(flash_dat),
                    module.BY_NAME["FLASH.dat"],
                    None,      # 输出到 FLASH.dat 同目录
                    verify,    # 对应脚本 --verify：回读 4 个输出并逐行比对
                    True,      # 加密
                )
            result["ok"] = True
        except SystemExit as e:
            result["ok"] = False
            result["err"] = f"加密脚本异常退出（exit {e.code}）"
        except BaseException as e:
            result["ok"] = False
            result["err"] = f"{type(e).__name__}: {e}"
            result["trace"] = traceback.format_exc()

    thread = threading.Thread(target=_worker, name="flash-dat-encrypt", daemon=True)
    thread.start()
    thread.join(timeout)

    text = output.getvalue()

    if thread.is_alive():
        return False, f"加密超时（>{timeout}s）: {flash_dat}"

    if not result.get("ok"):
        reason = _failure_detail(text, result.get("err", "未知错误"))
        logger.debug(result.get("trace", ""))
        return False, f"{result.get('err', '加密失败')}；脚本输出: {reason}"

    # 脚本退出 0 也要确认产物真实存在，避免"看起来成功但文件没出来"
    # 实例数跟随脚本自身的 N_INST（当前为 4），避免脚本调整分片数后这里写死
    out_files: List[Path] = [flash_dat.with_name(f"FLASH{i}.dat") for i in range(module.N_INST)]
    missing = [p.name for p in out_files if not p.is_file()]
    if missing:
        return False, f"加密脚本已执行，但缺少产物: {', '.join(missing)}"

    for line in text.strip().splitlines():
        if line.strip():
            logger.debug("  %s", line.strip())
    return True, f"{flash_dat.parent} -> FLASH0~3.dat"
