# -*- coding: utf-8 -*-
"""
AutoTest 回归测试包

只依赖标准库与项目已有的 PyQt5，不引入其它第三方依赖。
统一入口：python tests/run_checks.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# GUI 测试一律离屏运行，避免在任何机器上弹窗阻塞
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
