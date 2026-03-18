#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置面板

用于编辑和显示配置信息
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QGroupBox, QScrollArea, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
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
        
        content_layout.addWidget(test_group)
        
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
        
        return True
    
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
            
            self.config_changed.emit()
