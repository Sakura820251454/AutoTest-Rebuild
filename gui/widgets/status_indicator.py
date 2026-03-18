#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
状态指示器组件

用于显示硬件连接状态等
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette


class StatusIndicator(QWidget):
    """状态指示器组件"""
    
    STATUS_COLORS = {
        "unknown": ("#808080", "未知"),  # 灰色
        "checking": ("#FFA500", "检测中"),  # 橙色
        "connected": ("#00AA00", "已连接"),  # 绿色
        "disconnected": ("#FF0000", "未连接"),  # 红色
        "error": ("#FF0000", "错误"),  # 红色
    }
    
    def __init__(self, label: str = "", parent=None):
        """
        初始化状态指示器
        
        Args:
            label: 标签文本
            parent: 父部件
        """
        super().__init__(parent)
        
        self._setup_ui(label)
    
    def _setup_ui(self, label: str):
        """初始化界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 状态指示灯
        self.indicator = QLabel("●")
        self.indicator.setStyleSheet("font-size: 20px; color: #808080;")
        layout.addWidget(self.indicator)
        
        # 标签
        if label:
            self.label = QLabel(label)
            layout.addWidget(self.label)
        
        # 状态文本
        self.status_text = QLabel("未知")
        layout.addWidget(self.status_text)
        
        layout.addStretch()
    
    def set_status(self, status: str, message: str = None):
        """
        设置状态
        
        Args:
            status: 状态类型，"unknown", "checking", "connected", "disconnected", "error"
            message: 自定义状态消息，None 使用默认消息
        """
        color, default_msg = self.STATUS_COLORS.get(status, self.STATUS_COLORS["unknown"])
        
        self.indicator.setStyleSheet(f"font-size: 20px; color: {color};")
        self.status_text.setText(message or default_msg)
    
    def set_checking(self):
        """设置为检测中状态"""
        self.set_status("checking")
    
    def set_connected(self, message: str = None):
        """设置为已连接状态"""
        self.set_status("connected", message)
    
    def set_disconnected(self, message: str = None):
        """设置为未连接状态"""
        self.set_status("disconnected", message)
    
    def set_error(self, message: str = None):
        """设置为错误状态"""
        self.set_status("error", message)
