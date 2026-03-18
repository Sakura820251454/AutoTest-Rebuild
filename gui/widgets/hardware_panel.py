#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件检测面板

用于检测硬件连接状态
"""

import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from .status_indicator import StatusIndicator
from ..workers.hardware_checker import HardwareChecker


class HardwarePanel(QWidget):
    """硬件检测面板"""
    
    check_completed = pyqtSignal(bool, str)  # 检测完成信号(成功/失败, 消息)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config: Optional[Config] = None
        self.checker: Optional[HardwareChecker] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # ===== 状态显示组 =====
        status_group = QGroupBox("硬件连接状态")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(15)
        
        # 仿真器状态
        self.emulator_indicator = StatusIndicator("仿真器连接")
        status_layout.addWidget(self.emulator_indicator)
        
        # 目标板状态
        self.target_indicator = StatusIndicator("目标板连接")
        status_layout.addWidget(self.target_indicator)
        
        layout.addWidget(status_group)
        
        # ===== 详细信息组 =====
        detail_group = QGroupBox("详细信息")
        detail_layout = QVBoxLayout(detail_group)
        
        # 配置信息标签
        self.config_info_label = QLabel("请先加载配置文件")
        self.config_info_label.setWordWrap(True)
        detail_layout.addWidget(self.config_info_label)
        
        # 检测结果文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText('点击"开始检测"按钮检测硬件连接状态...')
        detail_layout.addWidget(self.result_text)
        
        layout.addWidget(detail_group)
        
        # ===== 按钮区域 =====
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.check_btn = QPushButton("开始检测")
        self.check_btn.setFixedWidth(120)
        self.check_btn.clicked.connect(self.start_check)
        button_layout.addWidget(self.check_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 添加弹性空间
        layout.addStretch()
    
    def set_config(self, config: Config):
        """
        设置配置
        
        Args:
            config: 配置对象
        """
        self.config = config
        
        # 更新配置信息显示
        info_text = f"""
<b>CCXML 文件:</b> {config.paths.ccxml}<br>
<b>设备名称:</b> {config.test.device}<br>
<b>CPU 名称:</b> {config.test.cpu}<br>
<b>DSS 执行器:</b> {config.paths.ccs_dss}
        """.strip()
        self.config_info_label.setText(info_text)
    
    def start_check(self):
        """开始检测"""
        if self.config is None:
            QMessageBox.warning(self, "警告", "请先加载配置文件")
            return
        
        # 检查必要配置
        if not self.config.paths.ccxml.exists():
            QMessageBox.warning(
                self,
                "配置错误",
                f"CCXML 文件不存在:\n{self.config.paths.ccxml}"
            )
            return
        
        if not self.config.paths.ccs_dss.exists():
            QMessageBox.warning(
                self,
                "配置错误",
                f"DSS 执行器不存在:\n{self.config.paths.ccs_dss}"
            )
            return
        
        # 设置检测中状态
        self.emulator_indicator.set_checking()
        self.target_indicator.set_checking()
        self.check_btn.setEnabled(False)
        self.result_text.clear()
        self.result_text.append("正在检测硬件连接...")
        
        # 创建并启动检测线程
        self.checker = HardwareChecker(self.config)
        self.checker.check_completed.connect(self.on_check_completed)
        self.checker.log_message.connect(self.on_log_message)
        self.checker.start()
    
    def on_check_completed(self, success: bool, message: str):
        """
        检测完成处理
        
        Args:
            success: 是否成功
            message: 结果消息
        """
        self.check_btn.setEnabled(True)
        
        if success:
            self.emulator_indicator.set_connected()
            self.target_indicator.set_connected()
        else:
            self.emulator_indicator.set_disconnected()
            self.target_indicator.set_disconnected()
        
        self.result_text.append(f"\n{'='*50}")
        self.result_text.append(f"检测结果: {'成功' if success else '失败'}")
        self.result_text.append(f"消息: {message}")
        
        self.check_completed.emit(success, message)
    
    def on_log_message(self, message: str):
        """
        日志消息处理
        
        Args:
            message: 日志消息
        """
        self.result_text.append(message)
