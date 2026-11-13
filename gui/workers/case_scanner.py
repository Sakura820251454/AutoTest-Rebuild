#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用例预扫描线程

在后台扫描工作区目录，给出“就绪/缺 .out”，避免大目录卡住界面

@input 工作区目录（generate_dir）
@output scanned 信号：[(用例名, 状态, 说明), ...]
@pos 执行页切换到前台时的后台预扫描，不参与真正的测试执行

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
from pathlib import Path
from typing import List, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def scan_cases(generate_dir: Path) -> List[Tuple[str, str, str]]:
    """扫描工作区，返回 [(名称, 状态, 说明)]

    状态：ready（有 .out）/ missing_out（有工程但没有 .out）。
    没有 .project 也没有 .out 的子目录不算用例。
    """
    results: List[Tuple[str, str, str]] = []
    if generate_dir is None or not Path(generate_dir).is_dir():
        return results

    for case_dir in sorted(Path(generate_dir).iterdir()):
        if not case_dir.is_dir() or case_dir.name.startswith("."):
            continue

        has_project = (case_dir / ".project").exists()
        out_files = list(case_dir.rglob("*.out"))
        if out_files:
            results.append((case_dir.name, "ready", "已找到 .out"))
        elif has_project:
            results.append((case_dir.name, "missing_out", "缺少 .out，需先构建"))

    return results


class CaseScanWorker(QThread):
    """后台扫描工作区用例（只读，不改任何文件）"""

    scanned = pyqtSignal(list)  # [(名称, 状态, 说明), ...]

    def __init__(self, generate_dir: Path, parent=None):
        super().__init__(parent)
        self.generate_dir = Path(generate_dir)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            results = scan_cases(self.generate_dir)
            if not self._cancelled:
                self.scanned.emit(results)
        except Exception:
            # 预扫描失败不影响手动执行，界面按空列表处理
            if not self._cancelled:
                self.scanned.emit([])
