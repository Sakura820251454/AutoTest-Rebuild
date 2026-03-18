"""
AutoTest - TI C2000 DSP 自动化测试框架
"""

__version__ = "2.0.0"
__author__ = "AutoTest Team"

from .exceptions import AutoTestError, ConfigError, BuildError, TestError
from .config import Config
from .logger import setup_logger, get_logger
