#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误对话框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon


class ErrorDialog(QDialog):
    """错误对话框"""
    
    def __init__(self, title: str, message: str, details: str = None, parent=None):
        """
        初始化错误对话框
        
        Args:
            title: 错误标题
            message: 错误消息
            details: 详细错误信息
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(500, 300)
        self.setModal(True)
        
        self._setup_ui(message, details)
    
    def _setup_ui(self, message: str, details: str = None):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 错误图标和消息
        msg_layout = QHBoxLayout()
        
        # 错误消息
        self.msg_label = QLabel(message)
        self.msg_label.setWordWrap(True)
        msg_layout.addWidget(self.msg_label)
        
        layout.addLayout(msg_layout)
        
        # 详细信息（可选）
        if details:
            self.details_text = QTextEdit()
            self.details_text.setPlainText(details)
            self.details_text.setReadOnly(True)
            self.details_text.setMaximumHeight(150)
            layout.addWidget(self.details_text)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 复制按钮
        copy_btn = QPushButton("复制错误信息")
        copy_btn.clicked.connect(self.copy_error)
        btn_layout.addWidget(copy_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def copy_error(self):
        """复制错误信息到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        
        text = self.msg_label.text()
        if hasattr(self, 'details_text'):
            text += "\n\n详细信息:\n" + self.details_text.toPlainText()
        
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        QMessageBox.information(self, "提示", "错误信息已复制到剪贴板")
    
    @staticmethod
    def show_error(parent, title: str, message: str, details: str = None):
        """
        显示错误对话框的静态方法
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息
            details: 详细信息
        """
        dialog = ErrorDialog(title, message, details, parent)
        dialog.exec()
