#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一消息框

@input 父窗口、标题、文案、按钮组合
@output critical()/warning()/information()/question()
@pos 所有 GUI 弹窗出口：在加载 Qt 翻译的基础上，显式把标准按钮改为中文
     （部分 PyQt 发行版缺少 qtbase_zh_CN.qm，只装 qt_zh_CN.qm 时按钮仍是 OK/Cancel）

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

from PyQt5.QtWidgets import QMessageBox

BUTTON_TEXTS = {
    QMessageBox.Ok: "确定",
    QMessageBox.Cancel: "取消",
    QMessageBox.Yes: "是",
    QMessageBox.No: "否",
    QMessageBox.Save: "保存",
    QMessageBox.Discard: "不保存",
    QMessageBox.Close: "关闭",
    QMessageBox.Retry: "重试",
    QMessageBox.Ignore: "忽略",
    QMessageBox.Abort: "中止",
}


def localize_buttons(box: QMessageBox) -> QMessageBox:
    """把已创建的标准按钮文字改成中文（找不到该按钮则跳过）"""
    for standard, text in BUTTON_TEXTS.items():
        button = box.button(standard)
        if button is not None:
            button.setText(text)
    return box


def critical(parent, title: str, text: str) -> int:
    box = QMessageBox(QMessageBox.Critical, title, text, QMessageBox.Ok, parent)
    return localize_buttons(box).exec_()


def warning(parent, title: str, text: str) -> int:
    box = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, parent)
    return localize_buttons(box).exec_()


def information(parent, title: str, text: str) -> int:
    box = QMessageBox(QMessageBox.Information, title, text, QMessageBox.Ok, parent)
    return localize_buttons(box).exec_()


def question(parent, title: str, text: str,
             buttons=QMessageBox.Yes | QMessageBox.No,
             default=QMessageBox.No) -> int:
    box = QMessageBox(QMessageBox.Question, title, text, buttons, parent)
    box.setDefaultButton(default)
    return localize_buttons(box).exec_()
