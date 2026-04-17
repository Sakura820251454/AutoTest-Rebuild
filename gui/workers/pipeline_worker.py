#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流水线执行工作线程

在后台执行测试流水线，调用与命令行相同的业务逻辑
"""

import sys
import tempfile
import json
import os
import time
import logging
from pathlib import Path
from typing import Optional, List
from enum import Enum

from PyQt5.QtCore import QThread, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.pipeline import Step
from src.generator import ProjectGenerator
from src.builder import ProjectBuilder
from src.executor import TestExecutor
from src.logger import setup_logger, get_logger, get_log_dir


class GUILogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到 GUI"""
    
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def emit(self, record):
        """发送日志记录到 GUI"""
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception:
            pass


class PipelineWorker(QThread):
    """流水线执行工作线程"""

    progress_updated = pyqtSignal(int, str)  # 进度更新(百分比, 消息)
    case_list_loaded = pyqtSignal(list)  # 用例列表加载完成(用例名称列表)
    case_started = pyqtSignal(str)  # 用例开始
    case_finished = pyqtSignal(str, str, float)  # 用例完成(名称, 状态, 耗时)
    log_message = pyqtSignal(str)  # 日志消息
    hardware_error = pyqtSignal(int, str)  # 硬件连接错误(批次号, 错误信息)
    finished = pyqtSignal(bool)  # 执行完成(成功/失败)

    def __init__(self, config: Config, start_stage: str, start_batch: int = 0, resume_test: bool = False, run_timestamp: Optional[str] = None):
        super().__init__()

        self.config = config
        self.start_stage = start_stage
        self.start_batch = start_batch
        self.resume_test = resume_test
        self.run_timestamp = run_timestamp  # 用于断点续测保持时间戳一致
        self.is_running = True

    def run(self):
        """执行流水线"""
        try:
            # 初始化日志系统
            log_dir = setup_logger()
            logger = get_logger(__name__)

            # 添加自定义日志处理器，将日志发送到 GUI
            gui_handler = GUILogHandler(self.log_message)
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
                    self.progress_updated.emit(100, "执行完成")
                    self.finished.emit(True)
                elif not self.is_running:
                    self.log_message.emit("执行被取消")
                    self.finished.emit(False)
                else:
                    self.progress_updated.emit(0, "执行失败")
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
            self.log_message.emit(f"执行错误: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
            self.finished.emit(False)

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
                "ccs_workspace": str(self.config.paths.ccs_workspace),
            },

            # 工具路径配置（新格式）
            "tools": {
                "ccs_executable": str(self.config.paths.ccs_executable),
                "ccs_dss": str(self.config.paths.ccs_dss),
                "ccxml": str(self.config.paths.ccxml),
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
                "timeout": self.config.test.test_timeout,
                "test_batch_size": self.config.test.test_batch_size,
                "result_addr": self.config.test.result_addr,
                "success_val": self.config.test.success_val,
                "error_val": self.config.test.error_val,
                "device": self.config.test.device,
                "cpu": self.config.test.cpu,
                "do_test": self.config.test.do_test,
            },

            # 内存段配置
            "memory_segments": {
                "segments": [
                    {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width}
                    for s in self.config.memory_segments
                ]
            },

            # 用例配置
            "cases": [
                {
                    "name": case.name,
                    "out": str(case.out),
                    "dat_dir": case.dat_dir if case.dat_dir else f"5_result_dat/{case.name}",
                    "segments": [
                        {"name": s.name, "addr": s.addr, "len": s.len, "width": s.width}
                        for s in (case.segments if case.segments else self.config.memory_segments)
                    ]
                }
                for case in self.config.cases
            ]
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

            # 计算总用例数
            total_cases = len(config.cases)
            completed_cases = 0

            # 执行每个步骤
            for step in steps:
                if not self.is_running:
                    return False

                self.log_message.emit(f"执行步骤: {step.value}")
                self.progress_updated.emit(
                    int(completed_cases / total_cases * 100) if total_cases > 0 else 0,
                    f"正在执行: {step.value}"
                )

                if step == Step.GENERATE:
                    if not self._execute_generate(config):
                        return False
                elif step == Step.BUILD:
                    if not self._execute_build(config):
                        return False
                elif step == Step.TEST:
                    success_count = self._execute_test(config)
                    completed_cases += success_count

            return True

        except Exception as e:
            self.log_message.emit(f"执行错误: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
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

            # 调用真实的生成器
            generator = ProjectGenerator(config)
            results = generator.generate()

            # 检查生成结果
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)

            if total_count > 0:
                self.log_message.emit(f"工程生成完成: {success_count}/{total_count} 成功")
            else:
                self.log_message.emit("工程生成完成")

            # 只要有成功的就返回 True（与命令行逻辑一致）
            return success_count > 0 or total_count == 0

        except Exception as e:
            self.log_message.emit(f"生成失败: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
            return False

    def _execute_build(self, config: Config) -> bool:
        """
        执行构建步骤 - 调用真实的构建逻辑

        Args:
            config: 配置对象

        Returns:
            是否成功
        """
        try:
            self.log_message.emit("开始构建工程...")

            # 调用真实的构建器
            builder = ProjectBuilder(config)
            results = builder.build_all()

            # 检查构建结果
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)

            if total_count > 0:
                self.log_message.emit(f"工程构建完成: {success_count}/{total_count} 成功")
            else:
                self.log_message.emit("工程构建完成")

            # 只要有成功的就返回 True（与命令行逻辑一致）
            return success_count > 0 or total_count == 0

        except Exception as e:
            self.log_message.emit(f"构建失败: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
            return False

    def _execute_test(self, config: Config) -> int:
        """
        执行测试步骤 - 调用真实的测试逻辑

        Args:
            config: 配置对象

        Returns:
            成功执行的用例数
        """
        # 使用类属性来跟踪进度
        self._test_success_count = 0
        self._test_total_cases = 0
        self._test_completed_cases = 0

        try:
            self.log_message.emit("开始执行测试...")

            # 调用真实的测试执行器
            # 如果是断点续测，使用原来的时间戳保持结果文件一致
            executor = TestExecutor(config, run_timestamp=self.run_timestamp)
            
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
                elif status == "Skipped":
                    gui_status = "skipped"
                else:
                    gui_status = "failed"
                
                self._test_completed_cases += 1
                
                # 更新进度
                if self._test_total_cases > 0:
                    progress = int(self._test_completed_cases / self._test_total_cases * 100)
                    self.progress_updated.emit(
                        progress,
                        f"测试进度: {self._test_completed_cases}/{self._test_total_cases} ({progress}%)"
                    )
                self._handle_case_finished(name, gui_status, duration)
            
            def on_hardware_error(batch_number, error_message):
                # 触发硬件错误信号
                self.hardware_error.emit(batch_number, error_message)
            
            executor.on_case_started = on_case_started
            executor.on_case_finished = on_case_finished
            executor.on_hardware_error = on_hardware_error

            # 优先使用已存在的 full_regr.json，避免覆盖用户修改的配置
            test_config_path = None
            existing_config = Path("full_regr.json")
            
            if existing_config.exists():
                test_config_path = str(existing_config)
                self.log_message.emit(f"使用现有测试配置: {test_config_path}")
                # 如果配置中没有用例，从测试配置文件中获取用例列表
                if not config.cases:
                    import json
                    with open(test_config_path, "r", encoding="utf-8") as f:
                        test_config = json.load(f)
                    case_names = [case["name"] for case in test_config.get("cases", [])]
                    self._test_total_cases = len(case_names)
                    if case_names:
                        self.log_message.emit(f"发现 {len(case_names)} 个用例")
                        self.case_list_loaded.emit(case_names)
            else:
                # 如果不存在 full_regr.json，则生成新的
                if not config.cases:
                    self.log_message.emit("从工作空间获取用例列表...")
                test_config_path = executor.generate_test_config()
                if test_config_path and Path(test_config_path).exists():
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
            # 最终进度更新
            if self._test_total_cases > 0:
                self.progress_updated.emit(
                    100,
                    f"测试完成: {self._test_success_count}/{self._test_total_cases} 成功"
                )

            self.log_message.emit(f"测试执行完成: {self._test_success_count}/{len(results)} 成功")

        except Exception as e:
            self.log_message.emit(f"测试执行失败: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())

        return self._test_success_count
    
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
            self.log_message.emit(f"用例错误: {case_name} - 硬件连接断开")
        elif status == "skipped":
            self.log_message.emit(f"用例跳过: {case_name}")
        else:
            self.log_message.emit(f"用例失败: {case_name} - {status}")
        
        self.case_finished.emit(case_name, status, duration)

    def stop(self):
        """停止执行"""
        self.is_running = False
        self.log_message.emit("正在停止执行...")
