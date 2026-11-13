#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行面板

用于控制测试执行和显示进度；提供可关闭的错误条与“打开结果目录”入口

@input Config、PipelineWorker 信号
@output execution_started/execution_finished/log_message/log_entry 信号、三步步骤条与加权总进度、用例状态表
@pos “执行”标签页，负责任务启动/停止、进度展示与错误提示

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
from pathlib import Path
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QProgressBar, QGroupBox,
    QComboBox, QMessageBox, QTextEdit,
    QCheckBox, QFrame
)
from .no_scroll_spinbox import NoScrollSpinBox as QSpinBox
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.runtime_paths import app_path, to_posix
from .case_table import CaseTable
from ..utils.error_messages import format_error
from ..utils.message_boxes import warning
from ..workers.pipeline_worker import PipelineWorker
from ..workers.case_scanner import CaseScanWorker
from ..dialogs.hardware_error_dialog import HardwareErrorDialog

# 三步步骤条：顺序、界面名称、加权总进度权重（只对本次参与的阶段重新归一化）
STAGE_ORDER = ("generate", "build", "test")
STAGE_NAMES = {"generate": "生成", "build": "构建", "test": "测试"}
STAGE_WEIGHTS = {"generate": 15, "build": 25, "test": 60}
STEP_ICONS = {"pending": "○", "running": "●", "done": "✓", "failed": "✗",
              "stopped": "■", "skipped": "—"}
STEP_COLORS = {"pending": "#888888", "running": "#0066CC", "done": "#2E7D32",
               "failed": "#C62828", "stopped": "#B26A00", "skipped": "#AAAAAA"}


def stages_from(start_stage: str):
    """从起始阶段推出本次参与的阶段（例如“仅测试”只计测试）"""
    if start_stage not in STAGE_ORDER:
        return list(STAGE_ORDER)
    return list(STAGE_ORDER[STAGE_ORDER.index(start_stage):])


def compute_weighted_progress(stage_percents: Dict[str, int], stages) -> int:
    """按参与阶段归一化权重，返回 0-100 的总进度

    每个阶段内部 0→100，总进度 = Σ(权重×阶段进度)/Σ权重。这样“仅测试”也能
    从 0 走到 100，而完整执行不会出现三个 0→100 的重复循环。
    """
    active = [s for s in STAGE_ORDER if s in stages] or list(STAGE_ORDER)
    total_weight = sum(STAGE_WEIGHTS[s] for s in active)
    if total_weight <= 0:
        return 0
    done = 0
    for stage in active:
        percent = max(0, min(100, int(stage_percents.get(stage, 0))))
        done += STAGE_WEIGHTS[stage] * percent
    return int(round(done / total_weight))


class ExecutePanel(QWidget):
    """执行面板"""
    
    execution_started = pyqtSignal()
    execution_finished = pyqtSignal(bool)  # 成功/失败
    log_message = pyqtSignal(str)  # 日志消息
    log_entry = pyqtSignal(str, str)  # (消息, 级别)
    show_log_requested = pyqtSignal()  # 错误条“查看日志”
    open_results_requested = pyqtSignal()  # 结果提示“打开结果目录”
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config: Optional[Config] = None
        self.current_stage: str = "unknown"
        self.stage_description: str = ""
        self.worker: Optional[PipelineWorker] = None
        self._scan_worker: Optional[CaseScanWorker] = None  # 用例预扫描线程
        self._config_available: bool = False
        self._no_config_reason: str = "尚未加载配置"
        
        # 断点续测相关
        self.resume_batch: int = 0  # 0 表示不启用断点续测
        self.hardware_error_occurred: bool = False
        self.failed_batch_number: int = 0
        self.stopping: bool = False  # 已点击停止、等待工作线程收尾
        self.stopped: bool = False  # 本次执行因停止而结束
        self.run_timestamp: Optional[str] = None  # 用于保持断点续测结果文件时间戳一致

        # 三步进度：各阶段内部百分比 + 本次参与的阶段 + 总进度不回退
        self._stage_percent: Dict[str, int] = {s: 0 for s in STAGE_ORDER}
        self._active_stages = list(STAGE_ORDER)
        self._progress_floor = 0
        self._step_states: Dict[str, str] = {s: "pending" for s in STAGE_ORDER}
        self.step_labels: Dict[str, QLabel] = {}

        # 测试阶段明细（第 x/N 批、当前用例、已用时间）
        self._test_batch = 0
        self._test_batch_total = 0
        self._current_case = ""
        self._test_elapsed = QElapsedTimer()
        self._test_timer = QTimer(self)
        self._test_timer.setInterval(500)
        self._test_timer.timeout.connect(self._update_test_detail)

        self._setup_ui()
    
    def _setup_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # ===== 顶部错误条（可关闭，默认隐藏，不改变正常流程布局）=====
        self.error_bar = QFrame()
        self.error_bar.setFrameShape(QFrame.Shape.StyledPanel)
        self.error_bar.setStyleSheet(
            "QFrame { background-color: #FDECEA; border: 1px solid #E0A0A0; border-radius: 4px; }")
        error_layout = QHBoxLayout(self.error_bar)
        error_layout.setContentsMargins(10, 6, 6, 6)
        error_layout.setSpacing(8)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #A00000; border: none;")
        error_layout.addWidget(self.error_label, 1)

        self.error_log_btn = QPushButton("查看日志")
        self.error_log_btn.setFixedWidth(90)
        self.error_log_btn.clicked.connect(self.show_log_requested.emit)
        error_layout.addWidget(self.error_log_btn)

        self.error_close_btn = QPushButton("×")
        self.error_close_btn.setFixedWidth(28)
        self.error_close_btn.setToolTip("关闭错误提示")
        self.error_close_btn.clicked.connect(self.hide_error_bar)
        error_layout.addWidget(self.error_close_btn)

        self.error_bar.setVisible(False)
        layout.addWidget(self.error_bar)

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

        # 三步步骤条（生成 → 构建 → 测试）：显示各阶段状态，配合下方加权总进度
        step_layout = QHBoxLayout()
        step_layout.setSpacing(6)
        for idx, stage in enumerate(STAGE_ORDER):
            chip = QLabel()
            chip.setAlignment(Qt.AlignCenter)
            chip.setMinimumWidth(84)
            self.step_labels[stage] = chip
            self._apply_step_state(stage, "pending")
            step_layout.addWidget(chip)
            if idx < len(STAGE_ORDER) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #999999;")
                step_layout.addWidget(arrow)
        step_layout.addStretch()
        control_layout.addLayout(step_layout)
        
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
        
        control_layout.addWidget(QLabel("起始阶段:"))
        self.start_stage_combo = QComboBox()
        self.start_stage_combo.addItem("生成（生成 → 构建 → 测试）", "generate")
        self.start_stage_combo.addItem("构建（构建 → 测试）", "build")
        self.start_stage_combo.addItem("测试（仅测试）", "test")
        self.start_stage_combo.setCurrentIndex(0)
        control_layout.addWidget(self.start_stage_combo)

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

        # 测试阶段明细：第 x/N 批 | 当前用例 | 已用时间
        self.test_detail_label = QLabel("")
        self.test_detail_label.setStyleSheet("color: #555555;")
        self.test_detail_label.setVisible(False)
        control_layout.addWidget(self.test_detail_label)
        
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

        # ===== 结果提示（执行结束后显示，可直接打开结果目录）=====
        self.result_hint = QFrame()
        self.result_hint.setFrameShape(QFrame.Shape.StyledPanel)
        result_layout = QHBoxLayout(self.result_hint)
        result_layout.setContentsMargins(10, 6, 6, 6)
        result_layout.setSpacing(8)

        self.result_hint_label = QLabel("")
        self.result_hint_label.setWordWrap(True)
        result_layout.addWidget(self.result_hint_label, 1)

        self.open_results_btn = QPushButton("打开结果目录")
        self.open_results_btn.setFixedWidth(120)
        self.open_results_btn.clicked.connect(self.open_results_requested.emit)
        result_layout.addWidget(self.open_results_btn)

        self.result_hint.setVisible(False)
        layout.addWidget(self.result_hint)

        # 未加载配置前不能开始执行
        self.case_table.set_dat_dir_provider(self.case_dat_dir)
        self._refresh_start_btn()
    
    def set_config(self, config: Config):
        """
        设置配置
        
        Args:
            config: 配置对象
        """
        self.config = config
        self._config_available = True
        self._refresh_start_btn()
        
        # 加载用例列表
        self.case_table.clear_cases()
        for case in config.cases:
            self.case_table.add_case(case.name)

    def set_config_available(self, available: bool, reason: str = ""):
        """配置是否可用：不可用时禁用“开始执行”并用 tooltip 说明原因"""
        self._config_available = bool(available)
        if reason:
            self._no_config_reason = reason
        self._refresh_start_btn()

    def start_case_scan(self):
        """切到执行页时后台预扫描 generate_dir，运行前就显示用例与就绪状态"""
        if self.config is None or not self._config_available:
            return
        if self.worker and self.worker.isRunning():
            return
        if self._scan_worker and self._scan_worker.isRunning():
            return

        generate_dir = getattr(self.config.paths, "generate_dir", None)
        if not generate_dir:
            return

        self._scan_worker = CaseScanWorker(Path(generate_dir), self)
        self._scan_worker.scanned.connect(self.on_scan_finished)
        self.stats_label.setText("正在扫描用例…")
        self._scan_worker.start()

    def on_scan_finished(self, rows: list):
        """预扫描完成：填充用例表并标注“就绪/缺 .out”"""
        if self.worker and self.worker.isRunning():
            return  # 已在执行，不要覆盖运行中的状态表

        self.case_table.clear_cases()
        ready = 0
        missing = 0
        for name, status, message in rows:
            self.case_table.add_case(name, status=status, message=message)
            if status == "ready":
                ready += 1
            elif status == "missing_out":
                missing += 1

        total = len(rows)
        if total:
            self.stats_label.setText(
                f"预扫描: {total} 个用例（就绪 {ready}，缺 .out {missing}）")
        else:
            self.stats_label.setText("预扫描: 工作区中没有发现用例")

    def shutdown_background_tasks(self):
        """关闭窗口前停掉后台预扫描，避免线程未结束就销毁控件"""
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait(2000)

    def _refresh_start_btn(self):
        """按“配置可用 + 未在执行”刷新开始按钮状态"""
        running = bool(self.worker and self.worker.isRunning())
        self.start_btn.setEnabled(self._config_available and not running)
        self.start_btn.setToolTip("" if self._config_available else self._no_config_reason)

    def show_error_bar(self, message: str):
        """显示顶部错误条（可关闭，带“查看日志”）"""
        self.error_label.setText(message)
        self.error_bar.setVisible(True)

    def hide_error_bar(self):
        """关闭顶部错误条"""
        self.error_bar.setVisible(False)

    def case_dat_dir(self, case_name: str) -> Optional[Path]:
        """用例的 dat 结果目录（优先 <结果根>/<时间戳>/<用例>/memory）"""
        if self.config is None:
            return None
        base = self.config.paths.results_dir
        stems = []
        if self.run_timestamp:
            stems.append(base / self.run_timestamp / case_name)
        stems.append(base / case_name)
        for stem in stems:
            if (stem / "memory").is_dir():
                return stem / "memory"
            if stem.is_dir():
                return stem
        return stems[0]

    def _results_dir(self) -> Optional[Path]:
        """本次执行的结果目录（没有时间戳时回退到结果根目录）"""
        if self.config is None:
            return None
        base = self.config.paths.results_dir
        if self.run_timestamp:
            candidate = base / self.run_timestamp
            if candidate.exists():
                return candidate
        return base

    def _update_result_hint(self):
        """执行结束后在按钮下方展示结果目录，便于直接打开"""
        target = self._results_dir()
        if target is None:
            self.result_hint.setVisible(False)
            return
        self.result_hint_label.setText(f"结果目录：{target}")
        self.result_hint.setVisible(True)

    def on_log_entry(self, message: str, level: str):
        """worker 带级别的日志，转发给主窗口日志页"""
        self.log_entry.emit(message, level)
    
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
    
    def _set_stage_item_enabled(self, stage: str, enabled: bool):
        """启用/禁用起始阶段下拉里的某一项"""
        index = self.start_stage_combo.findData(stage)
        if index < 0:
            return
        item = self.start_stage_combo.model().item(index)
        if item is not None:
            item.setEnabled(enabled)

    def _select_stage(self, stage: str):
        """选中起始阶段（该项禁用时也允许程序设置为当前值）"""
        index = self.start_stage_combo.findData(stage)
        if index >= 0:
            self.start_stage_combo.setCurrentIndex(index)

    def _update_execution_options(self):
        """按已检测到的阶段限制可选起始阶段，并默认选中合适项"""
        allowed = {
            "generate": ("generate",),
            "build": ("generate", "build"),
            "test": ("generate", "build", "test"),
            "unknown": ("generate", "build", "test"),
        }.get(self.current_stage, ("generate", "build", "test"))

        for stage in STAGE_ORDER:
            self._set_stage_item_enabled(stage, stage in allowed)

        if self.current_stage in ("build", "test"):
            self._select_stage(self.current_stage)
        elif self.current_stage == "generate":
            self._select_stage("generate")

    def _get_selected_stage(self) -> str:
        """获取选中的起始阶段"""
        return self.start_stage_combo.currentData() or "generate"

    def on_resume_checkbox_changed(self, state):
        """断点续测复选框状态改变"""
        self.resume_batch_spin.setEnabled(state == Qt.Checked)
        if state == Qt.Checked:
            # 断点续测只跑测试，自动把起始阶段切到“测试”
            self._set_stage_item_enabled("test", True)
            self._select_stage("test")
    
    def start_execution(self):
        """开始执行"""
        if self.config is None:
            warning(
                self, "无法开始执行",
                format_error(
                    "尚未加载配置",
                    action="请先在“配置”页选择目录并保存，或通过“文件 → 打开配置...”加载"))
            return
        
        # 获取选中的起始阶段
        start_stage = self._get_selected_stage()
        
        # 验证是否可以执行
        if start_stage == "test" and self.current_stage != "test":
            warning(
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
        
        self._reset_progress(start_stage)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stats_label.setText("执行中...")
        
        # 重置硬件错误标志
        self.hardware_error_occurred = False
        self.failed_batch_number = 0
        self.stopping = False
        self.stopped = False

        # 新一轮执行：收起上一轮的错误条与结果提示
        self.hide_error_bar()
        self.result_hint.setVisible(False)
        
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
        self.worker.stage_progress.connect(self.on_stage_progress)
        self.worker.test_batch_started.connect(self.on_test_batch_started)
        self.worker.case_list_loaded.connect(self.on_case_list_loaded)
        self.worker.case_started.connect(self.on_case_started)
        self.worker.case_finished.connect(self.on_case_finished)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.log_entry.connect(self.on_log_entry)
        self.worker.hardware_error.connect(self.on_hardware_error)
        self.worker.retry_attempt.connect(self.on_retry_attempt)
        self.worker.finished.connect(self.on_execution_finished)
        self.worker.start()
    
    def stop_execution(self):
        """停止执行"""
        if self.worker and self.worker.isRunning():
            # 先给出立即反馈，再调用可能阻塞的 stop()（内部会 terminate DSS 进程）
            self.stopping = True
            self.stop_btn.setEnabled(False)
            self.stats_label.setText("正在停止…")
            self.stats_label.repaint()
            self.worker.stop()
    
    def _reset_progress(self, start_stage: str):
        """开始新一轮执行：按起始阶段重置步骤条与总进度（不回退从 0 开始）"""
        self._active_stages = stages_from(start_stage)
        self._stage_percent = {s: 0 for s in STAGE_ORDER}
        self._progress_floor = 0
        for stage in STAGE_ORDER:
            if stage in self._active_stages:
                self._apply_step_state(stage, "pending")
            else:
                self._apply_step_state(stage, "skipped")
        self.progress_bar.setValue(0)
        self._test_batch = 0
        self._test_batch_total = 0
        self._current_case = ""
        self._test_elapsed.start()
        self._test_timer.start()
        self._update_test_detail()

    def _apply_step_state(self, stage: str, state: str):
        """更新某个步骤的状态（pending/running/done/failed/stopped/skipped）"""
        self._step_states[stage] = state
        label = self.step_labels.get(stage)
        if label is None:
            return
        icon = STEP_ICONS.get(state, "○")
        color = STEP_COLORS.get(state, "#888888")
        weight = "bold" if state == "running" else "normal"
        label.setText(f"{icon} {STAGE_NAMES[stage]}")
        label.setStyleSheet(
            f"color: {color}; font-weight: {weight};"
            "border: 1px solid #DDDDDD; border-radius: 10px; padding: 2px 8px;")
        label.setProperty("stepState", state)

    def on_stage_progress(self, stage: str, percent: int, message: str):
        """阶段内进度：只更新该阶段百分比，再按权重汇总成总进度"""
        if stage in self._stage_percent:
            self._stage_percent[stage] = max(self._stage_percent[stage], percent)
        if percent >= 100:
            self._apply_step_state(stage, "done")
        else:
            self._apply_step_state(stage, "running")
        self.stats_label.setText(message)
        self._refresh_total_progress()

    def _refresh_total_progress(self):
        """总进度：加权汇总且只增不减（停止时不会回跳）"""
        value = compute_weighted_progress(self._stage_percent, self._active_stages)
        value = max(self._progress_floor, value)
        self._progress_floor = value
        self.progress_bar.setValue(value)

    def on_test_batch_started(self, current: int, total: int):
        """测试批次开始：记录“第 x/N 批”，用于测试阶段明细"""
        self._test_batch = current
        self._test_batch_total = total
        self._update_test_detail()

    def _update_test_detail(self):
        """刷新测试阶段明细：第 x/N 批 | 当前用例 | 已用时间"""
        parts = []
        if self._test_batch_total > 0:
            parts.append(f"第 {self._test_batch}/{self._test_batch_total} 批")
        if self._current_case:
            parts.append(f"当前用例: {self._current_case}")
        if self._test_elapsed.isValid():
            seconds = self._test_elapsed.elapsed() / 1000.0
            if seconds < 60:
                parts.append(f"已用 {seconds:.1f}s")
            else:
                parts.append(f"已用 {int(seconds // 60)}m{int(seconds % 60)}s")
        self.test_detail_label.setText(" | ".join(parts))
        self.test_detail_label.setVisible(bool(parts))

    def on_case_list_loaded(self, case_names: list):
        """
        用例列表加载完成处理

        Args:
            case_names: 可测试用例名称列表（有 .out 文件的工程）
        """
        # 如果不是断点续测，清空并重新加载
        if not self.resume_checkbox.isChecked():
            self.case_table.clear_cases()

            # 添加可测试的用例
            for name in case_names:
                self.case_table.add_case(name, "pending")

            # 将工作空间中未编译的工程也加入列表，标记为 skipped，
            # 避免它们从界面消失（用户刷新后能看到全部工程）
            if self.config:
                generate_dir = self.config.paths.generate_dir
                if generate_dir.exists():
                    for d in sorted(generate_dir.iterdir()):
                        if d.is_dir() and d.name != ".metadata" and (d / ".project").exists():
                            if d.name not in case_names:
                                self.case_table.add_case(d.name, "skipped")
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
        self._current_case = case_name
        self._update_test_detail()
        self.log_message.emit(f"开始执行用例: {case_name}")
    
    def on_case_finished(self, case_name: str, status: str, duration: float):
        """
        用例完成处理
        
        Args:
            case_name: 用例名称
            status: 状态
            duration: 耗时(秒)
        """
        duration_str = "--" if status == "skipped" else f"{duration:.1f}s"
        self.case_table.update_case(case_name, status=status, duration=duration_str)
        
        # 更新统计（停止收尾期间保留"正在停止…"文案，由进度信号驱动）
        if not self.stopping:
            completed = self.case_table.get_completed_count()
            total = len(self.case_table.get_all_cases())
            success = self.case_table.get_success_count()
            failed = self.case_table.get_failed_count()
            skipped = self.case_table.get_skipped_count()
            
            self.stats_label.setText(
                f"进度: {completed}/{total} | 成功: {success} | 失败: {failed} | 跳过: {skipped}"
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

    def on_retry_attempt(self, batch_number: int, retry_count: int, max_retries: int):
        """
        重试尝试处理

        Args:
            batch_number: 重试的批次号
            retry_count: 当前重试次数
            max_retries: 最大重试次数（0=不限制）
        """
        if max_retries > 0:
            self.log_message.emit(f"第 {batch_number} 批自动重连中... ({retry_count}/{max_retries})")
            self.stats_label.setText(f"自动重连中... (第 {batch_number} 批, {retry_count}/{max_retries})")
        else:
            self.log_message.emit(f"第 {batch_number} 批自动重连中... (第 {retry_count} 次)")
            self.stats_label.setText(f"自动重连中... (第 {batch_number} 批, 第 {retry_count} 次)")

    def on_hardware_error(self, batch_number: int, error_message: str):
        """
        硬件连接错误处理

        Args:
            batch_number: 失败的批次号
            error_message: 错误信息
        """
        self.hardware_error_occurred = True
        self.failed_batch_number = batch_number

        # 如果启用了自动重连且重试已用尽，或未启用自动重连，显示对话框
        # 此时 executor 已经放弃重试，需要用户手动干预
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
        self._refresh_start_btn()
        self.stop_btn.setEnabled(False)
        self.stopping = False

        worker = self.worker
        stopped = bool(worker and getattr(worker, "stop_requested", False))
        self.stopped = stopped
        self._test_timer.stop()
        self._update_test_detail()

        running_stages = [s for s in self._active_stages if self._step_states.get(s) == "running"]

        if stopped:
            for stage in running_stages:
                self._apply_step_state(stage, "stopped")
        elif success:
            for stage in self._active_stages:
                self._apply_step_state(stage, "done")
        else:
            for stage in running_stages:
                self._apply_step_state(stage, "failed")

        if stopped:
            # 停止不是失败：保留工作线程给出的摘要（已停止（完成 x/N）| 成功/失败/跳过）
            summary = getattr(worker, "final_summary", "") or "已停止"
            self.stats_label.setText(summary)
        elif success:
            self._progress_floor = 100
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

            # 顶部错误条：一句话原因 + 结果路径 + 建议动作，堆栈只进日志页
            if self.hardware_error_occurred:
                reason = "硬件连接中断，测试未能完成"
            else:
                reason = getattr(worker, "final_summary", "") or "测试执行失败"
            target = self._results_dir()
            self.show_error_bar(format_error(
                reason,
                path=target,
                action="请点击“查看日志”定位具体原因，修正后重新执行"))

        # 执行结束都给出结果目录入口；失败时错误条同时可见
        self._update_result_hint()
        self.execution_finished.emit(success)

    def _recover_timestamp_from_results(self) -> Optional[str]:
        """
        从已有的结果目录恢复时间戳
        
        在断点续测时，如果时间戳丢失，尝试从以下位置恢复：
        1. 已有的结果目录 (results)
        2. 已有的日志目录 (logs/dss)
        3. full_regr.json 配置文件
        
        Returns:
            恢复的时间戳字符串，如果无法恢复则返回 None
        """
        from pathlib import Path
        
        # 方法1: 从结果目录获取最新的时间戳（配置的导出根目录 + 旧 5_result_dat 兼容）
        result_dirs = []
        if self.config is not None:
            result_dirs.append(self.config.paths.results_dir)
        else:
            result_dirs.append(app_path("results"))
        legacy_dir = app_path("5_result_dat")
        if legacy_dir.exists():
            result_dirs.append(legacy_dir)
        for result_dir in result_dirs:
            if not result_dir.exists():
                continue
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
        log_dir = app_path("logs") / "dss"
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
        config_file = app_path("full_regr.json")
        if config_file.exists():
            try:
                import json
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                cases = config.get("cases", [])
                if cases:
                    # 从第一个用例的 dat_dir 提取时间戳（正/反斜杠、相对/绝对路径都兼容）
                    dat_dir = to_posix(cases[0].get("dat_dir", ""))
                    import re
                    match = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2})", dat_dir)
                    if match:
                        timestamp = match.group(1)
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
                # 扫描工程目录下的子目录作为用例（排除 .metadata 目录）
                case_dirs = [d for d in generate_dir.iterdir() if d.is_dir() and d.name != ".metadata"]
                for case_dir in sorted(case_dirs):
                    # 检查是否是有效的工程目录（包含.project文件或.out文件）
                    has_project = any(case_dir.rglob(".project"))
                    has_out = any(case_dir.rglob("*.out"))
                    if has_project or has_out:
                        self.case_table.add_case(case_dir.name, "pending")

        # 更新统计显示
        total = len(self.case_table.get_all_cases())
        self.stats_label.setText(f"已刷新: {total} 个用例")
