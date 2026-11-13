#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件检测面板

用于检测硬件连接状态；检测过程与结果同步写入日志页

@input Config
@output check_completed/log_entry 信号
@pos “硬件检测”标签页，负责仿真器/目标板连接检测与可读错误提示

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import html
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QTextEdit, QMessageBox, QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from .status_indicator import StatusIndicator
from ..utils.error_messages import format_error
from ..utils.message_boxes import warning
from ..workers.hardware_checker import HardwareChecker


# 硬件相关工具路径：配置键、界面名称、config.json 字段
TOOL_PATH_FIELDS = (
    ("ccxml", "CCXML 文件", "tools.ccxml"),
    ("ccs_executable", "CCS 可执行文件", "tools.ccs_executable"),
    ("ccs_dss", "DSS 执行器", "tools.ccs_dss"),
)


def collect_missing_tools(paths) -> list:
    """收集不存在的工具路径，返回 [(界面名称, 配置字段, 路径), ...]"""
    missing = []
    for attr, label, key in TOOL_PATH_FIELDS:
        value = getattr(paths, attr, None)
        if value is None or not Path(value).exists():
            missing.append((label, key, value))
    return missing


def format_missing_tools_message(missing) -> str:
    """把缺失的工具路径拼成“原因/路径/建议”三段式提示"""
    count = len(missing)
    detail = "\n".join(f"- {label}（{key}）：{value}" for label, key, value in missing)
    return "\n".join([
        f"原因：硬件检测所需的 {count} 个工具路径不存在",
        "路径：",
        detail,
        "建议：请在“配置”页把上述项改为本机实际路径，保存后重新检测"
        "（对应 config.json 的 " + " / ".join(key for _, key, _ in missing) + "）",
    ])


def is_key_line(message: str) -> bool:
    """判断一行检测输出是否为“关键行”（其余归入折叠的 GEL 原始输出）"""
    text = (message or "").strip()
    keywords = (
        "开始检测", "预检测", "CCXML", "设备名称", "CPU 名称",
        "硬件连接", "检测出错", "检测被取消", "检测完成", "检测超时",
        "错误", "FAILED", "SUCCESS",
    )
    return any(keyword in text for keyword in keywords)


class HardwarePanel(QWidget):
    """硬件检测面板"""
    
    check_completed = pyqtSignal(bool, str)  # 检测完成信号(成功/失败, 消息)
    log_entry = pyqtSignal(str, str)  # (消息, 级别)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config: Optional[Config] = None
        self.checker: Optional[HardwareChecker] = None
        self._config_available: bool = False
        self._no_config_reason: str = "尚未加载配置"
        
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
        
        # 检测结果文本框（只显示关键行）
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText('点击"开始检测"按钮检测硬件连接状态...')
        detail_layout.addWidget(self.result_text)

        # GEL 原始输出：默认折叠，需要排查时展开
        self.raw_toggle = QToolButton()
        self.raw_toggle.setCheckable(True)
        self.raw_toggle.setChecked(False)
        self.raw_toggle.setArrowType(Qt.RightArrow)
        self.raw_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.raw_toggle.setText("显示 GEL 原始输出")
        self.raw_toggle.setVisible(False)
        self.raw_toggle.toggled.connect(self._on_raw_toggled)
        detail_layout.addWidget(self.raw_toggle)

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setMaximumHeight(180)
        self.raw_text.setVisible(False)
        detail_layout.addWidget(self.raw_text)
        
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

        self._refresh_check_btn()
    
    def set_config(self, config: Config):
        """
        设置配置
        
        Args:
            config: 配置对象
        """
        self.config = config
        self._config_available = True
        self._refresh_check_btn()
        
        # 更新配置信息显示（路径做 HTML 转义，避免 & 等字符破坏显示）
        info_text = f"""
<b>CCXML 文件:</b> {html.escape(str(config.paths.ccxml))}<br>
<b>设备名称:</b> {html.escape(str(config.test.device))}<br>
<b>CPU 名称:</b> {html.escape(str(config.test.cpu))}<br>
<b>DSS 执行器:</b> {html.escape(str(config.paths.ccs_dss))}
        """.strip()
        self.config_info_label.setText(info_text)

    def set_config_available(self, available: bool, reason: str = ""):
        """配置是否可用：不可用时禁用“开始检测”并用 tooltip 说明原因"""
        self._config_available = bool(available)
        if reason:
            self._no_config_reason = reason
        self._refresh_check_btn()

    def _refresh_check_btn(self):
        """按配置可用性与检测状态刷新按钮"""
        checking = bool(self.checker and self.checker.isRunning())
        self.check_btn.setEnabled(self._config_available and not checking)
        self.check_btn.setToolTip("" if self._config_available else self._no_config_reason)
    
    def _mark_not_connected(self, message: str):
        """检测无法开始/失败：指示灯统一为“未连接”，并在详情里说明原因"""
        self.emulator_indicator.set_disconnected()
        self.target_indicator.set_disconnected()
        self.result_text.setPlainText(message)
        self._refresh_check_btn()

    def _on_raw_toggled(self, expanded: bool):
        """展开/折叠 GEL 原始输出"""
        self.raw_text.setVisible(expanded)
        self.raw_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.raw_toggle.setText("隐藏 GEL 原始输出" if expanded else "显示 GEL 原始输出")

    def start_check(self):
        """开始检测"""
        if self.config is None:
            message = format_error(
                "尚未加载配置",
                action="请先在“配置”页选择目录并保存，或通过“文件 → 打开配置...”加载")
            self.log_entry.emit(message.replace("\n", " | "), "WARNING")
            self._mark_not_connected(message)
            warning(self, "无法检测硬件", message)
            return

        self.log_entry.emit("开始检测硬件连接", "INFO")
        
        # 检查工具路径：一次性列出全部缺失项，直接告诉用户改哪几项
        missing = collect_missing_tools(self.config.paths)
        if missing:
            message = format_missing_tools_message(missing)
            self.log_entry.emit(message.replace("\n", " | "), "ERROR")
            self._mark_not_connected(message)
            warning(self, "无法检测硬件", message)
            return
        
        # 设置检测中状态
        self.emulator_indicator.set_checking()
        self.target_indicator.set_checking()
        self.check_btn.setEnabled(False)
        self.result_text.clear()
        self.raw_text.clear()
        self.raw_toggle.setChecked(False)
        self.raw_toggle.setVisible(False)
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
        self._refresh_check_btn()
        
        if success:
            self.emulator_indicator.set_connected()
            self.target_indicator.set_connected()
        else:
            self.emulator_indicator.set_disconnected()
            self.target_indicator.set_disconnected()
        
        self.result_text.append(f"\n{'='*50}")
        self.result_text.append(f"检测结果: {'成功' if success else '失败'}")
        self.result_text.append(f"消息: {message}")

        if success:
            self.log_entry.emit(f"硬件检测完成：{message}", "INFO")
        else:
            self.log_entry.emit(f"硬件检测失败：{message}", "ERROR")
        
        self.check_completed.emit(success, message)
    
    def on_log_message(self, message: str):
        """
        日志消息处理：关键行显示在详情区，其余收进折叠的 GEL 原始输出

        Args:
            message: 日志消息
        """
        self.raw_text.append(message)
        self.raw_toggle.setVisible(True)
        if is_key_line(message):
            self.result_text.append(message)
        level = "ERROR" if ("失败" in message or "错误" in message) else "INFO"
        self.log_entry.emit(message, level)
