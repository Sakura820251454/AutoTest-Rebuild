#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关于对话框

@input gui/utils/build_info.py（名称/说明/版本/构建时间/提交/运行环境）
@output 模态对话框：标题 + 约 7 行信息 + 确定按钮
@pos “帮助 → 关于”，信息随打包时间与提交变化，不写更新日志

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..utils.build_info import APP_DESC, APP_NAME, VERSION, get_build_time, get_commit, runtime_lines


class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"关于 {APP_NAME}")
        self.setModal(True)

        self._setup_ui()

        # 宽固定、高按实际内容收缩（避免自动加高把窗口撑大）
        self.layout().activate()
        self.setFixedSize(460, self.heightForWidth(460))

    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 16, 20, 12)

        # 标题
        title_label = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 一句话说明
        desc_label = QLabel(APP_DESC)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #444444;")
        layout.addWidget(desc_label)

        # 版本 / 构建 / 提交 / 运行环境
        info_lines = [
            f"版本: {VERSION}",
            f"构建时间: {get_build_time()}",
            f"提交: {get_commit()}",
        ] + runtime_lines()
        info_label = QLabel("\n".join(info_lines))
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_label.setStyleSheet("color: #333333;")
        layout.addWidget(info_label)

        # 确定按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
