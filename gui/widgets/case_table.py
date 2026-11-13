#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用例表格组件

显示测试用例列表和执行状态；右键可打开 dat 目录或复制路径

@input 用例名称/状态/耗时/消息、dat 目录解析回调
@output 用例状态表与右键菜单操作
@pos “执行”页的用例列表，只读展示并支持目录快捷操作

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QBrush, QDesktopServices


class CaseTable(QTableWidget):
    """用例表格组件"""
    
    # 状态对应的显示文本和颜色
    STATUS_DISPLAY = {
        "pending": ("等待", "#808080"),  # 灰色
        "ready": ("就绪", "#00AA00"),  # 预扫描：已有 .out
        "missing_out": ("缺 .out", "#D97706"),  # 预扫描：有工程但没有 .out
        "running": ("运行中", "#FFA500"),  # 橙色
        "success": ("成功", "#00AA00"),  # 绿色
        "failed": ("失败", "#FF0000"),  # 红色
        "skipped": ("已跳过", "#808080"),  # 灰色
        "error": ("错误", "#FF0000"),  # 红色
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self.cases = {}  # 用例状态字典 {name: status}
        self.dat_dir_provider: Optional[Callable[[str], Optional[Path]]] = None
    
    def _setup_ui(self):
        """初始化界面"""
        # 设置列
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["用例名称", "状态", "耗时", "消息"])
        
        # 设置表头
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.setColumnWidth(1, 80)
        self.setColumnWidth(2, 80)
        
        # 设置选择模式
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # 设置交替行颜色
        self.setAlternatingRowColors(True)
    
    def clear_cases(self):
        """清空所有用例"""
        self.setRowCount(0)
        self.cases.clear()
    
    def add_case(self, name: str, status: str = "pending", duration: str = "--", message: str = ""):
        """
        添加用例
        
        Args:
            name: 用例名称
            status: 状态
            duration: 耗时
            message: 消息
        """
        row = self.rowCount()
        self.insertRow(row)
        
        # 用例名称
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        
        # 状态
        status_text, status_color = self.STATUS_DISPLAY.get(status, ("未知", "#808080"))
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setForeground(QBrush(QColor(status_color)))
        self.setItem(row, 1, status_item)
        
        # 耗时
        duration_item = QTableWidgetItem(duration)
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 2, duration_item)
        
        # 消息
        message_item = QTableWidgetItem(message)
        message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 3, message_item)
        
        # 保存用例状态
        self.cases[name] = {
            "row": row,
            "status": status,
            "duration": duration,
            "message": message
        }
    
    def update_case(self, name: str, status: str = None, duration: str = None, message: str = None):
        """
        更新用例状态
        
        Args:
            name: 用例名称
            status: 状态
            duration: 耗时
            message: 消息
        """
        if name not in self.cases:
            return
        
        case_info = self.cases[name]
        row = case_info["row"]
        
        # 更新状态
        if status is not None:
            status_text, status_color = self.STATUS_DISPLAY.get(status, ("未知", "#808080"))
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_item.setForeground(QBrush(QColor(status_color)))
            self.setItem(row, 1, status_item)
            case_info["status"] = status
        
        # 更新耗时
        if duration is not None:
            duration_item = QTableWidgetItem(duration)
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 2, duration_item)
            case_info["duration"] = duration
        
        # 更新消息
        if message is not None:
            message_item = QTableWidgetItem(message)
            message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 3, message_item)
            case_info["message"] = message
    
    def get_case_status(self, name: str) -> str:
        """获取用例状态"""
        if name in self.cases:
            return self.cases[name]["status"]
        return "unknown"
    
    def get_all_cases(self) -> list:
        """获取所有用例名称"""
        return list(self.cases.keys())
    
    def get_completed_count(self) -> int:
        """获取已完成用例数量"""
        completed_statuses = ["success", "failed", "error", "skipped"]
        return sum(1 for case in self.cases.values() if case["status"] in completed_statuses)
    
    def get_success_count(self) -> int:
        """获取成功用例数量"""
        return sum(1 for case in self.cases.values() if case["status"] == "success")
    
    def get_failed_count(self) -> int:
        """获取失败用例数量"""
        failed_statuses = ["failed", "error"]
        return sum(1 for case in self.cases.values() if case["status"] in failed_statuses)

    def get_skipped_count(self) -> int:
        """获取已跳过用例数量（未执行，不计入失败）"""
        return sum(1 for case in self.cases.values() if case["status"] == "skipped")

    # ========== 右键菜单：打开 dat 目录 / 复制路径 ==========

    def set_dat_dir_provider(self, provider: Callable[[str], Optional[Path]]):
        """注入“用例名 → dat 目录”的解析函数（由执行面板提供）"""
        self.dat_dir_provider = provider

    def _case_dat_dir(self, case_name: str) -> Optional[Path]:
        if self.dat_dir_provider is None:
            return None
        try:
            path = self.dat_dir_provider(case_name)
        except Exception:
            return None
        return Path(path) if path else None

    def open_case_dat_dir(self, case_name: str):
        """用资源管理器打开该用例的 dat 目录"""
        path = self._case_dat_dir(case_name)
        if path is None:
            QMessageBox.information(self, "提示", "尚未加载配置，无法定位 dat 目录")
            return
        if not path.is_dir():
            QMessageBox.information(
                self, "提示",
                f"该用例的 dat 目录还不存在：\n{path}\n\n请先执行该用例")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def copy_case_path(self, case_name: str):
        """复制该用例的 dat 目录路径"""
        path = self._case_dat_dir(case_name)
        if path is None:
            QMessageBox.information(self, "提示", "尚未加载配置，无法定位 dat 目录")
            return
        QApplication.clipboard().setText(str(path))

    def contextMenuEvent(self, event):
        """在用例行上右键：打开 dat 目录 / 复制路径"""
        row = self.rowAt(event.pos().y())
        if row < 0:
            return
        item = self.item(row, 0)
        if item is None:
            return

        case_name = item.text()
        menu = QMenu(self)
        open_action = menu.addAction("打开 dat 目录")
        copy_action = menu.addAction("复制路径")

        chosen = menu.exec_(event.globalPos())
        if chosen is open_action:
            self.open_case_dat_dir(case_name)
        elif chosen is copy_action:
            self.copy_case_path(case_name)
