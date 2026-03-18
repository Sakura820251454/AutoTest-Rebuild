#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关于对话框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont


class AboutDialog(QDialog):
    """关于对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("关于 AutoTest GUI")
        self.setFixedSize(400, 300)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("AutoTest GUI")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 版本
        version_label = QLabel("版本: 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        # 描述
        desc_label = QLabel(
            "TI C2000 DSP 自动化测试工具\n\n"
            "支持功能:\n"
            "• 工程生成\n"
            "• 自动构建\n"
            "• 硬件测试\n"
            "• 内存导出\n"
            "• 结果分析"
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 确定按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
