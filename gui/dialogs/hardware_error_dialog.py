#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件连接错误对话框

在硬件连接失败时显示，提供断点续测选项
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class HardwareErrorDialog(QDialog):
    """硬件连接错误对话框"""
    
    def __init__(self, batch_number: int, error_message: str = "", parent=None):
        """
        初始化硬件连接错误对话框
        
        Args:
            batch_number: 失败的批次号（1-based）
            error_message: 错误信息
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.batch_number = batch_number
        self.resume_batch = batch_number  # 默认从失败的批次开始
        
        self.setWindowTitle("硬件连接失败")
        self.setMinimumSize(550, 400)
        self.setModal(True)
        
        self._setup_ui(error_message)
    
    def _setup_ui(self, error_message: str):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("⚠️ 硬件连接断开")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #CC0000;")
        layout.addWidget(title_label)
        
        # 错误信息
        error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout(error_group)
        
        error_text = QLabel(
            f"<b>第 {self.batch_number} 批执行前检测到硬件连接断开！</b><br><br>"
            f"已执行 {self.batch_number - 1} 个批次，可以从第 {self.batch_number} 批继续执行。"
        )
        error_text.setWordWrap(True)
        error_layout.addWidget(error_text)
        
        if error_message:
            details_text = QTextEdit()
            details_text.setPlainText(error_message)
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(100)
            error_layout.addWidget(details_text)
        
        layout.addWidget(error_group)
        
        # 检查指南
        guide_group = QGroupBox("请检查以下项目")
        guide_layout = QVBoxLayout(guide_group)
        
        guide_text = QLabel(
            "1. XDS100 调试器是否正确连接到电脑<br>"
            "2. 目标板是否上电<br>"
            "3. FTDI 驱动是否安装正确<br>"
            "4. USB 线缆是否正常<br>"
            "5. 目标板电源是否稳定"
        )
        guide_text.setWordWrap(True)
        guide_layout.addWidget(guide_text)
        
        layout.addWidget(guide_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        # 断点续测按钮
        resume_btn = QPushButton(f"从第 {self.batch_number} 批继续")
        resume_btn.setDefault(True)
        resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066CC;
                color: white;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #0055AA;
            }
        """)
        resume_btn.clicked.connect(self.on_resume_clicked)
        btn_layout.addWidget(resume_btn)
        
        layout.addLayout(btn_layout)
    
    def on_resume_clicked(self):
        """断点续测按钮点击"""
        self.accept()
    
    def get_resume_batch(self) -> int:
        """获取续测的起始批次号"""
        return self.resume_batch
    
    @staticmethod
    def show_error(parent, batch_number: int, error_message: str = "") -> tuple:
        """
        显示硬件连接错误对话框
        
        Args:
            parent: 父窗口
            batch_number: 失败的批次号
            error_message: 错误信息
            
        Returns:
            (是否继续, 起始批次号)
        """
        dialog = HardwareErrorDialog(batch_number, error_message, parent)
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            return True, dialog.get_resume_batch()
        else:
            return False, 0
