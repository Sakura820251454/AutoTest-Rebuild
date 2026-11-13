#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可折叠分组框

用于配置页把体积大、改动少的配置收起，缩短页面滚动长度

@input 标题、默认展开状态
@output content/content_layout 供调用方填充子控件；expanded_changed 无（用按钮状态）
@pos 配置页“内存导出配置”“导出时间点配置”等高级分组的容器

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox, QToolButton, QVBoxLayout, QWidget
)


class CollapsibleGroupBox(QGroupBox):
    """带折叠按钮的分组框：点标题行展开/收起内容"""

    def __init__(self, title: str, expanded: bool = False, parent=None):
        super().__init__("", parent)

        self.title_text = title
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 8)
        outer.setSpacing(6)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 2px; }")
        self.toggle_button.toggled.connect(self._on_toggled)
        outer.addWidget(self.toggle_button, 0, Qt.AlignLeft)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        outer.addWidget(self.content)

        self.content.setVisible(expanded)
        self.setStyleSheet(
            "CollapsibleGroupBox { border: 1px solid #CCCCCC; border-radius: 4px; }")

    def _on_toggled(self, expanded: bool):
        self.content.setVisible(expanded)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()

    def set_expanded(self, expanded: bool):
        self.toggle_button.setChecked(expanded)
