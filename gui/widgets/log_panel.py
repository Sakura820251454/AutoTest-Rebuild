#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志面板

用于显示执行日志
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QLineEdit, QLabel, QFileDialog
)
from PyQt5.QtCore import Qt
from datetime import datetime


class LogPanel(QWidget):
    """日志面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self.logs = []  # 日志记录列表
    
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
        self.filter_combo.addItems(["全部", "信息", "警告", "错误", "调试"])
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
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("保存日志")
        self.save_btn.clicked.connect(self.save_logs)
        button_layout.addWidget(self.save_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def append_log(self, message: str, level: str = "INFO"):
        """
        添加日志
        
        Args:
            message: 日志消息
            level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        
        # 格式化日志文本
        level_colors = {
            "INFO": "#000000",
            "WARNING": "#FFA500",
            "ERROR": "#FF0000",
            "DEBUG": "#808080"
        }
        color = level_colors.get(level, "#000000")
        
        log_text = f"[{timestamp}] [{level}] {message}"
        
        # 添加到显示
        self.log_text.append(f'<span style="color: {color};">{log_text}</span>')
        
        # 自动滚动
        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
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
            except Exception as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "错误", f"保存日志失败:\n{str(e)}")
    
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
            filter_type: 过滤类型
        """
        # 清空显示
        self.log_text.clear()
        
        # 根据过滤类型重新显示
        level_map = {
            "全部": None,
            "信息": "INFO",
            "警告": "WARNING",
            "错误": "ERROR",
            "调试": "DEBUG"
        }
        
        target_level = level_map.get(filter_type)
        
        level_colors = {
            "INFO": "#000000",
            "WARNING": "#FFA500",
            "ERROR": "#FF0000",
            "DEBUG": "#808080"
        }
        
        for log in self.logs:
            if target_level is None or log["level"] == target_level:
                color = level_colors.get(log["level"], "#000000")
                log_text = f"[{log['timestamp']}] [{log['level']}] {log['message']}"
                self.log_text.append(f'<span style="color: {color};">{log_text}</span>')
