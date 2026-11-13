#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志面板

用于显示执行日志：按级别着色、HTML 转义、保留换行、限制内存条数

@input 日志文本与级别
@output 可过滤/搜索/保存的日志视图，可打开日志目录
@pos “日志”标签页，承载 worker、配置加载、硬件检测的日志输出

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import html
import re
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox
)
from .no_scroll_spinbox import NoScrollComboBox as QComboBox
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from datetime import datetime

from ..utils.message_boxes import critical, warning

# 内存中保留的最大日志条数，超出后丢弃最旧的，避免长时间运行卡顿
MAX_LOG_ENTRIES = 20000

LEVEL_COLORS = {
    "INFO": "#000000",
    "WARNING": "#FFA500",
    "ERROR": "#FF0000",
    "DEBUG": "#808080",
}

FILTER_LEVEL_MAP = {
    "全部": None,
    "信息": "INFO",
    "警告": "WARNING",
    "错误": "ERROR",
    "调试": "DEBUG",
}


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def normalize_level(level) -> str:
    """统一日志级别写法，未知级别按 INFO 处理

    控制台彩色 formatter 可能把 ANSI 颜色码拼进级别名（如 ``\x1b[31mERROR``），
    这里先剥掉颜色码再判断，避免 ERROR 被误判成 INFO。
    """
    value = _ANSI_RE.sub("", str(level or "INFO")).strip().upper()
    return value if value in LEVEL_COLORS else "INFO"


def format_log_html(timestamp: str, level: str, message) -> str:
    """
    生成单条日志的 HTML

    先转义再拼接，避免路径中的 & < > 破坏显示；换行转成 <br/>，
    并用 pre-wrap 保留缩进，防止多行路径连成一串。
    """
    level = normalize_level(level)
    color = LEVEL_COLORS[level]
    prefix = html.escape(f"[{timestamp}] [{level}] ")
    body = html.escape(str(message))
    body = body.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
    return (
        f'<div style="white-space: pre-wrap; color: {color};">'
        f'{prefix}{body}</div>'
    )


class LogPanel(QWidget):
    """日志面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.logs = []  # 日志记录列表（内存上限 MAX_LOG_ENTRIES）
        self._filter_type = "全部"

        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # ===== 工具栏 =====
        toolbar_layout = QHBoxLayout()
        
        # 搜索框
        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索...")
        self.search_edit.returnPressed.connect(self.search_logs)
        toolbar_layout.addWidget(self.search_edit)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.search_logs)
        toolbar_layout.addWidget(self.search_btn)
        
        toolbar_layout.addSpacing(20)
        
        # 过滤下拉框
        toolbar_layout.addWidget(QLabel("过滤:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(FILTER_LEVEL_MAP.keys()))
        self.filter_combo.currentTextChanged.connect(self.filter_logs)
        toolbar_layout.addWidget(self.filter_combo)
        
        toolbar_layout.addStretch()
        
        # 自动滚动选项
        self.auto_scroll_check = QPushButton("自动滚动")
        self.auto_scroll_check.setCheckable(True)
        self.auto_scroll_check.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_check)
        
        layout.addLayout(toolbar_layout)
        
        # ===== 日志显示区域 =====
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.log_text)
        
        # ===== 按钮区域 =====
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.open_dir_btn = QPushButton("打开日志目录")
        self.open_dir_btn.clicked.connect(self.open_log_dir)
        button_layout.addWidget(self.open_dir_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("保存日志")
        self.save_btn.clicked.connect(self.save_logs)
        button_layout.addWidget(self.save_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)

    def _is_visible(self, level: str) -> bool:
        """当前过滤条件下该级别是否显示"""
        target = FILTER_LEVEL_MAP.get(self._filter_type)
        return target is None or level == target

    def _auto_scroll(self):
        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _render(self):
        """按当前过滤条件重绘全部日志"""
        self.log_text.clear()
        for entry in self.logs:
            if self._is_visible(entry["level"]):
                self.log_text.append(format_log_html(
                    entry["timestamp"], entry["level"], entry["message"]))
        self._auto_scroll()
    
    def append_log(self, message: str, level: str = "INFO"):
        """
        添加日志
        
        Args:
            message: 日志消息（可多行；HTML 会被转义）
            level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        """
        level = normalize_level(level)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }
        self.logs.append(entry)

        # 超出上限时丢弃最旧的并重绘，保证内存与控件都不无限增长
        overflow = len(self.logs) - MAX_LOG_ENTRIES
        if overflow > 0:
            del self.logs[:overflow]
            self._render()
            return

        if self._is_visible(level):
            self.log_text.append(format_log_html(timestamp, level, message))
            self._auto_scroll()
    
    def clear_logs(self):
        """清空日志"""
        self.logs.clear()
        self.log_text.clear()
    
    def save_logs(self):
        """保存日志到文件"""
        if not self.logs:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存日志",
            f"autotest_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    for log in self.logs:
                        f.write(f"[{log['timestamp']}] [{log['level']}] {log['message']}\n")
            except Exception as exc:
                from ..utils.error_messages import describe_exception
                critical(
                    self, "保存日志失败",
                    describe_exception(
                        exc, path=path,
                        action="请检查目标文件是否被占用、目录是否有写权限"))

    def open_log_dir(self):
        """用资源管理器打开日志目录"""
        from src.logger import get_log_dir
        from src.runtime_paths import app_path

        log_dir = Path(get_log_dir() or app_path("logs"))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            from ..utils.error_messages import describe_exception
            warning(
                self, "无法打开日志目录",
                describe_exception(
                    exc, path=str(log_dir),
                    action="请检查路径是否存在、是否有写权限"))
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))
        self.append_log(f"已打开日志目录: {log_dir}", "INFO")
    
    def search_logs(self):
        """搜索日志"""
        keyword = self.search_edit.text()
        if not keyword:
            return
        
        # 在日志文本中查找
        if self.log_text.find(keyword):
            return
        
        # 如果没找到，尝试反向查找
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.log_text.setTextCursor(cursor)
        
        self.log_text.find(keyword)
    
    def filter_logs(self, filter_type: str):
        """
        过滤日志显示
        
        Args:
            filter_type: 过滤类型（全部/信息/警告/错误/调试）
        """
        self._filter_type = filter_type if filter_type in FILTER_LEVEL_MAP else "全部"
        self._render()
