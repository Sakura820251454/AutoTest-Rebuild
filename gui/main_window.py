#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoTest GUI 主窗口

@input Config (配置对象)
@input ConfigPanel, HardwarePanel, ExecutePanel, LogPanel (子面板)
@input QSettings (记住上次使用的配置)
@output MainWindow类；resolve_startup_config() 启动配置选择规则
@pos GUI核心入口，整合所有面板和菜单，提供图形化配置管理、硬件检测和测试执行；
     启动时按 -c → config/config.json → 上次使用 → 空态 的顺序加载配置

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
import os
import traceback
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QLabel, QPushButton,
    QFileDialog, QMessageBox, QApplication, QMenuBar, QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.logger import get_logger
from src.runtime_paths import app_path, resource_path
from .utils.error_messages import describe_exception, format_error
from .utils.message_boxes import critical, information, warning
from .widgets.config_panel import ConfigPanel
from .widgets.hardware_panel import HardwarePanel
from .widgets.execute_panel import ExecutePanel
from .widgets.log_panel import LogPanel
from .dialogs.about_dialog import AboutDialog

logger = get_logger(__name__)

SETTINGS_ORG = "AutoTest"
SETTINGS_APP = "AutoTestGUI"
LAST_CONFIG_KEY = "last_config_path"
DEFAULT_CONFIG_REL = Path("config") / "config.json"


def resolve_startup_config(explicit_path, default_path, last_path):
    """
    选择启动时要加载的配置

    优先级：-c 显式指定 → config/config.json → 上次使用的配置 → 空态（None）。
    只返回真实存在的文件，调用方无需再判存在。
    """
    for candidate in (explicit_path, default_path, last_path):
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return path
    return None


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
        self.config_available: bool = False

        self.setWindowTitle("AutoTest GUI - TI C2000 DSP 自动化测试")
        self.setMinimumSize(1000, 700)

        # 标题栏/任务栏图标（QApplication 已设置时保持一致）
        icon_path = resource_path("gui/assets/app.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._connect_signals()

        # 未加载配置前先进入空态（开始执行/开始检测禁用）
        self._set_config_available(False)

        # 启动配置：-c → config/config.json → 上次使用 → 空态
        self._load_startup_config(config_path)
    
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
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
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

        tools_menu.addSeparator()

        # 目录快捷入口（不改变任何执行流程，只是打开资源管理器）
        open_results_action = QAction("打开结果目录", self)
        open_results_action.triggered.connect(self.on_open_results_dir)
        tools_menu.addAction(open_results_action)

        open_workspace_action = QAction("打开工作区", self)
        open_workspace_action.triggered.connect(self.on_open_workspace_dir)
        tools_menu.addAction(open_workspace_action)

        open_log_action = QAction("打开日志目录", self)
        open_log_action.triggered.connect(self.on_open_log_dir)
        tools_menu.addAction(open_log_action)
        
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
        self.hardware_panel.log_entry.connect(self.on_log_entry)

        # 执行面板信号
        self.execute_panel.execution_started.connect(self.on_execution_started)
        self.execute_panel.execution_finished.connect(self.on_execution_finished)
        self.execute_panel.log_message.connect(self.on_log_message)
        self.execute_panel.log_entry.connect(self.on_log_entry)
        self.execute_panel.show_log_requested.connect(self.on_show_log_tab)
        self.execute_panel.open_results_requested.connect(self.on_open_results_dir)
        
        # 阶段检测信号
        self.stage_detected.connect(self.on_stage_detected)
    
    # ========== 启动配置 ==========

    @staticmethod
    def _settings() -> QSettings:
        """QSettings 显式指定组织/应用名，避免依赖 QApplication 的全局设置"""
        return QSettings(SETTINGS_ORG, SETTINGS_APP)

    def _last_config_path(self) -> str:
        """上次成功加载/保存的配置路径（没有则返回空串）"""
        try:
            value = self._settings().value(LAST_CONFIG_KEY, "")
        except Exception:
            return ""
        return str(value) if value else ""

    def _remember_config_path(self, path: str):
        """记住本次使用的配置，下次启动时作为兜底"""
        try:
            settings = self._settings()
            settings.setValue(LAST_CONFIG_KEY, str(path))
            settings.sync()
        except Exception:
            pass

    def _load_startup_config(self, config_path: Optional[str]):
        """
        启动时决定加载哪个配置

        不带 -c 时先找 config/config.json，再尝试上次使用的配置；都不存在则保持空态。
        """
        explicit = str(config_path) if config_path else None
        if explicit and not Path(explicit).is_file():
            message = format_error(
                "找不到 -c 指定的配置文件",
                path=explicit,
                action="请确认路径，或去掉 -c 让程序自动加载 config/config.json",
            )
            self.log_panel.append_log(message.replace("\n", " | "), "WARNING")
            warning(self, "配置加载失败", message)
            explicit = None

        target = resolve_startup_config(
            explicit, app_path(DEFAULT_CONFIG_REL), self._last_config_path()
        )
        if target is None:
            self.log_panel.append_log(
                "未加载配置：未指定 -c，config/config.json 和上次使用的配置都不存在。"
                "请按“配置”页的三步引导完成设置。",
                "WARNING",
            )
            self.set_status("未加载配置，请先在“配置”页完成设置")
            return

        self.load_config(str(target))

    def _set_config_available(self, available: bool):
        """同步“是否已加载配置”到各面板（禁用按钮 + 空态引导）"""
        self.config_available = bool(available)
        self.config_panel.set_config_loaded(self.config_available)
        reason = (
            "尚未加载配置：请先在“配置”页选择工作区目录并“保存配置”，"
            "或通过“文件 → 打开配置...”加载"
        )
        self.execute_panel.set_config_available(self.config_available, reason)
        self.hardware_panel.set_config_available(self.config_available, reason)

    def load_config(self, path: str):
        """
        加载配置文件
        
        Args:
            path: 配置文件路径
        """
        try:
            config = Config.load(path)
        except Exception as exc:
            message = describe_exception(exc, path=str(path))
            logger.error("加载配置失败: %s", path, exc_info=True)
            self.log_panel.append_log(f"加载配置失败: {path}", "ERROR")
            self.log_panel.append_log(traceback.format_exc().rstrip(), "DEBUG")
            self._set_config_available(False)
            self.set_status("配置加载失败")
            critical(self, "配置加载失败", message)
            return False

        self.config = config
        self.config_path = path

        # 更新配置面板
        self.config_panel.load_config(self.config)

        # 更新硬件检测面板
        self.hardware_panel.set_config(self.config)

        # 更新执行面板
        self.execute_panel.set_config(self.config)

        # 生成测试配置文件 full_regr.json
        self._generate_test_config()

        # 发送信号
        self.config_loaded.emit(self.config)

        # 记住本次配置并解除空态
        self._remember_config_path(path)
        self._set_config_available(True)

        self.log_panel.append_log(f"配置已加载: {path}", "INFO")

        # 更新状态栏
        self.set_status(f"配置已加载: {path}")

        # 自动检测阶段
        self.on_detect_stage()

        return True
    
    def _generate_test_config(self, run_timestamp: Optional[str] = None):
        """
        生成测试配置文件 full_regr.json
        
        Args:
            run_timestamp: 时间戳，用于断点续测时保持时间戳一致
        """
        try:
            from src.executor import TestExecutor
            
            executor = TestExecutor(self.config, run_timestamp=run_timestamp)
            test_config_path = executor.generate_test_config()
            
            if test_config_path and Path(test_config_path).exists():
                self.set_status(f"测试配置已生成: {test_config_path}")
        except Exception as exc:
            # 生成测试配置失败不影响主流程，只写日志（含堆栈），不弹窗
            logger.error("生成测试配置失败", exc_info=True)
            self.log_panel.append_log("生成测试配置失败", "ERROR")
            self.log_panel.append_log(traceback.format_exc().rstrip(), "DEBUG")
    
    def save_config(self, path: Optional[str] = None) -> bool:
        """
        保存配置文件
        
        Args:
            path: 保存路径，None 表示使用当前路径
        
        Returns:
            是否保存成功
        """
        if self.config is None:
            warning(self, "无法保存配置", "没有可保存的配置")
            return False
        
        try:
            # 从面板获取最新配置值
            config_dict = self.config_panel.get_config_dict()
            
            # 更新配置对象的各个属性
            self._update_config_from_dict(config_dict)

            # 导出 dat 目录必须可创建/可写，不做静默接受
            results_dir = self.config.paths.results_dir
            try:
                results_dir.mkdir(parents=True, exist_ok=True)
                probe = results_dir / ".write_test"
                probe.write_text("", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                message = describe_exception(
                    exc, path=str(results_dir),
                    action="请换一个可写目录，或检查目录是否被占用")
                logger.error("导出 dat 目录不可用: %s", results_dir, exc_info=True)
                self.log_panel.append_log(message.replace("\n", " | "), "ERROR")
                self.log_panel.append_log(traceback.format_exc().rstrip(), "DEBUG")
                warning(self, "导出 dat 目录不可用", message)
                return False

            # 确定保存路径
            save_path = path or self.config_path
            if save_path is None:
                return self.on_save_config_as()
            
            # 保存（使用新的保存方法，保留格式和注释）
            self.config.save(save_path)
            self.config_path = save_path
            
            # 保存配置后重新生成测试配置文件
            self._generate_test_config()

            self._remember_config_path(save_path)
            self._set_config_available(True)
            self.log_panel.append_log(f"配置已保存: {save_path}", "INFO")

            self.set_status(f"配置已保存: {save_path}")
            return True

        except Exception as exc:
            message = describe_exception(
                exc, path=str(path or self.config_path or ""),
                action="请检查配置文件是否被占用、目录是否有写权限")
            logger.error("保存配置失败", exc_info=True)
            self.log_panel.append_log("保存配置失败", "ERROR")
            self.log_panel.append_log(traceback.format_exc().rstrip(), "DEBUG")
            critical(self, "保存配置失败", message)
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
            # 工作区单一真源：ccs_workspace 始终跟随 generate_dir
            self.config.paths.ccs_workspace = self.config.paths.generate_dir
        if config_dict.get("result_dir"):
            self.config.paths.result_dir = Path(config_dict["result_dir"])
        results_dir = (config_dict.get("results_dir") or "").strip()
        if results_dir:
            results_path = Path(results_dir)
            if not results_path.is_absolute():
                results_path = self.config._base_dir / results_path
            self.config.paths.results_dir = results_path.resolve()
        if config_dict.get("ccs_executable"):
            self.config.paths.ccs_executable = Path(config_dict["ccs_executable"])
        if config_dict.get("ccs_dss"):
            self.config.paths.ccs_dss = Path(config_dict["ccs_dss"])
        if config_dict.get("ccxml"):
            self.config.paths.ccxml = Path(config_dict["ccxml"])
        if "gel_file" in config_dict:
            gel_value = (config_dict.get("gel_file") or "").strip()
            self.config.paths.gel_file = Path(gel_value) if gel_value else None
        
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
        if "auto_resume" in config_dict:
            self.config.test.auto_resume = config_dict["auto_resume"]
        if "max_retries" in config_dict:
            self.config.test.max_retries = config_dict["max_retries"]
        if "retry_delay" in config_dict:
            self.config.test.retry_delay = config_dict["retry_delay"]
        if "encrypt_flash_dat" in config_dict:
            self.config.test.encrypt_flash_dat = config_dict["encrypt_flash_dat"]
        if "flash_encrypt_verify" in config_dict:
            self.config.test.flash_encrypt_verify = config_dict["flash_encrypt_verify"]
        if "copy_project" in config_dict:
            self.config.test.copy_project = config_dict["copy_project"]
        
        # 更新内存段配置
        if config_dict.get("memory_segments"):
            # 更新到 _raw 中，以便保存时能正确写入
            self.config._raw["memory_segments"] = config_dict["memory_segments"]

            # 同时更新内存段列表
            from src.config import MemorySegment
            self.config.memory_segments = []
            for segment_data in config_dict["memory_segments"].get("segments", []):
                segment = MemorySegment(
                    name=segment_data["name"],
                    addr=segment_data["addr"],
                    len=segment_data["len"],
                    width=segment_data["width"],
                    page=segment_data.get("page", 0)
                )
                self.config.memory_segments.append(segment)

            # 同时更新导出时间点配置
            from src.config import ExportPoint
            export_points_data = config_dict["memory_segments"].get("export_points", [])
            if export_points_data:
                self.config.export_points = [
                    ExportPoint(
                        when=p.get("when", "after_run"),
                        enabled=p.get("enabled", True),
                        subdir=p.get("subdir", "memory")
                    )
                    for p in export_points_data
                ]
                # 同时更新每个测试用例的 export_points 配置
                for case in self.config.cases:
                    case.export_points = list(self.config.export_points)

            # 同时更新每个测试用例的 segments 配置
            for case in self.config.cases:
                case.segments = list(self.config.memory_segments)

        # 更新结果判断配置
        if config_dict.get("result_check"):
            from src.config import ResultCheck
            rc_data = config_dict["result_check"]
            self.config.result_check = ResultCheck(
                method=rc_data.get("method", "breakpoint"),
                success_label=rc_data.get("success_label", "Right"),
                fail_label=rc_data.get("fail_label", "IDLE"),
                check_addr=rc_data.get("check_addr", ""),
                check_width=rc_data.get("check_width", 32),
                success_val=rc_data.get("success_val", ""),
                fail_val=rc_data.get("fail_val", ""),
                expression=rc_data.get("expression", ""),
                expected_val=rc_data.get("expected_val", "")
            )

            # 同时更新每个测试用例的 result_check 配置
            for case in self.config.cases:
                case.result_check = self.config.result_check

        # 更新 Flash 项目配置
        if "is_flash" in config_dict:
            is_flash = config_dict["is_flash"]
            # 更新每个测试用例的 is_flash 配置
            for case in self.config.cases:
                case.is_flash = is_flash
    
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
        """设置状态栏消息

        只更新右侧的就绪状态，避免 showMessage 在左侧重复同一句话并挤掉
        硬件/阶段信息。
        """
        self.ready_label.setText(message)
    
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
            message = format_error(
                "尚未加载配置",
                action="请先在“配置”页选择目录并保存，或通过“文件 → 打开配置...”加载")
            self.log_panel.append_log(message.replace("\n", " | "), "WARNING")
            warning(self, "无法检测硬件", message)
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
            message = format_error(
                "尚未加载配置",
                action="请先在“配置”页选择目录并保存，或通过“文件 → 打开配置...”加载")
            self.log_panel.append_log(message.replace("\n", " | "), "WARNING")
            warning(self, "无法刷新项目状态", message)
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
            self.log_panel.append_log(f"硬件检测通过: {message}", "INFO")
        else:
            self.hw_status_label.setText("硬件: 未连接")
            self.hw_status_label.setStyleSheet("color: red;")
            self.log_panel.append_log(f"硬件检测失败: {message}", "ERROR")

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
        self._clear_execute_tab_mark()
        self.set_status("执行中...")
        self.ready_label.setText("执行中")
    
    def on_execution_finished(self, success: bool):
        """执行完成处理"""
        stopped = bool(getattr(self.execute_panel, "stopped", False))
        if stopped:
            self.log_panel.append_log("执行已停止（未执行用例标记为跳过）", "WARNING")
        elif success:
            self.log_panel.append_log("执行完成", "INFO")
        else:
            self.log_panel.append_log("执行失败", "ERROR")

        # 先重新检测阶段（会写状态栏），再写结束提示，避免提示被“阶段: xxx”覆盖
        self.on_detect_stage()

        detail = self.execute_panel.stats_label.text().strip()
        if stopped:
            message = detail if detail.startswith("已停止") else "执行已停止"
            self.ready_label.setText("已停止")
        elif success:
            message = "执行完成"
            self.ready_label.setText("完成")
        else:
            message = "执行失败"
            self.ready_label.setText("失败")
        self.set_status(message)

        # 用户不在执行页：页签标记 + 任务栏闪烁，避免错过结束提示
        if self.tab_widget.currentWidget() is not self.execute_panel:
            self._mark_execute_tab_result(success, stopped)
            QApplication.alert(self, 0)
    
    def on_log_message(self, message: str):
        """日志消息处理（INFO）"""
        self.log_panel.append_log(message, "INFO")

    def on_log_entry(self, message: str, level: str):
        """带级别的日志（worker / 硬件检测）"""
        self.log_panel.append_log(message, level)

    def on_show_log_tab(self):
        """从错误条“查看日志”跳到日志页"""
        self.tab_widget.setCurrentWidget(self.log_panel)

    # ========== 目录快捷入口 ==========

    def on_open_results_dir(self):
        """打开结果目录（执行完成提示 / 工具菜单共用）"""
        base = self.config.paths.results_dir if self.config else app_path("results")
        self._open_directory(base, "结果目录", create=True)

    def on_open_workspace_dir(self):
        """打开工作区目录"""
        base = self.config.paths.generate_dir if self.config else app_path("workspace")
        self._open_directory(base, "工作区", create=False)

    def on_open_log_dir(self):
        """打开日志目录"""
        from src.logger import get_log_dir
        self._open_directory(get_log_dir() or app_path("logs"), "日志目录", create=True)

    def _open_directory(self, path, label: str, create: bool = False):
        """用资源管理器打开目录；失败时给三段式中文提示"""
        target = Path(path)
        if not target.exists():
            if not create:
                message = format_error(
                    f"{label}还不存在", path=target,
                    action="请先完成配置或执行一次，让目录自动生成")
                self.log_panel.append_log(message.replace("\n", " | "), "WARNING")
                information(self, f"{label}不存在", message)
                return
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                message = describe_exception(
                    exc, path=str(target),
                    action="请检查路径是否存在、是否有写权限")
                self.log_panel.append_log(message.replace("\n", " | "), "ERROR")
                warning(self, f"无法打开{label}", message)
                return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        self.log_panel.append_log(f"已打开{label}: {target}", "INFO")
    
    def on_about(self):
        """关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def on_tab_changed(self, index: int):
        """切到执行页时后台预扫描工作区，提前显示用例与就绪状态"""
        if self.tab_widget.widget(index) is self.execute_panel:
            self._clear_execute_tab_mark()
            self.execute_panel.start_case_scan()

    def _mark_execute_tab_result(self, success: bool, stopped: bool):
        """用户不在执行页时，在页签上标记本次执行结束（切回后清除）"""
        idx = self.tab_widget.indexOf(self.execute_panel)
        if idx < 0:
            return
        mark = "■" if stopped else ("✓" if success else "✗")
        self.tab_widget.setTabText(idx, f"执行 {mark}")
        self.tab_widget.setTabToolTip(idx, "执行已结束，点击查看本次结果")

    def _clear_execute_tab_mark(self):
        """恢复执行页签标题"""
        idx = self.tab_widget.indexOf(self.execute_panel)
        if idx < 0:
            return
        self.tab_widget.setTabText(idx, "执行")
        self.tab_widget.setTabToolTip(idx, "")

    def closeEvent(self, event):
        """关闭事件处理"""
        # 检查是否有未保存的更改
        # TODO: 实现配置修改检测
        self.execute_panel.shutdown_background_tasks()
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
