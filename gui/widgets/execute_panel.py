#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行面板

用于控制测试执行和显示进度
"""

import sys
from pathlib import Path
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QProgressBar, QGroupBox,
    QRadioButton, QButtonGroup, QMessageBox, QTextEdit,
    QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from .case_table import CaseTable
from ..workers.pipeline_worker import PipelineWorker
from ..dialogs.hardware_error_dialog import HardwareErrorDialog


class ExecutePanel(QWidget):
    """执行面板"""
    
    execution_started = pyqtSignal()
    execution_finished = pyqtSignal(bool)  # 成功/失败
    log_message = pyqtSignal(str)  # 日志消息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config: Optional[Config] = None
        self.current_stage: str = "unknown"
        self.stage_description: str = ""
        self.worker: Optional[PipelineWorker] = None
        
        # 断点续测相关
        self.resume_batch: int = 0  # 0 表示不启用断点续测
        self.hardware_error_occurred: bool = False
        self.failed_batch_number: int = 0
        self.run_timestamp: Optional[str] = None  # 用于保持断点续测结果文件时间戳一致
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # ===== 执行控制组 =====
        control_group = QGroupBox("执行控制")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(10)
        
        # 当前阶段显示
        stage_layout = QHBoxLayout()
        stage_layout.addWidget(QLabel("当前阶段:"))
        self.stage_label = QLabel("未知")
        self.stage_label.setStyleSheet("font-weight: bold; color: #0066CC;")
        stage_layout.addWidget(self.stage_label)
        stage_layout.addStretch()
        control_layout.addLayout(stage_layout)
        
        # 阶段描述
        self.stage_desc_label = QLabel("请先加载配置文件")
        self.stage_desc_label.setWordWrap(True)
        control_layout.addWidget(self.stage_desc_label)
        
        # 分隔线
        line = QLabel()
        line.setFrameShape(QLabel.Shape.HLine)
        line.setStyleSheet("background-color: #CCCCCC;")
        line.setFixedHeight(1)
        control_layout.addWidget(line)
        
        # 执行选项
        control_layout.addWidget(QLabel("执行选项:"))
        
        self.stage_button_group = QButtonGroup(self)
        
        self.full_radio = QRadioButton("完整执行 (生成 → 构建 → 测试)")
        self.stage_button_group.addButton(self.full_radio, 0)
        control_layout.addWidget(self.full_radio)
        
        self.generate_radio = QRadioButton("从生成开始")
        self.stage_button_group.addButton(self.generate_radio, 1)
        control_layout.addWidget(self.generate_radio)
        
        self.build_radio = QRadioButton("从构建开始")
        self.stage_button_group.addButton(self.build_radio, 2)
        control_layout.addWidget(self.build_radio)
        
        self.test_radio = QRadioButton("仅测试")
        self.stage_button_group.addButton(self.test_radio, 3)
        control_layout.addWidget(self.test_radio)
        
        # 默认选中完整执行
        self.full_radio.setChecked(True)
        
        # 分隔线
        line2 = QLabel()
        line2.setFrameShape(QLabel.Shape.HLine)
        line2.setStyleSheet("background-color: #CCCCCC;")
        line2.setFixedHeight(1)
        control_layout.addWidget(line2)
        
        # 断点续测选项
        resume_layout = QHBoxLayout()
        
        self.resume_checkbox = QCheckBox("断点续测")
        self.resume_checkbox.setToolTip("启用断点续测功能，从上次失败的批次继续执行")
        self.resume_checkbox.stateChanged.connect(self.on_resume_checkbox_changed)
        resume_layout.addWidget(self.resume_checkbox)
        
        resume_layout.addWidget(QLabel("起始批次:"))
        self.resume_batch_spin = QSpinBox()
        self.resume_batch_spin.setMinimum(1)
        self.resume_batch_spin.setMaximum(9999)
        self.resume_batch_spin.setValue(1)
        self.resume_batch_spin.setEnabled(False)
        self.resume_batch_spin.setToolTip("设置从第几批开始执行（1-based）")
        resume_layout.addWidget(self.resume_batch_spin)
        
        resume_layout.addStretch()
        control_layout.addLayout(resume_layout)
        
        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("总进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        control_layout.addLayout(progress_layout)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("就绪")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        control_layout.addLayout(stats_layout)
        
        layout.addWidget(control_group)
        
        # ===== 用例列表组 =====
        case_group = QGroupBox("用例列表")
        case_layout = QVBoxLayout(case_group)
        
        self.case_table = CaseTable()
        case_layout.addWidget(self.case_table)
        
        layout.addWidget(case_group)
        
        # ===== 按钮区域 =====
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_btn = QPushButton("开始执行")
        self.start_btn.setFixedWidth(120)
        self.start_btn.clicked.connect(self.start_execution)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFixedWidth(120)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_execution)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def set_config(self, config: Config):
        """
        设置配置
        
        Args:
            config: 配置对象
        """
        self.config = config
        
        # 加载用例列表
        self.case_table.clear_cases()
        for case in config.cases:
            self.case_table.add_case(case.name)
    
    def set_current_stage(self, stage: str, description: str = ""):
        """
        设置当前阶段
        
        Args:
            stage: 阶段名称 ("generate", "build", "test", "unknown")
            description: 阶段描述
        """
        self.current_stage = stage
        self.stage_description = description
        
        # 更新显示
        stage_names = {
            "generate": "生成工程",
            "build": "构建",
            "test": "测试",
            "unknown": "未知"
        }
        self.stage_label.setText(stage_names.get(stage, stage))
        self.stage_desc_label.setText(description)
        
        # 更新执行选项可用性
        self._update_execution_options()
    
    def _update_execution_options(self):
        """更新执行选项可用性"""
        if self.current_stage == "generate":
            self.full_radio.setEnabled(True)
            self.generate_radio.setEnabled(True)
            self.build_radio.setEnabled(False)
            self.test_radio.setEnabled(False)
            self.full_radio.setChecked(True)
        elif self.current_stage == "build":
            self.full_radio.setEnabled(True)
            self.generate_radio.setEnabled(True)
            self.build_radio.setEnabled(True)
            self.test_radio.setEnabled(False)
            self.build_radio.setChecked(True)
        elif self.current_stage == "test":
            self.full_radio.setEnabled(True)
            self.generate_radio.setEnabled(True)
            self.build_radio.setEnabled(True)
            self.test_radio.setEnabled(True)
            self.test_radio.setChecked(True)
        else:  # unknown
            self.full_radio.setEnabled(True)
            self.generate_radio.setEnabled(True)
            self.build_radio.setEnabled(True)
            self.test_radio.setEnabled(True)
            self.full_radio.setChecked(True)
    
    def _get_selected_stage(self) -> str:
        """获取选中的起始阶段"""
        checked_id = self.stage_button_group.checkedId()
        
        if checked_id == 0:
            return "generate"
        elif checked_id == 1:
            return "generate"
        elif checked_id == 2:
            return "build"
        else:  # 3
            return "test"
    
    def on_resume_checkbox_changed(self, state):
        """断点续测复选框状态改变"""
        self.resume_batch_spin.setEnabled(state == Qt.Checked)
        if state == Qt.Checked:
            # 如果勾选了断点续测，自动选择"仅测试"
            self.test_radio.setChecked(True)
    
    def start_execution(self):
        """开始执行"""
        if self.config is None:
            QMessageBox.warning(self, "警告", "请先加载配置文件")
            return
        
        # 获取选中的起始阶段
        start_stage = self._get_selected_stage()
        
        # 验证是否可以执行
        if start_stage == "test" and self.current_stage != "test":
            QMessageBox.warning(
                self,
                "无法执行",
                "当前阶段不支持仅测试，请先完成构建。"
            )
            return
        
        # 获取断点续测设置
        start_batch = 0
        resume_test = False
        if self.resume_checkbox.isChecked():
            start_batch = self.resume_batch_spin.value() - 1  # 转换为 0-based
            resume_test = True
            self.log_message.emit(f"启用断点续测，从第 {start_batch + 1} 批开始")
        
        # 处理时间戳（必须在调用 _generate_test_config 之前）
        # 如果不是断点续测，生成新的时间戳
        # 如果是断点续测，保持原来的时间戳
        if not resume_test:
            from datetime import datetime
            self.run_timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
            self.log_message.emit(f"新的测试会话，时间戳: {self.run_timestamp}")
        else:
            # 断点续测时，如果时间戳丢失，尝试从已有结果目录恢复
            if self.run_timestamp is None:
                self.run_timestamp = self._recover_timestamp_from_results()
                if self.run_timestamp:
                    self.log_message.emit(f"断点续测，从结果目录恢复时间戳: {self.run_timestamp}")
                else:
                    from datetime import datetime
                    self.run_timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
                    self.log_message.emit(f"断点续测，无法恢复时间戳，使用新时间戳: {self.run_timestamp}")
            else:
                self.log_message.emit(f"断点续测，使用原时间戳: {self.run_timestamp}")
        
        # 在执行之前，从主窗口获取最新的配置
        main_window = self.window()
        if hasattr(main_window, 'config_panel') and hasattr(main_window, '_update_config_from_dict'):
            # 从配置面板获取最新配置并更新
            config_dict = main_window.config_panel.get_config_dict()
            main_window._update_config_from_dict(config_dict)
            # 更新执行面板的配置引用
            self.config = main_window.config
            # 重新生成测试配置文件（传递时间戳以保持一致）
            main_window._generate_test_config(run_timestamp=self.run_timestamp)
        
        # 重置状态（如果不是断点续测）
        if not resume_test:
            self.case_table.clear_cases()
            for case in self.config.cases:
                self.case_table.add_case(case.name, "pending")
        
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stats_label.setText("执行中...")
        
        # 重置硬件错误标志
        self.hardware_error_occurred = False
        self.failed_batch_number = 0
        
        # 发送开始信号
        self.execution_started.emit()
        self.log_message.emit(f"开始执行，起始阶段: {start_stage}")
        
        # 创建工作线程
        self.worker = PipelineWorker(
            self.config, start_stage,
            start_batch=start_batch,
            resume_test=resume_test,
            run_timestamp=self.run_timestamp
        )
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.case_list_loaded.connect(self.on_case_list_loaded)
        self.worker.case_started.connect(self.on_case_started)
        self.worker.case_finished.connect(self.on_case_finished)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.hardware_error.connect(self.on_hardware_error)
        self.worker.finished.connect(self.on_execution_finished)
        self.worker.start()
    
    def stop_execution(self):
        """停止执行"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.stop_btn.setEnabled(False)
    
    def on_progress_updated(self, percent: int, message: str):
        """
        进度更新处理

        Args:
            percent: 进度百分比
            message: 进度消息
        """
        self.progress_bar.setValue(percent)
        self.stats_label.setText(message)

    def on_case_list_loaded(self, case_names: list):
        """
        用例列表加载完成处理

        Args:
            case_names: 用例名称列表
        """
        # 如果不是断点续测，清空并重新加载所有用例
        # 如果是断点续测，只添加新用例，保留已有用例状态
        if not self.resume_checkbox.isChecked():
            self.case_table.clear_cases()
            for name in case_names:
                self.case_table.add_case(name, "pending")
        else:
            # 断点续测：只添加不存在的用例，保留已有用例状态
            existing_cases = set()
            for row in range(self.case_table.rowCount()):
                case_name_item = self.case_table.item(row, 0)
                if case_name_item:
                    existing_cases.add(case_name_item.text())
            
            for name in case_names:
                if name not in existing_cases:
                    self.case_table.add_case(name, "pending")

        total = self.case_table.rowCount()
        self.stats_label.setText(f"已加载 {total} 个用例")
        self.log_message.emit(f"用例列表已加载: {total} 个用例")

    def on_case_started(self, case_name: str):
        """
        用例开始处理
        
        Args:
            case_name: 用例名称
        """
        self.case_table.update_case(case_name, status="running")
        self.log_message.emit(f"开始执行用例: {case_name}")
    
    def on_case_finished(self, case_name: str, status: str, duration: float):
        """
        用例完成处理
        
        Args:
            case_name: 用例名称
            status: 状态
            duration: 耗时(秒)
        """
        duration_str = f"{duration:.1f}s"
        self.case_table.update_case(case_name, status=status, duration=duration_str)
        
        # 更新统计
        completed = self.case_table.get_completed_count()
        total = len(self.case_table.get_all_cases())
        success = self.case_table.get_success_count()
        failed = self.case_table.get_failed_count()
        
        self.stats_label.setText(
            f"进度: {completed}/{total} | 成功: {success} | 失败: {failed}"
        )
        
        self.log_message.emit(
            f"用例完成: {case_name} - {status} ({duration_str})"
        )
    
    def on_log_message(self, message: str):
        """
        日志消息处理
        
        Args:
            message: 日志消息
        """
        self.log_message.emit(message)
    
    def on_hardware_error(self, batch_number: int, error_message: str):
        """
        硬件连接错误处理
        
        Args:
            batch_number: 失败的批次号
            error_message: 错误信息
        """
        self.hardware_error_occurred = True
        self.failed_batch_number = batch_number
        
        # 显示硬件错误对话框
        should_resume, resume_batch = HardwareErrorDialog.show_error(
            self, batch_number, error_message
        )
        
        if should_resume:
            # 用户选择断点续测
            self.log_message.emit(f"用户选择从第 {resume_batch} 批继续执行")
            
            # 更新断点续测设置
            self.resume_checkbox.setChecked(True)
            self.resume_batch_spin.setValue(resume_batch)
            
            # 自动重新开始执行
            # 延迟执行，给用户足够时间重新连接硬件
            self.log_message.emit("请在5秒内重新连接硬件...")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(5000, self.start_execution)
        else:
            # 用户取消
            self.log_message.emit("用户取消断点续测")
            self.stats_label.setText(f"硬件连接失败，已执行 {batch_number - 1} 批")
    
    def on_execution_finished(self, success: bool):
        """
        执行完成处理

        Args:
            success: 是否成功
        """
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self.progress_bar.setValue(100)
            self.stats_label.setText("执行完成")
            # 执行成功，清除断点续测设置
            self.resume_checkbox.setChecked(False)
        else:
            if self.hardware_error_occurred:
                # 硬件错误已在 on_hardware_error 中处理
                pass
            else:
                self.stats_label.setText("执行失败")

        self.execution_finished.emit(success)

    def _recover_timestamp_from_results(self) -> Optional[str]:
        """
        从已有的结果目录恢复时间戳
        
        在断点续测时，如果时间戳丢失，尝试从以下位置恢复：
        1. 已有的结果目录 (5_result_dat)
        2. 已有的日志目录 (6_result_dat_logs)
        3. full_regr.json 配置文件
        
        Returns:
            恢复的时间戳字符串，如果无法恢复则返回 None
        """
        from pathlib import Path
        
        # 方法1: 从结果目录获取最新的时间戳
        result_dir = Path("5_result_dat")
        if result_dir.exists():
            # 获取所有时间戳目录
            timestamp_dirs = [d for d in result_dir.iterdir() if d.is_dir()]
            if timestamp_dirs:
                # 按修改时间排序，获取最新的
                latest_dir = max(timestamp_dirs, key=lambda d: d.stat().st_mtime)
                timestamp = latest_dir.name
                # 验证是否是有效的时间戳格式 (YYYY-MM-DD-HH-MM)
                import re
                if re.match(r'\d{4}-\d{2}-\d{2}-\d{2}-\d{2}', timestamp):
                    self.log_message.emit(f"从结果目录恢复时间戳: {timestamp}")
                    return timestamp
        
        # 方法2: 从日志目录获取最新的时间戳
        log_dir = Path("6_result_dat_logs")
        if log_dir.exists():
            timestamp_dirs = [d for d in log_dir.iterdir() if d.is_dir()]
            if timestamp_dirs:
                latest_dir = max(timestamp_dirs, key=lambda d: d.stat().st_mtime)
                timestamp = latest_dir.name
                import re
                if re.match(r'\d{4}-\d{2}-\d{2}-\d{2}-\d{2}', timestamp):
                    self.log_message.emit(f"从日志目录恢复时间戳: {timestamp}")
                    return timestamp
        
        # 方法3: 从 full_regr.json 配置文件获取
        config_file = Path("full_regr.json")
        if config_file.exists():
            try:
                import json
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                cases = config.get("cases", [])
                if cases:
                    # 从第一个用例的 dat_dir 提取时间戳
                    dat_dir = cases[0].get("dat_dir", "")
                    # dat_dir 格式: 5_result_dat/YYYY-MM-DD-HH-MM/case_name
                    parts = Path(dat_dir).parts
                    if len(parts) >= 2:
                        timestamp = parts[1] if parts[0] == "5_result_dat" else parts[-2]
                        import re
                        if re.match(r'\d{4}-\d{2}-\d{2}-\d{2}-\d{2}', timestamp):
                            self.log_message.emit(f"从配置文件恢复时间戳: {timestamp}")
                            return timestamp
            except Exception as e:
                self.log_message.emit(f"从配置文件恢复时间戳失败: {e}")
        
        return None

    def refresh_cases(self):
        """刷新用例列表 - 从工程目录重新扫描"""
        if self.config is None:
            return

        # 清空当前用例列表
        self.case_table.clear_cases()

        # 从配置中重新加载用例
        if self.config.cases:
            # 如果配置中有用例，直接使用
            for case in self.config.cases:
                self.case_table.add_case(case.name, "pending")
        else:
            # 如果配置中没有用例，从工程目录扫描
            generate_dir = self.config.paths.generate_dir
            if generate_dir.exists():
                # 扫描工程目录下的子目录作为用例
                case_dirs = [d for d in generate_dir.iterdir() if d.is_dir()]
                for case_dir in sorted(case_dirs):
                    # 检查是否是有效的工程目录（包含.project文件或.out文件）
                    has_project = any(case_dir.rglob(".project"))
                    has_out = any(case_dir.rglob("*.out"))
                    if has_project or has_out:
                        self.case_table.add_case(case_dir.name, "pending")

        # 更新统计显示
        total = len(self.case_table.get_all_cases())
        self.stats_label.setText(f"已刷新: {total} 个用例")
