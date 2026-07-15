"""
测试执行模块

@input Config, TestCase, MemorySegment (配置和类型)
@input hardware_detector.quick_hardware_check (硬件预检测)
@output TestExecutor类, TestResult类
@pos 核心模块，负责DSS测试执行、结果收集、断点续测、硬件连接检测

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import os
import json
import csv
import shutil
import tempfile
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .config import Config, TestCase, MemorySegment
from .exceptions import (
    TestError,
    DSSNotFoundError,
    TestExecutionError,
)
from .logger import get_logger, LogContext
from .hardware_detector import quick_hardware_check
from . import test_config_generator
from . import report_generator

logger = get_logger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    case_name: str
    status: str
    dat_dir: Optional[Path] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None  # DSS 脚本记录的耗时（毫秒）


class TestExecutor:
    """
    测试执行器
    
    用法：
        executor = TestExecutor(config)
        results = executor.run_all()
        for r in results:
            print(f"{r.case_name}: {r.status}")
    """
    
    def __init__(self, config: Config, run_timestamp: Optional[str] = None):
        self.config = config
        self.dss_exe = config.paths.ccs_dss
        self.ccxml = config.paths.ccxml
        self.device = config.test.device
        self.cpu = config.test.cpu
        self.timeout = config.test.test_timeout
        self.batch_size = config.test.test_batch_size
        self.result_addr = config.test.result_addr
        self.success_val = config.test.success_val
        self.error_val = config.test.error_val
        self.auto_resume = config.test.auto_resume
        self.max_retries = config.test.max_retries
        self.retry_delay = config.test.retry_delay
        
        self.template_path = Path(__file__).parent.parent / "templates" / "dss_test.js.tmpl"
        # 如果提供了时间戳则使用，否则生成新的（用于断点续测时保持时间戳一致）
        self.run_timestamp = run_timestamp if run_timestamp else datetime.now().strftime("%Y-%m-%d-%H-%M")
        
        # 回调函数
        self.on_case_started: Optional[callable] = None
        self.on_case_finished: Optional[callable] = None
        self.on_hardware_error: Optional[callable] = None  # 硬件连接错误回调
        self.on_retry: Optional[callable] = None  # 重试回调 (batch_number, retry_count, max_retries)
        self.should_stop: Optional[callable] = None  # 停止检查回调
        
        # 停止标志
        self._stop_requested = False
        self._current_process: Optional[subprocess.Popen] = None

        # DSS Java 进程环境变量
        self._dss_env = os.environ.copy()
        # DSS 的 print() 输出编码为 UTF-8

        # 直接调用 eclipsec.exe，绕过 dss.bat 和 cmd.exe，避免中文乱码
        # dss.bat 路径: C:/ti/ccs1210/ccs/ccs_base/scripting/bin/dss.bat
        # eclipsec.exe 路径: C:/ti/ccs1210/ccs/eclipse/eclipsec.exe
        self._eclipsec_exe = self.dss_exe.parent / ".." / ".." / ".." / "eclipse" / "eclipsec.exe"
        self._eclipsec_exe = self._eclipsec_exe.resolve()
    
    def validate(self):
        """验证测试环境"""
        if not self.dss_exe.exists():
            raise DSSNotFoundError(str(self.dss_exe))
        if not self.template_path.exists():
            raise TestError(
                f"DSS 模板文件不存在: {self.template_path}",
                error_code=4007,
                details={"template_path": str(self.template_path)}
            )
    
    def stop(self):
        """停止执行"""
        self._stop_requested = True
        if self._current_process:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=5)
            except:
                try:
                    self._current_process.kill()
                except:
                    pass
            self._current_process = None
        logger.info("测试执行已请求停止")

    def generate_test_config(self, output_path: Optional[Path] = None) -> Path:
        """
        从工作空间生成测试配置（代理方法）

        Args:
            output_path: 输出文件路径，默认为 full_regr.json

        Returns:
            生成的配置文件路径
        """
        return test_config_generator.generate_test_config(
            self.config, self.run_timestamp, output_path
        )

    def run_all(self, test_config_path: Optional[Path] = None, 
                start_batch: int = 0,
                resume_from_last: bool = False) -> List[TestResult]:
        """
        执行所有测试
        
        Args:
            test_config_path: 测试配置文件路径，如果为 None 则自动生成
            start_batch: 从第几个批次开始执行（0-based），用于断点续测
            resume_from_last: 是否从上次中断的批次继续（会覆盖 start_batch）
        
        Returns:
            测试结果列表
        """
        with LogContext(logger, "测试执行"):
            self.validate()
            
            if test_config_path is None:
                test_config_path = self.generate_test_config()
            
            # 将字符串路径转换为 Path 对象
            if isinstance(test_config_path, str):
                test_config_path = Path(test_config_path)
            
            if test_config_path is None or not test_config_path.exists():
                logger.error("没有测试配置文件，跳过测试执行")
                return []
            
            with open(test_config_path, "r", encoding="utf-8") as f:
                test_config = json.load(f)
            
            cases = test_config.get("cases", [])
            if not cases:
                logger.warning("测试配置中没有测试用例")
                return []
            
            logger.info(f"共 {len(cases)} 个测试用例")
            
            # 检查是否需要断点续测
            # 注意：如果用户已经指定了 start_batch（>0），则使用用户指定的值
            # 只有 start_batch=0 且 resume_from_last=True 时才自动检测
            if resume_from_last and start_batch == 0:
                detected_batch = self._find_last_completed_batch(cases)
                if detected_batch > 0:
                    start_batch = detected_batch
                    logger.info(f"自动检测到已完成的批次，从第 {start_batch + 1} 批继续执行")
            elif start_batch > 0:
                logger.info(f"使用用户指定的起始批次，从第 {start_batch + 1} 批继续执行")
            
            self._create_output_dirs(cases)
            
            log_dir = Path("6_result_dat_logs") / self.run_timestamp
            log_dir.mkdir(parents=True, exist_ok=True)
            
            batches = self._split_into_batches(cases, self.batch_size)
            logger.info(f"分成 {len(batches)} 批执行 (每批 {self.batch_size} 个)")
            
            # 如果指定了开始批次，跳过前面的
            if start_batch > 0:
                logger.info(f"跳过前 {start_batch} 个批次")
                batches = batches[start_batch:]
            
            console_log = log_dir / "console_all.log"
            all_results: List[TestResult] = []

            # DSS Java 进程的 System.out.println 使用 UTF-8 编码
            # 先写入 UTF-8 BOM（让记事本正确识别编码）
            if not console_log.exists() or console_log.stat().st_size == 0:
                with open(console_log, "wb") as f:
                    f.write(b'\xef\xbb\xbf')

            # 使用二进制模式追加（DSS Java 进程输出 UTF-8 字节流）
            with open(console_log, "ab") as f_out:
                batch_index = 0
                while batch_index < len(batches):
                    batch = batches[batch_index]
                    i = start_batch + 1 + batch_index

                    # 检查是否请求停止
                    if self._stop_requested or (self.should_stop and self.should_stop()):
                        logger.info("检测到停止请求，终止测试执行")
                        self._mark_remaining_batches_as_skipped(batches[batch_index:])
                        break

                    logger.info(f"执行第 {i}/{start_batch + len(batches)} 批 ({len(batch)} 个用例)")

                    # 通知批次中的用例开始
                    logger.info(f"通知批次开始，共 {len(batch)} 个用例")
                    for case in batch:
                        logger.info(f"通知用例开始: {case['name']}")
                        if self.on_case_started:
                            try:
                                self.on_case_started(case["name"])
                                logger.info(f"已通知用例开始: {case['name']}")
                            except Exception as e:
                                logger.error(f"通知用例开始失败: {case['name']}, 错误: {e}")

                    # 重试循环
                    retry_count = 0
                    batch_actually_success = False
                    while True:
                        # 检查是否请求停止
                        if self._stop_requested or (self.should_stop and self.should_stop()):
                            break

                        # 记录 console_all.log 在批次运行前的位置，只检查新内容
                        f_out.flush()
                        console_log_pos = f_out.tell()

                        batch_start_time = time.time()
                        dss_success = self._run_batch(batch, test_config, log_dir, f_out, console_log_pos)
                        batch_end_time = time.time()
                        logger.info(f"第 {i} 批 DSS 执行完成，成功: {dss_success}")

                        # 收集该批次的结果
                        logger.info(f"收集批次结果并通知完成")
                        batch_results = self._collect_batch_results(batch)
                        logger.info(f"批次结果: {len(batch_results)} 个")

                        # 检查 DSS 日志中是否有连接错误（仅检查当前批次的日志）
                        connection_lost = self._check_connection_error_in_log(log_dir, console_log_pos, batch[0]['name'])

                        # 判断批次是否成功
                        batch_actually_success = dss_success and len(batch_results) == len(batch) and not connection_lost

                        if batch_actually_success:
                            # 批次成功，处理结果并跳出重试循环
                            for result in batch_results:
                                all_results.append(result)
                                # 使用 DSS 脚本记录的耗时，如果没有则用批次时间估算
                                if result.duration_ms is not None:
                                    duration = result.duration_ms / 1000.0
                                else:
                                    duration = batch_end_time - batch_start_time
                                logger.info(f"Case finished: {result.case_name} = {result.status}, duration: {duration:.2f}s")
                                if self.on_case_finished:
                                    try:
                                        self.on_case_finished(result.case_name, result.status, duration)
                                    except Exception as e:
                                        logger.error(f"通知用例完成失败: {result.case_name}, 错误: {e}")
                            break

                        # 批次失败
                        logger.error(f"第 {i} 批执行失败（DSS成功: {dss_success}, 结果数: {len(batch_results)}/{len(batch)}, 连接断开: {connection_lost}）")

                        # 判断是否需要重试
                        can_retry = connection_lost and self.auto_resume
                        if can_retry and (self.max_retries == 0 or retry_count < self.max_retries):
                            retry_count += 1
                            logger.warning(f"第 {i} 批将在 {self.retry_delay} 秒后第 {retry_count} 次重试...")

                            # 通知重试回调
                            if self.on_retry:
                                try:
                                    self.on_retry(i, retry_count, self.max_retries)
                                except Exception as e:
                                    logger.error(f"重试回调失败: {e}")

                            # 等待重试间隔（可被停止请求中断）
                            for _ in range(self.retry_delay):
                                if self._stop_requested or (self.should_stop and self.should_stop()):
                                    break
                                time.sleep(1)
                            continue

                        # 不可重试或已达最大重试次数，处理结果并退出
                        if retry_count > 0:
                            logger.error(f"第 {i} 批重试 {retry_count} 次后仍然失败，放弃该批次")
                        else:
                            logger.error(f"第 {i} 批执行失败，停止后续批次")

                        # 处理有结果的用例
                        result_case_names = {r.case_name for r in batch_results}
                        for result in batch_results:
                            all_results.append(result)
                            # 使用 DSS 脚本记录的耗时，如果没有则用批次时间估算
                            if result.duration_ms is not None:
                                duration = result.duration_ms / 1000.0
                            else:
                                duration = batch_end_time - batch_start_time
                            logger.info(f"Case finished: {result.case_name} = {result.status}, duration: {duration:.2f}s")
                            if self.on_case_finished:
                                try:
                                    self.on_case_finished(result.case_name, result.status, duration)
                                except Exception as e:
                                    logger.error(f"通知用例完成失败: {result.case_name}, 错误: {e}")

                        # 处理没有结果的用例
                        for case in batch:
                            if case["name"] not in result_case_names:
                                if connection_lost:
                                    logger.error(f"用例未生成结果文件（硬件断开）: {case['name']}")
                                    status = "ConnectionLost"
                                else:
                                    logger.error(f"用例未生成结果文件，标记为失败: {case['name']}")
                                    status = "Failed"
                                duration = batch_end_time - batch_start_time
                                if self.on_case_finished:
                                    try:
                                        self.on_case_finished(case["name"], status, duration)
                                    except Exception as e:
                                        logger.error(f"通知用例失败失败: {case['name']}, 错误: {e}")

                        # 触发硬件错误回调（通知 GUI）
                        if self.on_hardware_error:
                            try:
                                if connection_lost:
                                    error_msg = f"第 {i} 批执行过程中检测到硬件连接断开（已重试 {retry_count} 次）" if retry_count > 0 else f"第 {i} 批执行过程中检测到硬件连接断开"
                                elif not dss_success:
                                    error_msg = f"第 {i} 批DSS执行失败（超时或错误），可能是硬件连接问题"
                                else:
                                    error_msg = f"第 {i} 批执行失败，未生成结果文件"
                                self.on_hardware_error(i, error_msg)
                            except Exception as e:
                                logger.error(f"触发硬件错误回调失败: {e}")

                        # 记录后续批次为未执行
                        self._mark_remaining_batches_as_skipped(batches[batch_index + 1:])
                        break

                    # 如果批次最终失败且不可重试，退出批次循环
                    if not batch_actually_success:
                        break

                    batch_index += 1
            
            # 收集剩余未执行用例的结果（如果有）
            executed_case_names = {r.case_name for r in all_results}
            for case in cases:
                if case["name"] not in executed_case_names:
                    # 检查该用例是否有结果文件
                    case_result = self._read_case_result(case)
                    if case_result:
                        all_results.append(case_result)
            
            # 按用例名称排序结果，保持顺序一致
            case_name_to_result = {r.case_name: r for r in all_results}
            sorted_results = []
            for case in cases:
                if case["name"] in case_name_to_result:
                    sorted_results.append(case_name_to_result[case["name"]])
            
            self._generate_summary_report(cases, sorted_results)
            
            self._post_process_dat_files(cases)
            
            self._cleanup_old_logs()
            
            return sorted_results
    
    def _find_last_completed_batch(self, cases: List[Dict]) -> int:
        """
        查找最后一个完成的批次索引
        
        逻辑：
        - 如果批次中所有用例都有结果文件且状态为 Success，则认为该批次已完成
        - 如果批次中有用例没有结果文件，或状态不是 Success，则认为该批次未完成
        - 返回第一个未完成的批次索引，用于断点续测
        
        Args:
            cases: 所有用例列表
            
        Returns:
            第一个未完成的批次索引（0-based），如果全部完成则返回批次总数
        """
        batches = self._split_into_batches(cases, self.batch_size)
        
        for i, batch in enumerate(batches):
            # 检查该批次的所有用例是否都有成功的结果
            for case in batch:
                summary_file = Path(case["dat_dir"]) / "summary.csv"
                if not summary_file.exists():
                    # 该批次未完成（没有结果文件）
                    logger.info(f"断点续测检测: 批次 {i+1} 用例 {case['name']} 无结果文件，从该批次开始")
                    return i
                
                # 检查结果状态
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content:
                            logger.info(f"断点续测检测: 批次 {i+1} 用例 {case['name']} 结果文件为空，从该批次开始")
                            return i
                        
                        # 解析 CSV 内容
                        parts = content.split(",")
                        if len(parts) >= 2:
                            status = parts[1]
                            # 只有 Success 状态才算完成
                            if status != "Success":
                                logger.info(f"断点续测检测: 批次 {i+1} 用例 {case['name']} 状态为 {status}，从该批次开始")
                                return i
                        else:
                            logger.info(f"断点续测检测: 批次 {i+1} 用例 {case['name']} 结果格式错误，从该批次开始")
                            return i
                except Exception as e:
                    logger.info(f"断点续测检测: 批次 {i+1} 用例 {case['name']} 读取结果失败: {e}，从该批次开始")
                    return i
            
            # 该批次所有用例都成功完成，继续检查下一批次
            logger.info(f"断点续测检测: 批次 {i+1} 已完成")
        
        # 所有批次都已完成
        logger.info(f"断点续测检测: 所有 {len(batches)} 个批次已完成")
        return len(batches)
    
    def _mark_remaining_batches_as_skipped(self, batches: List[List[Dict]]):
        """
        将剩余批次标记为跳过
        
        Args:
            batches: 剩余批次列表
        """
        for batch in batches:
            for case in batch:
                self._write_case_result(case, "Skipped")
    
    def _collect_batch_results(self, batch: List[Dict]) -> List[TestResult]:
        """
        收集批次中各用例的结果

        Args:
            batch: 批次中的用例列表

        Returns:
            测试结果列表
        """
        # 等待文件系统刷新（DSS 进程被杀死后，文件缓冲区可能还没写入磁盘）
        time.sleep(2)

        results = []
        logger.info(f"收集批次结果，批次包含 {len(batch)} 个用例")

        # 最多重试 3 次，每次间隔 1 秒
        max_collect_retries = 3
        for retry in range(max_collect_retries):
            results = []
            for case in batch:
                result = self._read_case_result(case)
                if result:
                    results.append(result)
                    logger.info(f"成功收集用例结果: {case['name']} = {result.status}")
                else:
                    logger.info(f"未能收集用例结果: {case['name']} (第 {retry+1} 次尝试)")

            # 如果收集到所有结果，提前退出
            if len(results) == len(batch):
                break

            # 还有结果未收集到，等待后重试
            if retry < max_collect_retries - 1:
                logger.info(f"只收集到 {len(results)}/{len(batch)} 个结果，等待 1 秒后重试...")
                time.sleep(1)

        logger.info(f"批次结果收集完成，共 {len(results)} 个结果")
        return results
    
    def _read_case_result(self, case: Dict) -> Optional[TestResult]:
        """
        读取单个用例的结果
        
        Args:
            case: 用例配置
            
        Returns:
            测试结果，如果没有结果则返回 None
        """
        # 使用绝对路径
        dat_dir = Path(case["dat_dir"]).resolve()
        summary_file = dat_dir / "summary.csv"
        
        logger.info(f"尝试读取用例结果: {case['name']} -> {summary_file}")
        
        if not summary_file.exists():
            logger.info(f"结果文件不存在: {summary_file}")
            return None
        
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.info(f"结果文件为空: {summary_file}")
                    return None

                # 解析 CSV 内容: case_name,status,duration_ms
                parts = content.split(",")
                if len(parts) >= 2:
                    case_name = parts[0]
                    status = parts[1]
                    duration_ms = int(parts[2]) if len(parts) >= 3 else None
                    logger.info(f"用例 {case_name} 结果: {status}")
                    return TestResult(
                        case_name=case_name,
                        status=status,
                        dat_dir=Path(case["dat_dir"]),
                        duration_ms=duration_ms
                    )
        except Exception as e:
            logger.warning(f"读取用例结果失败 {case['name']}: {e}")
        
        return None
    
    def _create_output_dirs(self, cases: List[Dict]):
        """创建输出目录"""
        for case in cases:
            dat_dir = Path(case["dat_dir"])
            dat_dir.mkdir(parents=True, exist_ok=True)
    
    def _split_into_batches(self, cases: List[Dict], batch_size: int) -> List[List[Dict]]:
        """将用例分批"""
        batches = []
        for i in range(0, len(cases), batch_size):
            batches.append(cases[i:i + batch_size])
        return batches
    
    def _check_hardware_connection(self) -> bool:
        """
        快速检查硬件连接状态
        
        优化策略：
        1. 首先进行 USB 设备预检测（快速，< 1秒）
        2. 如果预检测通过，再进行 DSS 连接检测（验证实际可连接性）
        3. 如果预检测失败，直接返回失败，避免等待 DSS 超时
        
        Returns:
            连接是否正常
        """
        # 步骤1: USB 设备预检测（快速）
        logger.info("执行硬件预检测...")
        precheck_passed, precheck_msg = quick_hardware_check()
        
        if not precheck_passed:
            logger.warning(f"硬件预检测失败: {precheck_msg}")
            # 预检测失败，直接返回，避免调用耗时的 DSS 检测
            return False
        
        logger.info(f"硬件预检测通过: {precheck_msg}")
        
        # 步骤2: DSS 连接检测（验证实际可连接性）
        # 只有在预检测通过后才执行，此时硬件大概率存在，DSS 检测会很快
        try:
            # 创建临时连接检测脚本
            check_script = self._create_connection_check_script()
            
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(check_script)
                js_file = f.name
            
            try:
                # 直接调用 eclipsec.exe，绕过 dss.bat 和 cmd.exe，避免中文乱码
                cmd = [
                    str(self._eclipsec_exe),
                    "-nosplash",
                    "-application", "com.ti.ccstudio.apps.runScript",
                    "-product", "com.ti.ccstudio.branding.product",
                    "-dss.rhinoArgs", js_file
                ]
                logger.info(f"执行 DSS 硬件检测命令: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,  # 增加超时时间到30秒
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    env=self._dss_env
                )
                
                # 检查输出中是否包含成功标志（DSS 输出为 UTF-8 编码）
                output = result.stdout.decode('utf-8', errors='ignore')
                stderr_output = result.stderr.decode('utf-8', errors='ignore')
                
                logger.info(f"DSS 硬件检测返回码: {result.returncode}")
                logger.info(f"DSS 硬件检测输出: {output}")
                if stderr_output:
                    logger.info(f"DSS 硬件检测错误输出: {stderr_output}")
                
                # 检查连接状态：必须包含 CONNECTION_OK 且不包含 CONNECTION_FAILED
                is_connected = "CONNECTION_OK" in output and "CONNECTION_FAILED" not in output and result.returncode == 0
                
                if not is_connected:
                    logger.warning(f"DSS 硬件连接检测失败，返回码: {result.returncode}")
                    logger.warning(f"标准输出: {output[:500]}")
                    if stderr_output:
                        logger.warning(f"错误输出: {stderr_output[:500]}")
                
                return is_connected
                
            finally:
                try:
                    os.unlink(js_file)
                except:
                    pass
                    
        except Exception as e:
            logger.warning(f"DSS 硬件连接检测失败: {e}")
            import traceback
            logger.warning(f"检测异常详情: {traceback.format_exc()}")
            return False
    
    def _create_connection_check_script(self) -> str:
        """
        创建硬件连接检测脚本
        
        Returns:
            JavaScript 脚本内容
        """
        ccxml_path = str(self.ccxml).replace('\\', '/')
        device_name = self.device
        cpu_name = self.cpu
        return f'''
importPackage(Packages.com.ti.debug.engine.scripting);
importPackage(Packages.com.ti.ccstudio.scripting.environment);
importPackage(Packages.java.lang);

print("正在连接目标设备...");

var env = null;
var server = null;
var session = null;
var connected = false;

try {{
    // 创建调试会话
    env = ScriptingEnvironment.instance();
    server = env.getServer("DebugServer.1");
    
    // 先尝试停止任何现有的调试会话（清理残留状态）
    try {{
        server.stop();
        print("已停止现有调试会话");
    }} catch (e) {{
        // 忽略错误，可能没有现有会话
    }}
    
    server.setConfig("{ccxml_path}");

    // 打开会话
    session = server.openSession("{device_name}", "{cpu_name}");

    // 尝试连接
    print("尝试连接目标...");
    try {{
        session.target.connect();
        connected = session.target.isConnected();
    }} catch (e) {{
        print("CONNECTION_FAILED: 连接异常 - " + e.message);
        connected = false;
    }}

    // 检查连接状态
    if (connected) {{
        print("CONNECTION_OK: 硬件连接正常");
        try {{
            session.target.disconnect();
        }} catch (e) {{
            print("警告: 断开连接时出错 - " + e.message);
        }}
    }} else {{
        print("CONNECTION_FAILED: 硬件连接失败");
    }}
}} catch (e) {{
    print("CONNECTION_FAILED: 脚本异常 - " + e.message);
}} finally {{
    // 确保资源被释放
    if (session) {{
        try {{
            if (session.target.isConnected()) {{
                session.target.disconnect();
            }}
        }} catch (e) {{}}
    }}
    if (server) {{
        try {{
            server.stop();
        }} catch (e) {{}}
    }}
}}

print("检测完成");
'''

    def _run_batch(self, batch: List[Dict], global_config: Dict, log_dir: Path, log_file, console_log_pos: int = 0) -> bool:
        """
        执行一批测试用例
        
        Args:
            batch: 批次中的用例列表
            global_config: 全局配置
            log_dir: 日志目录
            log_file: 日志文件
            
        Returns:
            是否成功执行该批次
        """
        log_file_path = str((log_dir / f"DSS_Batch_{batch[0]['name']}.xml").resolve()).replace("\\", "/")

        config_json = {
            "global": {
                "ccxml": global_config["ccxml"],
                "device": global_config["device"],
                "cpu": global_config["cpu"]
            },
            "log_file": log_file_path,
            "cases": [
                {
                    "case_name": case["name"],
                    "out": case["out"],
                    "timeout": global_config["timeout"],
                    "result_addr": int(global_config["result_addr"], 16),
                    "success_val": int(global_config["success_val"], 16),
                    "error_val": int(global_config["error_val"], 16),
                    "dat_dir": str(Path(case["dat_dir"]).resolve()).replace("\\", "/"),
                    "is_flash": case.get("is_flash"),  # 可选字段，None表示自动判断
                    "segments": [
                        {
                            "name": s["name"],
                            "addr": int(s["addr"], 16),
                            "len": int(s["len"], 16),
                            "width": s["width"]
                        }
                        for s in case["segments"]
                    ],
                    "export_points": case.get("export_points", [{"when": "after_run", "enabled": True, "subdir": "Memory"}]),
                    "result_check": case.get("result_check", {"method": "breakpoint", "success_label": "Right", "fail_label": "IDLE"})
                }
                for case in batch
            ]
        }
        
        js_script = self._generate_js_script(config_json)
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js_script)
            js_file = f.name
        
        try:
            # 直接调用 eclipsec.exe，绕过 dss.bat 和 cmd.exe，避免中文乱码
            cmd = [
                str(self._eclipsec_exe),
                "-nosplash",
                "-application", "com.ti.ccstudio.apps.runScript",
                "-product", "com.ti.ccstudio.branding.product",
                "-dss.rhinoArgs", js_file
            ]
            logger.info(f"执行 DSS 命令: {' '.join(cmd)}")

            self._current_process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=self._dss_env
            )
            
            # 批次超时 = 用例数 × (运行超时 + 内存导出预留时间) + 缓冲时间
            # 每个用例除了运行时间外，还需要内存导出时间（ZONE7 1MB 约需 30-40 秒）
            export_time_per_case = 60  # 每个用例预留 60 秒用于内存导出
            timeout_seconds = len(batch) * (self.timeout / 1000 + export_time_per_case) + 60
            try:
                return_code = self._current_process.wait(timeout=timeout_seconds)
                
                if return_code != 0:
                    logger.warning(f"批次 DSS 执行返回非零码: {return_code}")
                    if self._check_connection_error_in_log(log_dir, console_log_pos, batch[0]['name']):
                        return False
                
                return True
                    
            except subprocess.TimeoutExpired:
                logger.error(f"批次 DSS 执行超时")
                self._current_process.kill()
                self._current_process.wait()
                return False
        finally:
            try:
                os.unlink(js_file)
            except Exception as e:
                logger.warning(f"清理临时 JS 文件失败: {e}")
    
    def _check_connection_error_in_log(self, log_dir: Path, console_log_from_pos: int = 0, batch_name: str = "") -> bool:
        """
        检查日志中的连接错误（仅检查当前批次新增的日志内容）

        Args:
            log_dir: 日志目录
            console_log_from_pos: console_all.log 中开始检查的位置（之前的内容属于旧批次）
            batch_name: 当前批次第一个用例名，用于定位对应的 XML trace 文件

        Returns:
            是否检测到连接错误
        """
        connection_error_patterns = [
            "Error connecting to the target",
            "emulation failure",
            "TARGET_CONNECT_FAILED",
            "FTDI driver functions",
            "no XDS100 is plugged in",
            "CONNECTION_LOST_DETECTED",  # DSS 脚本检测到的运行时连接断开
            "连接失败",  # DSS 脚本中文错误信息
        ]

        def _has_connection_error(content: str) -> bool:
            for pattern in connection_error_patterns:
                if pattern in content:
                    return True
            return False

        # 仅检查 console_all.log 中当前批次新增的内容
        console_log_path = log_dir / "console_all.log"
        if console_log_path.exists():
            try:
                # 使用二进制模式读取，然后用 UTF-8 解码（DSS Java 进程输出 UTF-8）
                with open(console_log_path, 'rb') as f:
                    f.seek(console_log_from_pos)
                    raw_bytes = f.read()
                    new_content = raw_bytes.decode('utf-8', errors='ignore')
                    if _has_connection_error(new_content):
                        logger.error("=" * 60)
                        logger.error("检测到硬件连接问题！(console_all.log)")
                        logger.error("=" * 60)
                        logger.error("请检查以下项目:")
                        logger.error("  1. XDS100 调试器是否正确连接到电脑")
                        logger.error("  2. 目标板是否上电")
                        logger.error("  3. FTDI 驱动是否安装正确")
                        logger.error("  4. USB 线缆是否正常")
                        logger.error("=" * 60)
                        return True
            except Exception as e:
                logger.warning(f"检查 console_all.log 连接错误时出错: {e}")

        # 仅检查当前批次的 DSS XML trace 日志文件（每个批次的 XML 会被覆盖）
        if batch_name:
            xml_log = log_dir / f"DSS_Batch_{batch_name}.xml"
            if xml_log.exists():
                try:
                    with open(xml_log, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if _has_connection_error(content):
                            logger.error("=" * 60)
                            logger.error(f"检测到硬件连接问题！({xml_log.name})")
                            logger.error("=" * 60)
                            return True
                except Exception as e:
                    logger.warning(f"检查 {xml_log.name} 连接错误时出错: {e}")

        return False
    
    def _write_case_result(self, case: Dict, status: str):
        """写入单个用例的结果"""
        try:
            summary_file = Path(case["dat_dir"]) / "summary.csv"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"{case['name']},{status}\n")
        except Exception as e:
            logger.warning(f"写入用例结果失败: {e}")
    
    def _generate_js_script(self, config_json: Dict) -> str:
        """生成 DSS JavaScript 脚本"""
        with open(self.template_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        config_str = json.dumps(config_json, indent=2)
        return template.replace("${CONFIG_JSON}", config_str)
    
    def _collect_results(self, cases: List[Dict]) -> List[TestResult]:
        """收集测试结果"""
        results = []
        
        if not cases:
            return results
        
        # 从第一个用例的 dat_dir 获取时间戳目录
        first_dat_dir = Path(cases[0]["dat_dir"])
        time_dir = first_dat_dir.parent
        summary_file = time_dir / "summary.csv"
        
        logger.debug(f"查找汇总文件: {summary_file}")
        
        # 检查时间戳目录是否存在
        if not time_dir.exists():
            logger.warning(f"时间戳目录不存在: {time_dir}")
            # 为所有用例返回无结果
            for case in cases:
                results.append(TestResult(
                    case_name=case["name"],
                    status="NoResult",
                    error=f"时间戳目录不存在: {time_dir}"
                ))
            return results
        
        # 读取汇总文件
        if summary_file.exists():
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2:
                            case_name = row[0]
                            status = row[1]
                            # 找到对应的用例配置以获取 dat_dir
                            dat_dir = None
                            for case in cases:
                                if case["name"] == case_name:
                                    dat_dir = Path(case["dat_dir"])
                                    break
                            if dat_dir is None:
                                dat_dir = first_dat_dir  # 默认使用第一个用例的目录
                            
                            results.append(TestResult(
                                case_name=case_name,
                                status=status,
                                dat_dir=dat_dir
                            ))
                            logger.info(f"用例 {case_name} 结果: {status}")
                        else:
                            logger.warning(f"汇总文件行格式不正确: {row}")
            except Exception as e:
                logger.error(f"读取汇总文件失败: {e}")
                # 为所有用例返回无结果
                for case in cases:
                    results.append(TestResult(
                        case_name=case["name"],
                        status="NoResult",
                        error=f"读取汇总文件失败: {e}"
                    ))
        else:
            logger.warning(f"汇总文件不存在: {summary_file}")
            # 为所有用例返回无结果
            for case in cases:
                results.append(TestResult(
                    case_name=case["name"],
                    status="NoResult",
                    error="汇总文件不存在"
                ))
        
        return results

    def _generate_summary_report(self, cases: List[Dict], results: List[TestResult]):
        """生成汇总报告（代理方法）"""
        report_generator.generate_summary_report(self.run_timestamp, cases, results)

    def _post_process_dat_files(self, cases: List[Dict]):
        """后处理 .dat 文件（删除文件头）"""
        for case in cases:
            export_points = case.get("export_points", [{"when": "after_run", "subdir": "Memory"}])
            for ep in export_points:
                subdir = ep.get("subdir", "Memory")
                memory_dir = Path(case["dat_dir"]) / subdir
                if memory_dir.exists():
                    for dat_file in memory_dir.glob("*.dat"):
                        self._remove_first_line_if_header(dat_file)
    
    def _remove_first_line_if_header(self, file_path: Path):
        """
        如果文件第一行是 CCS 文件头格式，则删除第一行
        
        CCS .dat 文件头格式: 1651 <Format> <StartingAddress> <PageNum> <Length> [NewFormat]
        例如: 
        - 旧格式: 1651 1 80000000 0 10
        - 新格式: 1651 9 88675cac 0 c278 c00000000
        
        如果第一行不是文件头格式，则不删除（避免重复删除数据行）
        """
        import re
        try:
            with open(file_path, "r", encoding="utf-8") as src:
                lines = src.readlines()
            
            if not lines:
                return
            
            first_line = lines[0].strip()
            
            # 检查第一行是否是 CCS 文件头格式
            # 格式: 1651 <Format> <StartingAddress> <PageNum> <Length> [NewFormat]
            # - MagicNumber: 固定为 1651
            # - Format: 1-4 或 9 (十进制)
            # - StartingAddress: 十六进制 (如 80000000, 88675cac)
            # - PageNum: 十进制 (如 0, 1)
            # - Length: 十六进制 (如 10, 1a70c, c278)
            # - NewFormat: 可选，十六进制 (新格式时使用)
            header_pattern = r'^1651\s+\d+\s+[0-9A-Fa-f]+\s+\d+\s+[0-9A-Fa-f]+(\s+[0-9A-Fa-f]+)?$'
            
            if re.match(header_pattern, first_line):
                # 第一行是文件头，删除它
                with open(file_path, "w", encoding="utf-8") as dst:
                    dst.writelines(lines[1:])
                logger.debug(f"已删除文件头: {file_path}")
            else:
                # 第一行不是文件头，说明文件已经被处理过，跳过
                logger.debug(f"文件已处理过或无文件头，跳过: {file_path}")
                
        except Exception as e:
            logger.debug(f"处理文件失败 {file_path}: {e}")
    
    def _cleanup_old_logs(self, days: int = 30):
        """清理旧日志"""
        import time
        cutoff = time.time() - days * 86400
        log_root = Path("6_result_dat_logs")
        
        if not log_root.exists():
            return
        
        for d in log_root.iterdir():
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d)
                logger.info(f"已清理旧日志: {d}")
