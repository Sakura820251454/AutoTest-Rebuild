"""
日志管理模块

@input logging, sys.stdout (标准日志和输出)
@output setup_logger(), get_logger(), LogContext类, log_exception()
@pos 核心基础模块，统一日志格式、彩色控制台输出、文件日志、上下文管理

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import os
import sys
import logging
import atexit
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Union
from logging.handlers import RotatingFileHandler


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_loggers: Dict[str, logging.Logger] = {}
_log_dir: Optional[Path] = None
_file_handlers: Dict[str, logging.FileHandler] = {}


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（仅用于控制台）"""
    
    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    log_dir: Optional[Union[str, Path]] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    root_level: int = logging.DEBUG,
) -> Path:
    """
    设置日志系统
    
    Args:
        log_dir: 日志目录，默认为当前工作目录下的 logs/YYYY-MM-DD/
        console_level: 控制台日志级别
        file_level: 文件日志级别
        root_level: 根日志级别
    
    Returns:
        日志目录路径
    """
    global _log_dir
    
    if log_dir is None:
        _log_dir = Path.cwd() / "logs" / datetime.now().strftime("%Y-%m-%d")
    else:
        _log_dir = Path(log_dir)
    
    _log_dir.mkdir(parents=True, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = ColoredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    main_log_file = _log_dir / "autotest.log"
    file_handler = logging.FileHandler(main_log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    _file_handlers["main"] = file_handler
    
    atexit.register(_cleanup_handlers)
    
    return _log_dir


def get_logger(name: str, separate_file: bool = False) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称（通常使用 __name__）
        separate_file: 是否创建独立的日志文件
    
    Returns:
        日志记录器实例
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if separate_file and _log_dir:
        safe_name = name.replace(".", "_").replace(" ", "_")
        log_file = _log_dir / f"{safe_name}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        _file_handlers[name] = file_handler
    
    _loggers[name] = logger
    return logger


def get_log_dir() -> Optional[Path]:
    """获取当前日志目录"""
    return _log_dir


def _cleanup_handlers():
    """清理所有文件处理器"""
    for handler in _file_handlers.values():
        try:
            handler.close()
        except Exception:
            pass
    _file_handlers.clear()


class LogContext:
    """
    日志上下文管理器，用于记录代码块的执行
    
    用法：
        with LogContext(logger, "执行测试用例"):
            # 执行代码
            pass
    """
    
    def __init__(self, logger: logging.Logger, action: str, level: int = logging.INFO):
        self.logger = logger
        self.action = action
        self.level = level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.log(self.level, f"开始: {self.action}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if exc_type is None:
            self.logger.log(self.level, f"完成: {self.action} (耗时 {elapsed:.2f} 秒)")
        else:
            self.logger.error(f"失败: {self.action} (耗时 {elapsed:.2f} 秒) - {exc_val}")
        return False


def log_exception(logger: logging.Logger, exc: Exception, context: str = ""):
    """
    记录异常信息
    
    Args:
        logger: 日志记录器
        exc: 异常对象
        context: 上下文信息
    """
    import traceback
    
    msg = f"异常: {type(exc).__name__}: {exc}"
    if context:
        msg = f"{context} - {msg}"
    
    logger.error(msg)
    logger.debug(traceback.format_exc())
