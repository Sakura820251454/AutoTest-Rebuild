#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径选择器组件

提供带浏览按钮的路径输入框
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QLabel
)
from PyQt5.QtCore import pyqtSignal


class PathSelector(QWidget):
    """路径选择器组件"""
    
    path_changed = pyqtSignal(str)  # 路径变更信号
    
    def __init__(self, select_type: str = "file", filter_str: str = "", parent=None):
        """
        初始化路径选择器
        
        Args:
            select_type: 选择类型，"file" 或 "dir"
            filter_str: 文件过滤器（仅 file 类型有效）
            parent: 父部件
        """
        super().__init__(parent)
        
        self.select_type = select_type
        self.filter_str = filter_str
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 路径输入框
        self.path_edit = QLineEdit()
        self.path_edit.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.path_edit)
        
        # 浏览按钮
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setFixedWidth(70)
        self.browse_btn.clicked.connect(self.on_browse)
        layout.addWidget(self.browse_btn)
    
    def on_browse(self):
        """浏览按钮点击处理"""
        current_path = self.path_edit.text()
        
        if self.select_type == "file":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择文件",
                current_path,
                self.filter_str
            )
        else:  # dir
            path = QFileDialog.getExistingDirectory(
                self,
                "选择目录",
                current_path
            )
        
        if path:
            self.path_edit.setText(path)
            self.path_changed.emit(path)
    
    def on_text_changed(self, text: str):
        """文本变更处理"""
        self.path_changed.emit(text)
    
    def get_path(self) -> str:
        """获取当前路径"""
        return self.path_edit.text()
    
    def set_path(self, path: str):
        """设置路径"""
        self.path_edit.setText(path)
    
    def set_placeholder(self, text: str):
        """设置占位符文本"""
        self.path_edit.setPlaceholderText(text)
