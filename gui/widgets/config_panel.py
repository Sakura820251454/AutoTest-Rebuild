#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置面板

用于编辑和显示配置信息
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton,
    QGroupBox, QScrollArea, QFrame, QMessageBox, QTableWidget, QTableWidgetItem,
    QCheckBox
)
from .no_scroll_spinbox import NoScrollSpinBox as QSpinBox, NoScrollComboBox as QComboBox
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config, ExportPoint, DEFAULT_EXPORT_POINTS
from .path_selector import PathSelector


class ConfigPanel(QWidget):
    """配置面板"""
    
    config_changed = pyqtSignal()  # 配置变更信号
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.config: Optional[Config] = None
        self.path_selectors: Dict[str, PathSelector] = {}
        self.build_inputs: Dict[str, Any] = {}
        self.test_inputs: Dict[str, Any] = {}

        # 内存段配置相关
        self.memory_table = None

        # 导出时间点配置相关
        self.export_when_combo = None

        # 结果判断配置相关
        self.result_method_combo = None
        self.breakpoint_group = None
        self.memory_group = None
        self.expression_group = None

        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll)
        
        # 滚动内容部件
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        scroll.setWidget(content_widget)
        
        # ===== 路径配置组 =====
        path_group = QGroupBox("路径配置")
        path_layout = QGridLayout(path_group)
        path_layout.setSpacing(10)
        
        # 路径配置项
        path_configs = [
            ("template_dir", "模板工程目录:", "dir"),
            ("source_dir", "源文件目录:", "dir"),
            ("generate_dir", "工程生成目录:", "dir"),
            ("result_dir", "结果输出目录:", "dir"),
            ("ccs_workspace", "CCS 工作区:", "dir"),
            ("ccs_executable", "CCS 可执行文件:", "file", "可执行文件 (*.exe);;所有文件 (*.*)"),
            ("ccs_dss", "DSS 执行器:", "file", "批处理文件 (*.bat);;所有文件 (*.*)"),
            ("ccxml", "CCXML 文件:", "file", "CCXML 文件 (*.ccxml);;所有文件 (*.*)"),
        ]
        
        for i, config in enumerate(path_configs):
            key, label, select_type = config[0], config[1], config[2]
            filter_str = config[3] if len(config) > 3 else ""
            
            path_layout.addWidget(QLabel(label), i, 0)
            
            selector = PathSelector(select_type, filter_str)
            selector.path_changed.connect(self.on_config_modified)
            path_layout.addWidget(selector, i, 1)
            self.path_selectors[key] = selector
        
        content_layout.addWidget(path_group)
        
        # ===== 构建设置组 =====
        build_group = QGroupBox("构建设置")
        build_layout = QGridLayout(build_group)
        build_layout.setSpacing(10)
        
        # 构建配置
        build_layout.addWidget(QLabel("构建配置:"), 0, 0)
        self.build_config_combo = QComboBox()
        self.build_config_combo.addItems(["Debug", "Release", "RAM_EABI", "RAM_COFF", "FLASH_EABI", "FLASH_COFF"])
        self.build_config_combo.setEditable(True)
        self.build_config_combo.currentTextChanged.connect(self.on_config_modified)
        build_layout.addWidget(self.build_config_combo, 0, 1)
        
        # 构建超时
        build_layout.addWidget(QLabel("构建超时(秒):"), 0, 2)
        self.build_timeout_spin = QSpinBox()
        self.build_timeout_spin.setRange(60, 3600)
        self.build_timeout_spin.setValue(600)
        self.build_timeout_spin.setSingleStep(60)
        self.build_timeout_spin.valueChanged.connect(self.on_config_modified)
        build_layout.addWidget(self.build_timeout_spin, 0, 3)
        
        # 最大线程数
        build_layout.addWidget(QLabel("最大线程数:"), 1, 0)
        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 16)
        self.max_threads_spin.setValue(4)
        self.max_threads_spin.valueChanged.connect(self.on_config_modified)
        build_layout.addWidget(self.max_threads_spin, 1, 1)

        # 工程生成模式
        build_layout.addWidget(QLabel("生成模式:"), 1, 2)
        self.generation_mode_combo = QComboBox()
        self.generation_mode_combo.addItems(["template", "manual"])
        self.generation_mode_combo.setToolTip("template: 从模板生成工程\nmanual: 使用手动配置的工程")
        self.generation_mode_combo.currentTextChanged.connect(self.on_config_modified)
        build_layout.addWidget(self.generation_mode_combo, 1, 3)

        build_layout.setColumnStretch(1, 1)
        build_layout.setColumnStretch(3, 1)

        self.build_inputs["build_config"] = self.build_config_combo
        self.build_inputs["build_timeout"] = self.build_timeout_spin
        self.build_inputs["max_build_threads"] = self.max_threads_spin
        self.build_inputs["generation_mode"] = self.generation_mode_combo
        
        content_layout.addWidget(build_group)
        
        # ===== 测试设置组 =====
        test_group = QGroupBox("测试设置")
        test_layout = QGridLayout(test_group)
        test_layout.setSpacing(10)
        
        # 测试超时
        test_layout.addWidget(QLabel("测试超时(毫秒):"), 0, 0)
        self.test_timeout_spin = QSpinBox()
        self.test_timeout_spin.setRange(1000, 300000)
        self.test_timeout_spin.setValue(45000)
        self.test_timeout_spin.setSingleStep(1000)
        self.test_timeout_spin.valueChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.test_timeout_spin, 0, 1)
        
        # 批次大小
        test_layout.addWidget(QLabel("批次大小:"), 0, 2)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)
        self.batch_size_spin.setValue(10)
        self.batch_size_spin.valueChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.batch_size_spin, 0, 3)

        # 自动重连
        self.auto_resume_check = QCheckBox("断连自动重连")
        self.auto_resume_check.setChecked(True)
        self.auto_resume_check.setToolTip("硬件断连后自动等待并重连，无需手动干预")
        self.auto_resume_check.stateChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.auto_resume_check, 3, 0)

        # 最大重试次数
        test_layout.addWidget(QLabel("最大重试次数:"), 3, 2)
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 100)
        self.max_retries_spin.setValue(5)
        self.max_retries_spin.setSpecialValueText("不限制")
        self.max_retries_spin.setToolTip("0 表示不限制重试次数，直到手动停止")
        self.max_retries_spin.valueChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.max_retries_spin, 3, 3)

        # 重试间隔
        test_layout.addWidget(QLabel("重试间隔(秒):"), 4, 0)
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 300)
        self.retry_delay_spin.setValue(10)
        self.retry_delay_spin.valueChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.retry_delay_spin, 4, 1)
        
        # 设备名称
        test_layout.addWidget(QLabel("设备名称:"), 1, 0)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("Texas Instruments XDS100v3 USB Debug Probe_0")
        self.device_edit.textChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.device_edit, 1, 1, 1, 3)
        
        # CPU 名称
        test_layout.addWidget(QLabel("CPU 名称:"), 2, 0)
        self.cpu_edit = QLineEdit()
        self.cpu_edit.setPlaceholderText("C28xx_CPU1")
        self.cpu_edit.textChanged.connect(self.on_config_modified)
        test_layout.addWidget(self.cpu_edit, 2, 1, 1, 3)
        
        test_layout.setColumnStretch(1, 1)
        test_layout.setColumnStretch(3, 1)
        
        self.test_inputs["test_timeout"] = self.test_timeout_spin
        self.test_inputs["test_batch_size"] = self.batch_size_spin
        self.test_inputs["device"] = self.device_edit
        self.test_inputs["cpu"] = self.cpu_edit
        self.test_inputs["auto_resume"] = self.auto_resume_check
        self.test_inputs["max_retries"] = self.max_retries_spin
        self.test_inputs["retry_delay"] = self.retry_delay_spin
        
        content_layout.addWidget(test_group)
        
        # ===== 内存段配置组 =====
        memory_group = QGroupBox("内存导出配置")
        memory_layout = QVBoxLayout(memory_group)
        memory_layout.setSpacing(10)
        
        # 内存段表格
        self.memory_table = QTableWidget()
        self.memory_table.setColumnCount(5)
        self.memory_table.setHorizontalHeaderLabels(["名称", "起始地址", "长度", "格式ID", "Page"])
        self.memory_table.setColumnWidth(0, 100)
        self.memory_table.setColumnWidth(1, 120)
        self.memory_table.setColumnWidth(2, 100)
        self.memory_table.setColumnWidth(3, 80)
        self.memory_table.setColumnWidth(4, 60)
        self.memory_table.setMinimumHeight(300)
        self.memory_table.itemChanged.connect(self.on_config_modified)
        memory_layout.addWidget(self.memory_table)
        
        # 按钮布局
        memory_button_layout = QHBoxLayout()
        
        self.add_memory_btn = QPushButton("添加内存段")
        self.add_memory_btn.clicked.connect(self.on_add_memory_segment)
        memory_button_layout.addWidget(self.add_memory_btn)
        
        self.remove_memory_btn = QPushButton("删除选中内存段")
        self.remove_memory_btn.clicked.connect(self.on_remove_memory_segment)
        memory_button_layout.addWidget(self.remove_memory_btn)
        
        memory_button_layout.addStretch()
        memory_layout.addLayout(memory_button_layout)
        
        # 说明标签
        info_label = QLabel("说明：")
        info_label.setStyleSheet("font-weight: bold;")
        memory_layout.addWidget(info_label)
        
        info_text = QLabel("- 名称：内存段名称，用于生成导出文件名")
        info_text.setWordWrap(True)
        memory_layout.addWidget(info_text)
        
        info_text2 = QLabel("- 起始地址：十六进制格式（如：0xA810）")
        info_text2.setWordWrap(True)
        memory_layout.addWidget(info_text2)
        
        info_text3 = QLabel("- 长度：十六进制格式（如：0x960）")
        info_text3.setWordWrap(True)
        memory_layout.addWidget(info_text3)
        
        info_text4 = QLabel("- 格式ID：导出数据格式，常用值：")
        info_text4.setWordWrap(True)
        memory_layout.addWidget(info_text4)

        format_info = QLabel("  7=16位TI十六进制, 8=16位C十六进制, 15=8位无符号整数, 0=32位TI十六进制, 21=TI64bit")
        format_info.setWordWrap(True)
        format_info.setStyleSheet("color: #666;")
        memory_layout.addWidget(format_info)

        info_text5 = QLabel("- Page：内存页，0=程序空间(PAGE 0)，1=数据空间(PAGE 1)")
        info_text5.setWordWrap(True)
        memory_layout.addWidget(info_text5)

        content_layout.addWidget(memory_group)

        # ===== 导出时间点配置组 =====
        export_group = QGroupBox("导出时间点配置")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(10)

        # 导出时间点选择
        export_select_layout = QHBoxLayout()
        export_select_layout.addWidget(QLabel("内存导出时机:"))

        self.export_when_combo = QComboBox()
        self.export_when_combo.addItems(["after_load", "before_run", "after_run"])
        self.export_when_combo.setCurrentText("after_run")
        self.export_when_combo.setToolTip("选择在哪个时间点导出内存数据")
        self.export_when_combo.currentTextChanged.connect(self.on_config_modified)
        export_select_layout.addWidget(self.export_when_combo)

        export_select_layout.addStretch()
        export_layout.addLayout(export_select_layout)

        # 导出时间点说明
        export_info_label = QLabel("导出时间点说明：")
        export_info_label.setStyleSheet("font-weight: bold;")
        export_layout.addWidget(export_info_label)

        export_desc1 = QLabel("- after_load：程序烧录到板子后立即导出，用于验证初始值")
        export_desc1.setWordWrap(True)
        export_layout.addWidget(export_desc1)

        export_desc2 = QLabel("- before_run：程序运行前导出，用于检查预设数据")
        export_desc2.setWordWrap(True)
        export_layout.addWidget(export_desc2)

        export_desc3 = QLabel("- after_run：程序运行完成后导出，用于检查最终结果（默认）")
        export_desc3.setWordWrap(True)
        export_layout.addWidget(export_desc3)

        content_layout.addWidget(export_group)

        # ===== 结果判断配置组 =====
        result_group = QGroupBox("结果判断配置")
        result_layout = QVBoxLayout(result_group)
        result_layout.setSpacing(10)

        # 判断方式选择
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("判断方式:"))

        self.result_method_combo = QComboBox()
        self.result_method_combo.addItems(["breakpoint", "memory", "expression"])
        self.result_method_combo.setCurrentText("breakpoint")
        self.result_method_combo.setToolTip("选择如何判断测试结果")
        self.result_method_combo.currentTextChanged.connect(self.on_result_method_changed)
        method_layout.addWidget(self.result_method_combo)

        method_layout.addStretch()
        result_layout.addLayout(method_layout)

        # 断点方式参数（默认显示）
        self.breakpoint_group = QGroupBox("断点方式参数")
        breakpoint_layout = QGridLayout(self.breakpoint_group)

        breakpoint_layout.addWidget(QLabel("成功标签:"), 0, 0)
        self.success_label_edit = QLineEdit("Right")
        self.success_label_edit.setToolTip("程序停在此标签时判定为成功")
        self.success_label_edit.textChanged.connect(self.on_config_modified)
        breakpoint_layout.addWidget(self.success_label_edit, 0, 1)

        breakpoint_layout.addWidget(QLabel("失败标签:"), 1, 0)
        self.fail_label_edit = QLineEdit("IDLE")
        self.fail_label_edit.setToolTip("程序停在此标签时判定为失败")
        self.fail_label_edit.textChanged.connect(self.on_config_modified)
        breakpoint_layout.addWidget(self.fail_label_edit, 1, 1)

        breakpoint_layout.setColumnStretch(1, 1)
        result_layout.addWidget(self.breakpoint_group)

        # 内存值方式参数
        self.memory_group = QGroupBox("内存值方式参数")
        memory_check_layout = QGridLayout(self.memory_group)

        memory_check_layout.addWidget(QLabel("检查地址:"), 0, 0)
        self.check_addr_edit = QLineEdit()
        self.check_addr_edit.setPlaceholderText("0x7625")
        self.check_addr_edit.setToolTip("要检查的内存地址")
        self.check_addr_edit.textChanged.connect(self.on_config_modified)
        memory_check_layout.addWidget(self.check_addr_edit, 0, 1)

        memory_check_layout.addWidget(QLabel("读取宽度:"), 1, 0)
        self.check_width_combo = QComboBox()
        self.check_width_combo.addItems(["32", "16"])
        self.check_width_combo.setToolTip("内存读取宽度：16位或32位")
        self.check_width_combo.currentTextChanged.connect(self.on_config_modified)
        memory_check_layout.addWidget(self.check_width_combo, 1, 1)

        memory_check_layout.addWidget(QLabel("成功值:"), 2, 0)
        self.success_val_edit = QLineEdit()
        self.success_val_edit.setPlaceholderText("0xCCCC")
        self.success_val_edit.setToolTip("内存值等于此值时判定为成功")
        self.success_val_edit.textChanged.connect(self.on_config_modified)
        memory_check_layout.addWidget(self.success_val_edit, 2, 1)

        memory_check_layout.addWidget(QLabel("失败值:"), 3, 0)
        self.fail_val_edit = QLineEdit()
        self.fail_val_edit.setPlaceholderText("0xEEEE")
        self.fail_val_edit.setToolTip("内存值等于此值时判定为失败")
        self.fail_val_edit.textChanged.connect(self.on_config_modified)
        memory_check_layout.addWidget(self.fail_val_edit, 3, 1)

        memory_check_layout.setColumnStretch(1, 1)
        self.memory_group.setVisible(False)
        result_layout.addWidget(self.memory_group)

        # 表达式方式参数
        self.expression_group = QGroupBox("表达式方式参数")
        expression_layout = QGridLayout(self.expression_group)

        expression_layout.addWidget(QLabel("表达式:"), 0, 0)
        self.expression_edit = QLineEdit()
        self.expression_edit.setPlaceholderText("$PC")
        self.expression_edit.setToolTip("要评估的表达式")
        self.expression_edit.textChanged.connect(self.on_config_modified)
        expression_layout.addWidget(self.expression_edit, 0, 1)

        expression_layout.addWidget(QLabel("期望值:"), 1, 0)
        self.expected_val_edit = QLineEdit()
        self.expected_val_edit.setPlaceholderText("0x3fb8b9")
        self.expected_val_edit.setToolTip("表达式结果等于此值时判定为成功")
        self.expected_val_edit.textChanged.connect(self.on_config_modified)
        expression_layout.addWidget(self.expected_val_edit, 1, 1)

        expression_layout.setColumnStretch(1, 1)
        self.expression_group.setVisible(False)
        result_layout.addWidget(self.expression_group)

        # 结果判断说明
        result_info_label = QLabel("判断方式说明：")
        result_info_label.setStyleSheet("font-weight: bold;")
        result_layout.addWidget(result_info_label)

        result_desc1 = QLabel("- breakpoint：通过检查程序停在哪个断点来判断结果（默认）")
        result_desc1.setWordWrap(True)
        result_layout.addWidget(result_desc1)

        result_desc2 = QLabel("- memory：通过读取指定内存地址的值来判断结果")
        result_desc2.setWordWrap(True)
        result_layout.addWidget(result_desc2)

        result_desc3 = QLabel("- expression：通过评估表达式的结果来判断")
        result_desc3.setWordWrap(True)
        result_layout.addWidget(result_desc3)

        content_layout.addWidget(result_group)

        # 添加弹性空间
        content_layout.addStretch()
        
        # ===== 按钮区域 =====
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.load_btn = QPushButton("加载配置")
        self.load_btn.clicked.connect(self.on_load_config)
        button_layout.addWidget(self.load_btn)
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.on_save_config)
        button_layout.addWidget(self.save_btn)
        
        self.default_btn = QPushButton("恢复默认")
        self.default_btn.clicked.connect(self.on_restore_default)
        button_layout.addWidget(self.default_btn)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
    
    def load_config(self, config: Config):
        """
        加载配置到界面
        
        Args:
            config: 配置对象
        """
        self.config = config
        
        # 加载路径配置
        self.path_selectors["template_dir"].set_path(str(config.paths.template_dir))
        self.path_selectors["source_dir"].set_path(str(config.paths.source_dir))
        self.path_selectors["generate_dir"].set_path(str(config.paths.generate_dir))
        self.path_selectors["result_dir"].set_path(str(config.paths.result_dir))
        self.path_selectors["ccs_workspace"].set_path(str(config.paths.ccs_workspace))
        self.path_selectors["ccs_executable"].set_path(str(config.paths.ccs_executable))
        self.path_selectors["ccs_dss"].set_path(str(config.paths.ccs_dss))
        self.path_selectors["ccxml"].set_path(str(config.paths.ccxml))
        
        # 加载构建设置
        self.build_config_combo.setCurrentText(config.build.build_config)
        self.build_timeout_spin.setValue(config.build.build_timeout)
        self.max_threads_spin.setValue(config.build.max_build_threads)

        # 加载工程生成模式
        generation_mode = config._raw.get("generation", {}).get("generation_mode", "template")
        self.generation_mode_combo.setCurrentText(generation_mode)
        
        # 加载测试设置
        self.test_timeout_spin.setValue(config.test.test_timeout)
        self.batch_size_spin.setValue(config.test.test_batch_size)
        self.device_edit.setText(config.test.device)
        self.cpu_edit.setText(config.test.cpu)
        self.auto_resume_check.setChecked(config.test.auto_resume)
        self.max_retries_spin.setValue(config.test.max_retries)
        self.retry_delay_spin.setValue(config.test.retry_delay)

        # 加载结果判断配置
        result_check = config.result_check
        self.result_method_combo.setCurrentText(result_check.method)
        self.success_label_edit.setText(result_check.success_label)
        self.fail_label_edit.setText(result_check.fail_label)
        self.check_addr_edit.setText(result_check.check_addr)
        self.check_width_combo.setCurrentText(str(result_check.check_width))
        self.success_val_edit.setText(result_check.success_val)
        self.fail_val_edit.setText(result_check.fail_val)
        self.expression_edit.setText(result_check.expression)
        self.expected_val_edit.setText(result_check.expected_val)

        # 加载内存段配置
        self.memory_table.setRowCount(0)
        for segment in config.memory_segments:
            row = self.memory_table.rowCount()
            self.memory_table.insertRow(row)

            # 名称
            name_item = QTableWidgetItem(segment.name)
            name_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.memory_table.setItem(row, 0, name_item)

            # 起始地址
            addr_item = QTableWidgetItem(segment.addr)
            addr_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.memory_table.setItem(row, 1, addr_item)

            # 长度
            len_item = QTableWidgetItem(segment.len)
            len_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.memory_table.setItem(row, 2, len_item)

            # 位宽
            width_item = QTableWidgetItem(str(segment.width))
            width_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.memory_table.setItem(row, 3, width_item)

            # Page
            page_item = QTableWidgetItem(str(segment.page))
            page_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.memory_table.setItem(row, 4, page_item)

        # 加载导出时间点配置
        export_points = config.export_points if config.export_points else DEFAULT_EXPORT_POINTS
        if export_points:
            self.export_when_combo.setCurrentText(export_points[0].when)

    def get_config_dict(self) -> Dict[str, Any]:
        """
        从界面获取配置字典
        
        Returns:
            配置字典
        """
        config_dict = {
            # 路径配置
            "template_dir": self.path_selectors["template_dir"].get_path(),
            "source_dir": self.path_selectors["source_dir"].get_path(),
            "generate_dir": self.path_selectors["generate_dir"].get_path(),
            "result_dir": self.path_selectors["result_dir"].get_path(),
            "ccs_workspace": self.path_selectors["ccs_workspace"].get_path(),
            "ccs_executable": self.path_selectors["ccs_executable"].get_path(),
            "ccs_dss": self.path_selectors["ccs_dss"].get_path(),
            "ccxml": self.path_selectors["ccxml"].get_path(),
            
            # 构建设置
            "build_config": self.build_config_combo.currentText(),
            "build_timeout": self.build_timeout_spin.value(),
            "max_build_threads": self.max_threads_spin.value(),

            # 工程生成模式
            "generation": {
                "generation_mode": self.generation_mode_combo.currentText()
            },

            # 测试设置
            "timeout": self.test_timeout_spin.value(),
            "test_batch_size": self.batch_size_spin.value(),
            "device": self.device_edit.text(),
            "cpu": self.cpu_edit.text(),
            "auto_resume": self.auto_resume_check.isChecked(),
            "max_retries": self.max_retries_spin.value(),
            "retry_delay": self.retry_delay_spin.value(),
            
            # 内存段配置
            "memory_segments": {
                "segments": [],
                "export_points": []
            }
        }

        # 收集内存段配置
        for row in range(self.memory_table.rowCount()):
            name_item = self.memory_table.item(row, 0)
            addr_item = self.memory_table.item(row, 1)
            len_item = self.memory_table.item(row, 2)
            width_item = self.memory_table.item(row, 3)
            page_item = self.memory_table.item(row, 4)

            if name_item and addr_item and len_item and width_item:
                segment = {
                    "name": name_item.text(),
                    "addr": addr_item.text(),
                    "len": len_item.text(),
                    "width": int(width_item.text()),
                    "page": int(page_item.text()) if page_item else 0
                }
                config_dict["memory_segments"]["segments"].append(segment)

        # 收集导出时间点配置
        when = self.export_when_combo.currentText()
        config_dict["memory_segments"]["export_points"] = [
            {"when": when, "enabled": True, "subdir": "Memory"}
        ]

        # 收集结果判断配置
        config_dict["result_check"] = {
            "method": self.result_method_combo.currentText(),
            "success_label": self.success_label_edit.text(),
            "fail_label": self.fail_label_edit.text(),
            "check_addr": self.check_addr_edit.text(),
            "check_width": int(self.check_width_combo.currentText()),
            "success_val": self.success_val_edit.text(),
            "fail_val": self.fail_val_edit.text(),
            "expression": self.expression_edit.text(),
            "expected_val": self.expected_val_edit.text()
        }

        return config_dict
    
    def validate(self) -> bool:
        """
        验证配置输入
        
        Returns:
            是否验证通过
        """
        config_dict = self.get_config_dict()
        
        # 检查必填路径
        required_paths = [
            ("generate_dir", "工程生成目录"),
            ("ccs_executable", "CCS 可执行文件"),
            ("ccs_dss", "DSS 执行器"),
        ]
        
        for key, name in required_paths:
            if not config_dict.get(key):
                QMessageBox.warning(self, "验证失败", f"请填写 {name}")
                return False
        
        # 验证内存段配置
        memory_segments = config_dict.get("memory_segments", {}).get("segments", [])
        for i, segment in enumerate(memory_segments):
            # 验证名称
            if not segment.get("name"):
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 缺少名称")
                return False
            
            # 验证地址格式（十六进制）
            addr = segment.get("addr", "")
            if not addr.startswith("0x"):
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的起始地址格式错误，应为十六进制格式（如：0x0000）")
                return False
            try:
                int(addr, 16)
            except ValueError:
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的起始地址不是有效的十六进制值")
                return False
            
            # 验证长度格式（十六进制）
            length = segment.get("len", "")
            if not length.startswith("0x"):
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的长度格式错误，应为十六进制格式（如：0x200）")
                return False
            try:
                int(length, 16)
            except ValueError:
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的长度不是有效的十六进制值")
                return False
            
            # 验证格式ID
            width = segment.get("width", 0)
            if not isinstance(width, int) or width < 0:
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的格式ID必须是非负整数")
                return False

            # 验证Page
            page = segment.get("page", 0)
            if not isinstance(page, int) or page not in (0, 1):
                QMessageBox.warning(self, "验证失败", f"内存段 {i+1} 的Page必须是0或1")
                return False

        return True

    def on_result_method_changed(self, method: str):
        """判断方式改变处理"""
        # 隐藏所有参数组
        self.breakpoint_group.setVisible(False)
        self.memory_group.setVisible(False)
        self.expression_group.setVisible(False)

        # 显示对应的参数组
        if method == "breakpoint":
            self.breakpoint_group.setVisible(True)
        elif method == "memory":
            self.memory_group.setVisible(True)
        elif method == "expression":
            self.expression_group.setVisible(True)

        self.config_changed.emit()

    def on_config_modified(self):
        """配置修改处理"""
        self.config_changed.emit()
    
    def on_load_config(self):
        """加载配置按钮处理"""
        # 获取主窗口实例并调用打开配置方法
        from PyQt5.QtWidgets import QFileDialog
        
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开配置文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if path:
            # 获取主窗口并调用加载配置
            main_window = self.window()
            if hasattr(main_window, 'load_config'):
                main_window.load_config(path)
    
    def on_save_config(self):
        """保存配置按钮处理"""
        if not self.validate():
            return
        
        # 获取主窗口实例并调用保存配置方法
        main_window = self.window()
        if hasattr(main_window, 'save_config'):
            main_window.save_config()
    
    def on_add_memory_segment(self):
        """添加内存段"""
        row = self.memory_table.rowCount()
        self.memory_table.insertRow(row)

        # 默认值
        name_item = QTableWidgetItem(f"Segment{row+1}")
        name_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.memory_table.setItem(row, 0, name_item)

        addr_item = QTableWidgetItem("0x0000")
        addr_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.memory_table.setItem(row, 1, addr_item)

        len_item = QTableWidgetItem("0x200")
        len_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.memory_table.setItem(row, 2, len_item)

        width_item = QTableWidgetItem("15")
        width_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.memory_table.setItem(row, 3, width_item)

        page_item = QTableWidgetItem("0")
        page_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.memory_table.setItem(row, 4, page_item)

        self.config_changed.emit()
    
    def on_remove_memory_segment(self):
        """删除选中内存段"""
        selected_rows = set()
        for item in self.memory_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先选择要删除的内存段")
            return

        # 从后往前删除，避免索引混乱
        for row in sorted(selected_rows, reverse=True):
            self.memory_table.removeRow(row)

        self.config_changed.emit()

    def on_restore_default(self):
        """恢复默认配置"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要恢复默认配置吗？当前配置将丢失。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清空所有输入
            for selector in self.path_selectors.values():
                selector.set_path("")
            
            self.build_config_combo.setCurrentIndex(0)
            self.build_timeout_spin.setValue(600)
            self.max_threads_spin.setValue(4)
            self.generation_mode_combo.setCurrentText("template")
            self.test_timeout_spin.setValue(45000)
            self.batch_size_spin.setValue(10)
            self.device_edit.clear()
            self.cpu_edit.clear()
            
            # 恢复默认内存段配置
            self.memory_table.setRowCount(0)
            default_segments = [
                {"name": "M0", "addr": "0x0000", "len": "0x200", "width": 15},
                {"name": "M1", "addr": "0x0400", "len": "0x200", "width": 15},
                {"name": "LS0", "addr": "0x8000", "len": "0x400", "width": 15},
                {"name": "LS1", "addr": "0x8800", "len": "0x400", "width": 15},
                {"name": "LS2", "addr": "0x9000", "len": "0x400", "width": 15},
                {"name": "LS3", "addr": "0x9800", "len": "0x400", "width": 15},
                {"name": "LS4", "addr": "0xa000", "len": "0x400", "width": 15},
                {"name": "LS5", "addr": "0xa800", "len": "0x400", "width": 15},
                {"name": "LS6", "addr": "0xb000", "len": "0x400", "width": 15},
                {"name": "LS7", "addr": "0xb800", "len": "0x400", "width": 15},
                {"name": "GS0", "addr": "0xc000", "len": "0x800", "width": 15},
                {"name": "GS1", "addr": "0xd000", "len": "0x800", "width": 15},
                {"name": "GS2", "addr": "0xe000", "len": "0x800", "width": 15},
                {"name": "GS3", "addr": "0xf000", "len": "0x800", "width": 15}
            ]
            
            for segment in default_segments:
                row = self.memory_table.rowCount()
                self.memory_table.insertRow(row)

                name_item = QTableWidgetItem(segment["name"])
                name_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.memory_table.setItem(row, 0, name_item)

                addr_item = QTableWidgetItem(segment["addr"])
                addr_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.memory_table.setItem(row, 1, addr_item)

                len_item = QTableWidgetItem(segment["len"])
                len_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.memory_table.setItem(row, 2, len_item)

                width_item = QTableWidgetItem(str(segment["width"]))
                width_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.memory_table.setItem(row, 3, width_item)

                page_item = QTableWidgetItem("0")
                page_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.memory_table.setItem(row, 4, page_item)

            # 恢复默认导出时间点配置
            self.export_when_combo.setCurrentText("after_run")

            # 恢复默认结果判断配置
            self.result_method_combo.setCurrentText("breakpoint")
            self.success_label_edit.setText("Right")
            self.fail_label_edit.setText("IDLE")
            self.check_addr_edit.clear()
            self.check_width_combo.setCurrentText("32")
            self.success_val_edit.clear()
            self.fail_val_edit.clear()
            self.expression_edit.clear()
            self.expected_val_edit.clear()

            self.config_changed.emit()
