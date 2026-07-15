#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
禁用滚轮的输入控件

防止鼠标滚轮意外修改数值
"""

from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QComboBox
from PyQt5.QtGui import QWheelEvent


class NoScrollSpinBox(QSpinBox):
    """禁用滚轮事件的SpinBox"""

    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改数值"""
        event.ignore()


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """禁用滚轮事件的DoubleSpinBox"""

    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改数值"""
        event.ignore()


class NoScrollComboBox(QComboBox):
    """禁用滚轮事件的ComboBox"""

    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改数值"""
        event.ignore()
