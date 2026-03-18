#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoTest GUI 主窗口

@input Config (配置对象)
@input ConfigPanel, HardwarePanel, ExecutePanel, LogPanel (子面板)
@output MainWindow类
@pos GUI核心入口，整合所有面板和菜单，提供图形化配置管理、硬件检测和测试执行

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
import os
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QLabel, QPushButton,
    QFileDialog, QMessageBox, QApplication, QMenuBar, QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from .widgets.config_panel import ConfigPanel
from .widgets.hardware_panel import HardwarePanel
from .widgets.execute_panel import ExecutePanel
from .widgets.log_panel import LogPanel
from .dialogs.about_dialog import AboutDialog


class MainWindow(QMainWindow):
    """AutoTest GUI 主窗口"""
    
    # 信号定义
    config_loaded = pyqtSignal(object)  # 配置加载完成信号
    stage_detected = pyqtSignal(str, str)  # 阶段检测完成信号(阶段, 描述)
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        
        self.config: Optional[Config] = None
        self.current_stage: str = "unknown"
        self.stage_description: str = ""
        self.config_path: Optional[str] = config_path
        
        self.setWindowTitle("AutoTest GUI - TI C2000 DSP 自动化测试")
        self.setMinimumSize(1000, 700)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._connect_signals()
        
        # 如果指定了配置文件，自动加载
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
    
    def _setup_ui(self):
        """初始化界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 配置面板
        self.config_panel = ConfigPanel()
        self.tab_widget.addTab(self.config_panel, "配置")
        
        # 硬件检测面板
        self.hardware_panel = HardwarePanel()
        self.tab_widget.addTab(self.hardware_panel, "硬件检测")
        
        # 执行面板
        self.execute_panel = ExecutePanel()
        self.tab_widget.addTab(self.execute_panel, "执行")
        
        # 日志面板
        self.log_panel = LogPanel()
        self.tab_widget.addTab(self.log_panel, "日志")
    
    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        # 打开配置
        open_action = QAction("打开配置...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open_config)
        file_menu.addAction(open_action)
        
        # 保存配置
        save_action = QAction("保存配置", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.on_save_config)
        file_menu.addAction(save_action)
        
        # 另存为
        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.on_save_config_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        # 刷新项目状态
        refresh_action = QAction("刷新项目状态", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.on_refresh_project)
        tools_menu.addAction(refresh_action)
        
        tools_menu.addSeparator()
        
        # 检测硬件
        check_hw_action = QAction("检测硬件连接", self)
        check_hw_action.triggered.connect(self.on_check_hardware)
        tools_menu.addAction(check_hw_action)
        
        # 检测阶段
        detect_stage_action = QAction("检测当前阶段", self)
        detect_stage_action.triggered.connect(self.on_detect_stage)
        tools_menu.addAction(detect_stage_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)
    
    def _setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 硬件状态标签
        self.hw_status_label = QLabel("硬件: 未检测")
        self.status_bar.addWidget(self.hw_status_label)
        
        # 分隔线
        self.status_bar.addWidget(QLabel(" | "))
        
        # 当前阶段标签
        self.stage_label = QLabel("阶段: 未知")
        self.status_bar.addWidget(self.stage_label)
        
        # 分隔线
        self.status_bar.addWidget(QLabel(" | "))
        
        # 就绪状态
        self.ready_label = QLabel("就绪")
        self.status_bar.addPermanentWidget(self.ready_label)
    
    def _connect_signals(self):
        """连接信号"""
        # 配置面板信号
        self.config_panel.config_changed.connect(self.on_config_changed)
        
        # 硬件检测面板信号
        self.hardware_panel.check_completed.connect(self.on_hardware_check_completed)
        
        # 执行面板信号
        self.execute_panel.execution_started.connect(self.on_execution_started)
        self.execute_panel.execution_finished.connect(self.on_execution_finished)
        self.execute_panel.log_message.connect(self.on_log_message)
        
        # 阶段检测信号
        self.stage_detected.connect(self.on_stage_detected)
    
    def load_config(self, path: str):
        """
        加载配置文件
        
        Args:
            path: 配置文件路径
        """
        try:
            self.config = Config.load(path)
            self.config_path = path
            
            # 更新配置面板
            self.config_panel.load_config(self.config)
            
            # 更新硬件检测面板
            self.hardware_panel.set_config(self.config)
            
            # 更新执行面板
            self.execute_panel.set_config(self.config)
            
            # 发送信号
            self.config_loaded.emit(self.config)
            
            # 更新状态栏
            self.set_status(f"配置已加载: {path}")
            
            # 自动检测阶段
            self.on_detect_stage()
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载配置文件失败:\n{str(e)}")
            return False
    
    def save_config(self, path: Optional[str] = None) -> bool:
        """
        保存配置文件
        
        Args:
            path: 保存路径，None 表示使用当前路径
        
        Returns:
            是否保存成功
        """
        if self.config is None:
            QMessageBox.warning(self, "警告", "没有可保存的配置")
            return False
        
        try:
            # 从面板获取最新配置值
            config_dict = self.config_panel.get_config_dict()
            
            # 更新配置对象的各个属性
            self._update_config_from_dict(config_dict)
            
            # 确定保存路径
            save_path = path or self.config_path
            if save_path is None:
                return self.on_save_config_as()
            
            # 保存（使用新的保存方法，保留格式和注释）
            self.config.save(save_path)
            self.config_path = save_path
            
            self.set_status(f"配置已保存: {save_path}")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置文件失败:\n{str(e)}")
            return False
    
    def _update_config_from_dict(self, config_dict: dict):
        """从字典更新配置对象的属性"""
        from pathlib import Path
        
        # 更新路径配置
        if config_dict.get("template_dir"):
            self.config.paths.template_dir = Path(config_dict["template_dir"])
        if config_dict.get("source_dir"):
            self.config.paths.source_dir = Path(config_dict["source_dir"])
        if config_dict.get("generate_dir"):
            self.config.paths.generate_dir = Path(config_dict["generate_dir"])
        if config_dict.get("result_dir"):
            self.config.paths.result_dir = Path(config_dict["result_dir"])
        if config_dict.get("ccs_workspace"):
            self.config.paths.ccs_workspace = Path(config_dict["ccs_workspace"])
        if config_dict.get("ccs_executable"):
            self.config.paths.ccs_executable = Path(config_dict["ccs_executable"])
        if config_dict.get("ccs_dss"):
            self.config.paths.ccs_dss = Path(config_dict["ccs_dss"])
        if config_dict.get("ccxml"):
            self.config.paths.ccxml = Path(config_dict["ccxml"])
        
        # 更新构建设置
        if config_dict.get("build_config"):
            self.config.build.build_config = config_dict["build_config"]
        if config_dict.get("build_timeout"):
            self.config.build.build_timeout = config_dict["build_timeout"]
        if config_dict.get("max_build_threads"):
            self.config.build.max_build_threads = config_dict["max_build_threads"]
        
        # 更新生成模式到 _raw
        if "generation" in config_dict and config_dict["generation"]:
            if "generation_mode" in config_dict["generation"]:
                if "generation" not in self.config._raw:
                    self.config._raw["generation"] = {}
                self.config._raw["generation"]["generation_mode"] = config_dict["generation"]["generation_mode"]
        
        # 更新测试设置
        if config_dict.get("timeout"):
            self.config.test.test_timeout = config_dict["timeout"]
        if config_dict.get("test_batch_size"):
            self.config.test.test_batch_size = config_dict["test_batch_size"]
        if config_dict.get("device"):
            self.config.test.device = config_dict["device"]
        if config_dict.get("cpu"):
            self.config.test.cpu = config_dict["cpu"]
    
    def detect_current_stage(self) -> Tuple[str, str]:
        """
        检测当前所处的阶段
        
        Returns:
            (stage, description)
            stage: "generate", "build", "test", "unknown"
            description: 阶段描述
        """
        if self.config is None:
            return "unknown", "未加载配置"
        
        generate_dir = self.config.paths.generate_dir
        
        # 检查工程目录是否存在
        if not generate_dir.exists():
            return "generate", "工程目录不存在，需要生成工程"
        
        # 获取期望的工程数量
        template_dir = self.config.paths.template_dir
        if template_dir.exists():
            expected_projects = len([d for d in template_dir.iterdir() if d.is_dir()])
        else:
            expected_projects = len(self.config.cases)
        
        if expected_projects == 0:
            expected_projects = 1  # 至少一个
        
        # 检查工程文件
        project_files = list(generate_dir.rglob(".project"))
        if len(project_files) < expected_projects:
            return "generate", f"工程不完整 ({len(project_files)}/{expected_projects})，需要生成"
        
        # 检查 .out 文件
        out_files = list(generate_dir.rglob("*.out"))
        if len(out_files) < expected_projects:
            return "build", f"缺少 .out 文件 ({len(out_files)}/{expected_projects})，需要构建"
        
        return "test", "工程已就绪，可以直接测试"
    
    def set_status(self, message: str):
        """设置状态栏消息"""
        self.ready_label.setText(message)
        self.status_bar.showMessage(message, 5000)
    
    # ========== 事件处理 ==========
    
    def on_open_config(self):
        """打开配置文件"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开配置文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if path:
            self.load_config(path)
    
    def on_save_config(self):
        """保存配置"""
        self.save_config()
    
    def on_save_config_as(self) -> bool:
        """另存为配置"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存配置文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if path:
            return self.save_config(path)
        return False
    
    def on_check_hardware(self):
        """检测硬件"""
        if self.config is None:
            QMessageBox.warning(self, "警告", "请先加载配置文件")
            return
        
        # 切换到硬件检测标签页
        self.tab_widget.setCurrentWidget(self.hardware_panel)
        
        # 开始检测
        self.hardware_panel.start_check()
    
    def on_detect_stage(self):
        """检测当前阶段"""
        stage, description = self.detect_current_stage()
        self.stage_detected.emit(stage, description)

    def on_refresh_project(self):
        """刷新项目状态 - 重新检测当前阶段"""
        if self.config is None:
            QMessageBox.warning(self, "警告", "请先加载配置文件")
            return

        self.set_status("正在刷新项目状态...")

        # 重新检测当前阶段
        stage, description = self.detect_current_stage()
        self.stage_detected.emit(stage, description)

        # 刷新执行面板中的用例列表
        self.execute_panel.refresh_cases()

        self.set_status(f"项目状态已刷新: {description}")
    
    def on_config_changed(self):
        """配置变更处理"""
        self.set_status("配置已修改")
        # 重新检测阶段
        self.on_detect_stage()
    
    def on_hardware_check_completed(self, success: bool, message: str):
        """硬件检测完成处理"""
        if success:
            self.hw_status_label.setText("硬件: 已连接")
            self.hw_status_label.setStyleSheet("color: green;")
        else:
            self.hw_status_label.setText("硬件: 未连接")
            self.hw_status_label.setStyleSheet("color: red;")
        
        self.set_status(f"硬件检测: {message}")
    
    def on_stage_detected(self, stage: str, description: str):
        """阶段检测完成处理"""
        self.current_stage = stage
        self.stage_description = description
        
        # 更新状态栏
        stage_names = {
            "generate": "生成工程",
            "build": "构建",
            "test": "测试",
            "unknown": "未知"
        }
        self.stage_label.setText(f"阶段: {stage_names.get(stage, stage)}")
        
        # 更新执行面板
        self.execute_panel.set_current_stage(stage, description)
        
        self.set_status(description)
    
    def on_execution_started(self):
        """执行开始处理"""
        self.set_status("执行中...")
        self.ready_label.setText("执行中")
    
    def on_execution_finished(self, success: bool):
        """执行完成处理"""
        if success:
            self.set_status("执行完成")
            self.ready_label.setText("完成")
        else:
            self.set_status("执行失败")
            self.ready_label.setText("失败")
        
        # 重新检测阶段
        self.on_detect_stage()
    
    def on_log_message(self, message: str):
        """日志消息处理"""
        self.log_panel.append_log(message)
    
    def on_about(self):
        """关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 检查是否有未保存的更改
        # TODO: 实现配置修改检测
        event.accept()


def main():
    """GUI 入口函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
