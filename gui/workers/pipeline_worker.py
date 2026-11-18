#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流水线执行工作线程

在后台执行测试流水线，调用与命令行相同的业务逻辑

@input Config、起始阶段、断点续测参数
@output stage_progress/test_batch_started/case_finished/log_message/log_entry/finished 等信号
@pos GUI 与业务逻辑之间的线程边界；日志按真实级别上报（失败/堆栈为 ERROR）

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
import tempfile
import json
import os
import time
import logging
import traceback
from pathlib import Path
from typing import Optional, List, Tuple
from enum import Enum

from PyQt5.QtCore import QThread, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.pipeline import Step
from src.generator import ProjectGenerator
from src.builder import ProjectBuilder
from src.executor import TestExecutor
from src.logger import setup_logger, get_logger, get_log_dir
from src.runtime_paths import to_posix


class GUILogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到 GUI"""
    
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def emit(self, record):
        """发送日志记录到 GUI（带真实级别）

        注意两点：
        1. 控制台 ColoredFormatter 会给 record.levelname 拼上 ANSI 颜色码，
           这里必须用 levelno 还原级别，否则 ERROR 会被当成未知级别显示成 INFO；
        2. 只用 record.getMessage()，堆栈由 worker 单独按行发送，
           用 self.format(record) 会把 traceback 再拼一遍造成重复。
        """
        try:
            msg = record.getMessage()
            self.log_signal.emit(msg, logging.getLevelName(record.levelno))
        except Exception:
            pass


def format_execution_summary(stopped, success, failed, skipped, total,
                             encrypt_failure_count=0, failure_reasons=None):
    """
    构造测试结束摘要

    返回 (进度百分比, 摘要文本)。停止与正常完成分开：停止时明确显示"已停止"，
    并给出 成功/失败/跳过 三个口径（分母为用例总数）；正常跑完且无失败/跳过时
    文本与原来保持一致。失败原因直接拼进摘要，不用翻日志。
    """
    executed = success + failed
    if stopped:
        percent = int(executed / total * 100) if total else 0
        text = f"已停止（完成 {success}/{total}） | 成功: {success} | 失败: {failed} | 跳过: {skipped}"
    else:
        percent = 100
        text = f"测试完成: {success}/{total} 成功"
        if failed or skipped:
            text += f" | 失败: {failed} | 跳过: {skipped}"

    if encrypt_failure_count:
        text += f" | FLASH 加密失败 {encrypt_failure_count} 处"

    if failure_reasons:
        preview = "；".join(failure_reasons[:3])
        if len(failure_reasons) > 3:
            preview += f"；等共 {len(failure_reasons)} 项"
        text += f"；失败原因: {preview}"

    return percent, text


class PipelineWorker(QThread):
    """流水线执行工作线程"""

    stage_progress = pyqtSignal(str, int, str)  # 阶段内进度(阶段, 0-100, 消息)
    test_batch_started = pyqtSignal(int, int)  # 测试批次开始(第 x 批, 共 N 批)
    case_list_loaded = pyqtSignal(list)  # 用例列表加载完成(用例名称列表)
    case_started = pyqtSignal(str)  # 用例开始
    case_finished = pyqtSignal(str, str, float)  # 用例完成(名称, 状态, 耗时)
    log_message = pyqtSignal(str)  # 日志消息（INFO）
    log_entry = pyqtSignal(str, str)  # 日志消息(文本, 级别)
    hardware_error = pyqtSignal(int, str)  # 硬件连接错误(批次号, 错误信息)
    retry_attempt = pyqtSignal(int, int, int)  # 重试尝试(批次号, 当前次数, 最大次数)
    finished = pyqtSignal(bool)  # 执行完成(成功/失败)

    def __init__(self, config: Config, start_stage: str, start_batch: int = 0, resume_test: bool = False, run_timestamp: Optional[str] = None):
        super().__init__()

        self.config = config
        self.start_stage = start_stage
        self.start_batch = start_batch
        self.resume_test = resume_test
        self.run_timestamp = run_timestamp  # 用于断点续测保持时间戳一致
        self.is_running = True
        self._executor: Optional[TestExecutor] = None  # 测试执行器引用
        self.stop_requested = False  # 用户是否点了停止
        self.stopped = False  # 本次执行是否真的因停止而提前结束
        self.final_summary = ""  # 测试结束摘要（停止/完成）
        self._test_success_count = 0
        self._test_failed_count = 0
        self._test_skipped_count = 0
        self._test_total_cases = 0
        self._test_completed_cases = 0

    def run(self):
        """执行流水线"""
        try:
            # 初始化日志系统
            log_dir = setup_logger()
            logger = get_logger(__name__)

            # 添加自定义日志处理器，将日志（含真实级别）发送到 GUI
            gui_handler = GUILogHandler(self.log_entry)
            gui_handler.setLevel(logging.INFO)
            logging.getLogger().addHandler(gui_handler)

            logger.info("=" * 60)
            logger.info("AutoTest 流水线启动")
            logger.info(f"日志目录: {log_dir}")
            logger.info("=" * 60)

            # 根据起始阶段确定要执行的步骤
            steps = self._get_steps()

            self.log_message.emit(f"开始执行，起始阶段: {self.start_stage}")
            self.log_message.emit(f"执行步骤: {[s.value for s in steps]}")
            logger.info(f"开始执行，起始阶段: {self.start_stage}")
            logger.info(f"执行步骤: {[s.value for s in steps]}")

            # 临时保存配置
            config_path = self._save_temp_config()

            try:
                # 执行流水线
                success = self._execute_pipeline(config_path, steps)

                if success and self.is_running:
                    self.finished.emit(True)
                elif not self.is_running:
                    self.log_message.emit("执行被取消")
                    self.finished.emit(False)
                else:
                    # 失败时保留当前进度，不回跳到 0（避免误导为“什么都没跑”）
                    self.finished.emit(False)

            finally:
                # 移除 GUI 日志处理器
                logging.getLogger().removeHandler(gui_handler)
                # 清理临时文件
                try:
                    os.remove(config_path)
                except:
                    pass

        except Exception as e:
            self._emit_exception("执行错误", e)
            self.finished.emit(False)

    def _emit_error(self, message: str):
        """失败信息按 ERROR 级别送到日志页"""
        self.log_entry.emit(message, "ERROR")

    def _emit_exception(self, message: str, exc: Exception):
        """异常：一句话原因 + 堆栈，全部按 ERROR 写日志页（不弹 Python 原文）"""
        self.log_entry.emit(f"{message}: {type(exc).__name__}: {exc}", "ERROR")
        self.log_entry.emit(traceback.format_exc().rstrip(), "ERROR")
        logging.getLogger(__name__).error(message, exc_info=True)

    def _get_steps(self) -> List[Step]:
        """
        根据起始阶段获取执行步骤

        Returns:
            步骤列表
        """
        if self.start_stage == "generate":
            return [Step.GENERATE, Step.BUILD, Step.TEST]
        elif self.start_stage == "build":
            return [Step.BUILD, Step.TEST]
        else:  # test
            return [Step.TEST]

    def _save_temp_config(self) -> str:
        """
        保存临时配置文件

        Returns:
            配置文件路径
        """
        config_dict = self._config_to_dict()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
            return f.name

    def _config_to_dict(self) -> dict:
        """
        将配置对象转换为字典

        Returns:
            配置字典
        """
        # 获取生成模式
        generation_mode = self.config._raw.get("generation", {}).get("generation_mode", "template")

        return {
            # 路径配置（新格式）
            "paths": {
                "template_dir": str(self.config.paths.template_dir),
                "source_dir": str(self.config.paths.source_dir),
                "generate_dir": str(self.config.paths.generate_dir),
                "result_dir": str(self.config.paths.result_dir),
                "results_dir": str(self.config.paths.results_dir),
                # 工作区单一真源：ccs_workspace 始终跟随 generate_dir
                "ccs_workspace": str(self.config.paths.generate_dir),
            },

            # 工具路径配置（新格式）
            "tools": {
                "ccs_executable": str(self.config.paths.ccs_executable),
                "ccs_dss": str(self.config.paths.ccs_dss),
                "ccxml": str(self.config.paths.ccxml),
                "gel_file": str(self.config.paths.gel_file) if self.config.paths.gel_file else "",
            },

            # 构建设置
            "build": {
                "build_config": self.config.build.build_config,
                "build_timeout": self.config.build.build_timeout,
                "max_build_threads": self.config.build.max_build_threads,
                "do_generate": self.config.build.do_generate,
                "do_build": self.config.build.do_build,
            },

            # 工程生成模式
            "generation": {
                "generation_mode": generation_mode
            },

            # 测试设置
            "test": {
                "test_timeout": self.config.test.test_timeout,
                "test_batch_size": self.config.test.test_batch_size,
                "result_addr": self.config.test.result_addr,
                "success_val": self.config.test.success_val,
                "error_val": self.config.test.error_val,
                "device": self.config.test.device,
                "cpu": self.config.test.cpu,
                "do_test": self.config.test.do_test,
                "auto_resume": self.config.test.auto_resume,
                "max_retries": self.config.test.max_retries,
                "retry_delay": self.config.test.retry_delay,
                "encrypt_flash_dat": self.config.test.encrypt_flash_dat,
                "flash_encrypt_verify": self.config.test.flash_encrypt_verify,
                "copy_project": self.config.test.copy_project,
                "result_check": {
                    "method": self.config.result_check.method,
                    "success_label": self.config.result_check.success_label,
                    "fail_label": self.config.result_check.fail_label,
                    "check_addr": self.config.result_check.check_addr,
                    "check_width": self.config.result_check.check_width,
                    "success_val": self.config.result_check.success_val,
                    "fail_val": self.config.result_check.fail_val,
                    "expression": self.config.result_check.expression,
                    "expected_val": self.config.result_check.expected_val,
                },
            },

            # 内存段配置
            "memory_segments": {
                "segments": [
                    {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width, "page": s.page}
                    for s in self.config.memory_segments
                ],
                "export_points": [
                    {"when": p.when, "enabled": p.enabled, "subdir": p.subdir}
                    for p in self.config.export_points
                ],
            },

            # 用例配置
            "cases": [
                {
                    "name": case.name,
                    "out": to_posix(case.out),
                    "dat_dir": to_posix(case.dat_dir) if case.dat_dir else to_posix(
                        self.config.paths.results_dir / self.run_timestamp / case.name),
                    "is_flash": case.is_flash,
                    "segments": [
                        {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width, "page": s.page}
                        for s in (case.segments if case.segments else self.config.memory_segments)
                    ],
                    "export_points": [
                        {"when": p.when, "enabled": p.enabled, "subdir": p.subdir}
                        for p in (case.export_points if case.export_points else self.config.export_points)
                    ],
                    "result_check": {
                        "method": case.result_check.method,
                        "success_label": case.result_check.success_label,
                        "fail_label": case.result_check.fail_label,
                        "check_addr": case.result_check.check_addr,
                        "check_width": case.result_check.check_width,
                        "success_val": case.result_check.success_val,
                        "fail_val": case.result_check.fail_val,
                        "expression": case.result_check.expression,
                        "expected_val": case.result_check.expected_val,
                    },
                }
                for case in self.config.cases
            ],

            # 日志配置（Config 本身不解析，原样保留，避免临时配置丢字段）
            "log": {
                "log_retention_days": self.config._raw.get("log", {}).get("log_retention_days", 30)
            },
        }

    def _execute_pipeline(self, config_path: str, steps: List[Step]) -> bool:
        """
        执行流水线

        Args:
            config_path: 配置文件路径
            steps: 执行步骤列表

        Returns:
            是否成功
        """
        try:
            # 加载配置
            config = Config.load(config_path)

            # 执行每个步骤；进度按阶段上报，由 GUI 按权重汇总
            stage_labels = {"generate": "生成工程", "build": "构建", "test": "测试"}
            for step in steps:
                if not self.is_running:
                    return False

                stage = step.value
                label = stage_labels.get(stage, stage)
                self.log_message.emit(f"执行步骤: {stage}")
                self.stage_progress.emit(stage, 0, f"正在{label}...")

                if step == Step.GENERATE:
                    if not self._execute_generate(config):
                        return False
                elif step == Step.BUILD:
                    if not self._execute_build(config):
                        return False
                elif step == Step.TEST:
                    test_ok, _success_count = self._execute_test(config)
                    if not test_ok:
                        return False
                else:
                    continue

                # 测试阶段自己按用例上报百分比（停止时不会到 100），这里只收尾前两个阶段
                if step != Step.TEST:
                    self.stage_progress.emit(stage, 100, f"{label}完成")

            return True

        except Exception as e:
            self._emit_exception("执行错误", e)
            return False

    def _execute_generate(self, config: Config) -> bool:
        """
        执行生成步骤 - 调用真实的生成逻辑

        Args:
            config: 配置对象

        Returns:
            是否成功
        """
        try:
            self.log_message.emit("开始生成工程...")
            
            # 检查是否请求停止
            if not self.is_running:
                return False

            # 调用真实的生成器
            generator = ProjectGenerator(config)
            results = generator.generate()

            # 检查生成结果
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)

            if total_count == 0:
                # 工作区不存在 / 没有工程 / 模板源为空，都不能静默当成“生成完成”
                workspace = config.paths.generate_dir
                if not workspace.exists():
                    self._emit_error(f"生成失败：工作区目录不存在，请检查“工作区目录”配置: {workspace}")
                else:
                    self._emit_error(
                        f"生成失败：工作区 {workspace} 中没有找到任何有效工程，请检查工作区目录是否配置正确"
                    )
                return False

            self.log_message.emit(f"工程生成完成: {success_count}/{total_count} 成功")
            return success_count > 0

        except Exception as e:
            self._emit_exception("生成失败", e)
            return False

    def _execute_build(self, config: Config) -> bool:
        """
        执行构建步骤 - 调用真实的构建逻辑，通过回调驱动 GUI 进度

        Args:
            config: 配置对象

        Returns:
            是否成功
        """
        try:
            self.log_message.emit("开始构建工程...")
            self._build_completed = 0
            self._build_total = 0
            self._build_success_count = 0

            # 检查是否请求停止
            if not self.is_running:
                return False

            # 调用真实的构建器
            builder = ProjectBuilder(config)

            # 设置停止检查回调
            def should_stop():
                return not self.is_running
            builder.should_stop = should_stop

            # 设置回调函数用于实时更新 GUI
            def on_project_start(name):
                self.log_message.emit(f"  构建: {name}...")
                if self._build_total > 0:
                    progress = int(self._build_completed / self._build_total * 100)
                    self.stage_progress.emit(
                        "build",
                        progress,
                        f"构建进度: {self._build_completed}/{self._build_total} ({progress}%)"
                    )

            def on_project_finish(name, success, duration_s):
                self._build_completed += 1
                if success:
                    self._build_success_count += 1
                status_icon = "✓" if success else "✗"
                self.log_message.emit(f"  {status_icon} {name} ({duration_s:.1f}s)")
                if self._build_total > 0:
                    progress = int(self._build_completed / self._build_total * 100)
                    self.stage_progress.emit(
                        "build",
                        progress,
                        f"构建进度: {self._build_completed}/{self._build_total} ({progress}%)"
                    )

            builder.on_project_start = on_project_start
            builder.on_project_finish = on_project_finish

            # 先获取工程总数用于进度计算
            workspace = config.paths.generate_dir
            if not workspace.exists():
                self._emit_error(f"构建失败：工作区目录不存在，请检查“工作区目录”配置: {workspace}")
                return False

            projects = builder.find_projects()
            self._build_total = len(projects)
            if not projects:
                self._emit_error(
                    f"构建失败：工作区 {workspace} 中没有任何有效工程（未找到含 .project 的子目录），"
                    f"已中止，避免后续误测旧工程"
                )
                self.stage_progress.emit("build", 0, "构建未执行：工作区中没有工程")
                return False

            results = builder.build_all()

            # 检查构建结果
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)

            self.log_message.emit(f"工程构建完成: {success_count}/{total_count} 成功")

            # 只要有成功的就返回 True（与命令行逻辑一致）
            return success_count > 0

        except Exception as e:
            self._emit_exception("构建失败", e)
            return False

    def _execute_test(self, config: Config) -> Tuple[bool, int]:
        """
        执行测试步骤 - 调用真实的测试逻辑

        Args:
            config: 配置对象

        Returns:
            (是否成功执行测试, 成功用例数)。工作区缺失/无 .out/权限拒绝等“压根没跑起来”
            的情况返回 False，让流水线整体按失败上报，而不是显示“执行完成”。
        """
        # 使用类属性来跟踪进度
        self._test_success_count = 0
        self._test_failed_count = 0
        self._test_skipped_count = 0
        self._test_total_cases = 0
        self._test_completed_cases = 0
        self.final_summary = ""

        try:
            self.log_message.emit("开始执行测试...")

            # 调用真实的测试执行器
            # 如果是断点续测，使用原来的时间戳保持结果文件一致
            executor = TestExecutor(config, run_timestamp=self.run_timestamp)
            self._executor = executor  # 保存引用以便停止
            
            # 设置停止检查回调
            def should_stop():
                return not self.is_running
            
            executor.should_stop = should_stop
            
            # 设置回调函数用于实时更新GUI
            def on_case_started(name):
                self.case_started.emit(name)
                self.log_message.emit(f"开始执行用例: {name}")
            
            def on_case_finished(name, status, duration):
                # 转换状态为GUI格式
                if status == "Success":
                    gui_status = "success"
                    self._test_success_count += 1
                elif status == "ConnectionLost":
                    gui_status = "error"
                    self._test_failed_count += 1
                elif status == "Skipped":
                    gui_status = "skipped"
                    self._test_skipped_count += 1
                else:
                    gui_status = "failed"
                    self._test_failed_count += 1
                
                self._test_completed_cases += 1
                
                # 更新进度（跳过的用例不计入已完成进度，避免停止后直接跳到 100%）
                if self._test_total_cases > 0:
                    executed = self._test_success_count + self._test_failed_count
                    progress = int(executed / self._test_total_cases * 100)
                    if gui_status == "skipped" and self.stop_requested:
                        message = f"正在停止… 已跳过 {self._test_skipped_count}/{self._test_total_cases}"
                    else:
                        message = f"测试进度: {executed}/{self._test_total_cases} ({progress}%)"
                    self.stage_progress.emit("test", progress, message)
                self._handle_case_finished(name, gui_status, duration)

            def on_batch_started(current, total):
                self.test_batch_started.emit(current, total)
            
            def on_hardware_error(batch_number, error_message):
                # 触发硬件错误信号
                self.hardware_error.emit(batch_number, error_message)

            def on_retry(batch_number, retry_count, max_retries):
                # 触发重试信号
                self.retry_attempt.emit(batch_number, retry_count, max_retries)

            executor.on_case_started = on_case_started
            executor.on_case_finished = on_case_finished
            executor.on_batch_started = on_batch_started
            executor.on_hardware_error = on_hardware_error
            executor.on_retry = on_retry

            # 每次都重新生成 full_regr.json，确保配置最新
            if not config.cases:
                self.log_message.emit("从工作空间获取用例列表...")
            test_config_path = executor.generate_test_config()
            if not test_config_path or not Path(test_config_path).exists():
                # 不能拿旧 full_regr.json 继续跑，否则会无声地测旧工程
                workspace = config.paths.generate_dir
                if not workspace.exists():
                    self._emit_error(f"测试中止：工作区目录不存在，请检查“工作区目录”配置: {workspace}")
                else:
                    self._emit_error(
                        f"测试中止：工作区 {workspace} 中没有找到任何 .out 文件，请先构建或检查工作区目录"
                    )
                self.stage_progress.emit("test", 0, "测试未执行：未找到 .out")
                return False, 0

            import json
            with open(test_config_path, "r", encoding="utf-8") as f:
                test_config = json.load(f)
            case_names = [case["name"] for case in test_config.get("cases", [])]
            self._test_total_cases = len(case_names)
            if case_names:
                self.log_message.emit(f"发现 {len(case_names)} 个用例")
                self.case_list_loaded.emit(case_names)
            
            if self._test_total_cases == 0 and config.cases:
                self._test_total_cases = len(config.cases)

            # 支持断点续测
            results = executor.run_all(
                test_config_path=test_config_path,
                start_batch=self.start_batch,
                resume_from_last=self.resume_test
            )

            # 处理测试结果（已经通过回调函数更新了，这里只统计成功数和进度）
            total = self._test_total_cases
            success = self._test_success_count
            failed = self._test_failed_count
            skipped = self._test_skipped_count
            stopped = bool(getattr(executor, "stopped", False))
            self.stopped = stopped

            # FLASH 加密失败必须明确告知（不能只留在滚动日志里，也不能当作成功）
            encrypt_failures = getattr(executor, "encrypt_failures", None) or []
            if encrypt_failures:
                self._emit_error(f"FLASH 段加密失败 {len(encrypt_failures)} 处，相关数据不能直接用于软仿：")
                for line in encrypt_failures:
                    self._emit_error(f"  {line}")

            failure_reasons = getattr(executor, "failure_reasons", None) or []
            if failure_reasons:
                self._emit_error(f"失败原因（{len(failure_reasons)} 项）：")
                for line in failure_reasons:
                    self._emit_error(f"  {line}")

            percent, summary = format_execution_summary(
                stopped, success, failed, skipped, total,
                encrypt_failure_count=len(encrypt_failures),
                failure_reasons=failure_reasons
            )
            self.final_summary = summary
            if total > 0:
                self.stage_progress.emit("test", percent, summary)

            if stopped:
                self.log_message.emit(f"测试已停止: 成功 {success} / 失败 {failed} / 跳过 {skipped}")
            else:
                self.log_message.emit(f"测试执行完成: {success}/{len(results)} 成功")

        except Exception as e:
            self._emit_exception("测试执行失败", e)
            return False, self._test_success_count

        return True, self._test_success_count
    
    def _handle_case_finished(self, case_name: str, status: str, duration: float):
        """
        处理用例完成事件
        
        Args:
            case_name: 用例名称
            status: 状态 (已经是GUI格式: success, error, skipped, failed)
            duration: 耗时
        """
        # 状态已经是GUI使用的格式，直接发送信号
        if status == "success":
            self.log_message.emit(f"用例成功: {case_name} ({duration:.1f}s)")
        elif status == "error":
            self._emit_error(f"用例错误: {case_name} - 硬件连接断开")
        elif status == "skipped":
            self.log_entry.emit(f"用例跳过: {case_name}", "WARNING")
        else:
            self._emit_error(f"用例失败: {case_name} - {status}")
        
        self.case_finished.emit(case_name, status, duration)

    def stop(self):
        """停止执行"""
        self.stop_requested = True
        self.is_running = False
        if self._executor:
            self._executor.stop()
        self.log_message.emit("正在停止执行...")
