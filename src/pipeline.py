"""
流水线管理模块

@input Config, ProjectGenerator, ProjectBuilder, TestExecutor (核心组件)
@input AutoTestError (异常基类)
@output Pipeline类, Step枚举, PipelineResult类
@pos 核心入口模块，串联生成/构建/测试步骤，支持断点续传

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from .config import Config
from .logger import setup_logger, get_logger, LogContext
from .exceptions import AutoTestError
from .generator import ProjectGenerator
from .builder import ProjectBuilder
from .executor import TestExecutor

logger = get_logger(__name__)


class Step(Enum):
    """流水线步骤"""
    GENERATE = "generate"
    BUILD = "build"
    TEST = "test"


@dataclass
class PipelineResult:
    """流水线执行结果"""
    step: Step
    success: bool
    duration: float
    error: Optional[str] = None


class Pipeline:
    """
    测试流水线
    
    用法：
        pipeline = Pipeline(config_path)
        pipeline.run()
    """
    
    def __init__(self, config_path: str, start_batch: int = 0, resume_test: bool = False):
        self.config_path = Path(config_path).resolve()
        self.config: Optional[Config] = None
        self.results: List[PipelineResult] = []
        self.start_time: float = 0
        self.start_batch = start_batch
        self.resume_test = resume_test
    
    def run(self, steps: Optional[List[Step]] = None, resume: bool = False):
        """
        执行流水线
        
        Args:
            steps: 要执行的步骤列表，None 表示执行全部
            resume: 是否从断点续传
        """
        self.start_time = time.perf_counter()
        
        log_dir = setup_logger()
        logger.info("=" * 60)
        logger.info("AutoTest 流水线启动")
        logger.info(f"配置文件: {self.config_path}")
        logger.info(f"日志目录: {log_dir}")
        logger.info("=" * 60)
        
        try:
            self._load_config()
            self._check_environment()
            
            if steps is None:
                steps = self._get_enabled_steps()
            
            if resume:
                steps = self._find_resume_point(steps)
            
            for step in steps:
                result = self._run_step(step)
                self.results.append(result)
                
                if not result.success:
                    logger.error(f"步骤 {step.value} 失败，停止流水线")
                    break
            
            self._print_summary()
            
        except AutoTestError as e:
            logger.error(f"流水线错误: {e}")
            self._print_error_help(e)
            sys.exit(1)
        except Exception as e:
            logger.exception(f"未预期的错误: {e}")
            sys.exit(1)
    
    def _load_config(self):
        """加载配置"""
        with LogContext(logger, "加载配置"):
            self.config = Config.load(self.config_path)
            self.config.validate()
            logger.info(f"配置验证通过")
    
    def _check_environment(self):
        """检查环境"""
        with LogContext(logger, "环境检查"):
            if not self.config.paths.ccs_executable.exists():
                logger.error(f"CCS 未找到: {self.config.paths.ccs_executable}")
                logger.info("请确保 CCS 已正确安装，并在配置文件中指定正确的路径")
            else:
                logger.info(f"CCS: {self.config.paths.ccs_executable}")
            
            if not self.config.paths.ccs_dss.exists():
                logger.error(f"DSS 未找到: {self.config.paths.ccs_dss}")
            else:
                logger.info(f"DSS: {self.config.paths.ccs_dss}")
            
            if not self.config.paths.ccxml.exists():
                logger.warning(f"CCXML 文件不存在: {self.config.paths.ccxml}")
            else:
                logger.info(f"CCXML: {self.config.paths.ccxml}")
    
    def _get_enabled_steps(self) -> List[Step]:
        """获取启用的步骤"""
        steps = []
        if self.config.build.do_generate:
            steps.append(Step.GENERATE)
        if self.config.build.do_build:
            steps.append(Step.BUILD)
        if self.config.test.do_test:
            steps.append(Step.TEST)
        return steps
    
    def _find_resume_point(self, steps: List[Step]) -> List[Step]:
        """查找断点续传位置"""
        if self.config.paths.generate_dir.exists():
            out_files = list(self.config.paths.generate_dir.rglob("*.out"))
            if out_files:
                logger.info(f"发现 {len(out_files)} 个已构建的 .out 文件，尝试跳过生成和构建步骤")
                return [Step.TEST]
        return steps
    
    def _run_step(self, step: Step) -> PipelineResult:
        """执行单个步骤"""
        start = time.perf_counter()
        
        try:
            if step == Step.GENERATE:
                generator = ProjectGenerator(self.config)
                # 根据配置的 generation_mode 自动选择模式
                results = generator.generate()
                success = all(r.success for r in results)
                
            elif step == Step.BUILD:
                builder = ProjectBuilder(self.config)
                results = builder.build_all()
                success = any(r.success for r in results)
                
            elif step == Step.TEST:
                executor = TestExecutor(self.config)
                # 支持从指定批次开始或断点续测
                results = executor.run_all(
                    start_batch=self.start_batch,
                    resume_from_last=self.resume_test
                )
                success = any(r.status == "Success" for r in results)
            
            else:
                success = False
            
            duration = time.perf_counter() - start
            return PipelineResult(step=step, success=success, duration=duration)
            
        except Exception as e:
            duration = time.perf_counter() - start
            return PipelineResult(step=step, success=False, duration=duration, error=str(e))
    
    def _print_summary(self):
        """打印执行摘要"""
        total_duration = time.perf_counter() - self.start_time
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("流水线执行摘要")
        logger.info("=" * 60)
        
        for result in self.results:
            status = "✓ 成功" if result.success else "✗ 失败"
            logger.info(f"  {result.step.value:12s} {status:8s} ({result.duration:.2f}s)")
            if result.error:
                logger.info(f"    错误: {result.error}")
        
        logger.info("-" * 60)
        logger.info(f"总耗时: {total_duration:.2f} 秒")
        logger.info("=" * 60)
    
    def _print_error_help(self, error: AutoTestError):
        """打印错误帮助信息"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("错误诊断")
        logger.info("=" * 60)
        logger.info(f"错误码: E{error.error_code:04d}")
        logger.info(f"错误信息: {error.message}")
        
        if error.details:
            logger.info("详细信息:")
            for k, v in error.details.items():
                logger.info(f"  {k}: {v}")
        
        help_messages = {
            1001: "请检查配置文件路径是否正确",
            1002: "请检查配置文件中的字段值是否有效",
            1003: "请检查路径配置，确保所有目录和文件都存在",
            2001: "请确保模板工程目录存在且包含 .project 和 .cproject 文件",
            2002: "请确保源文件目录存在且包含有效的源文件",
            3001: "请确保 CCS 已正确安装，并在配置文件中指定正确的路径",
            4001: "请确保 CCS DSS 脚本执行器存在",
        }
        
        if error.error_code in help_messages:
            logger.info(f"建议: {help_messages[error.error_code]}")
        
        logger.info("=" * 60)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="AutoTest - TI C2000 DSP 自动化测试框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.pipeline -c config.json              # 执行全部步骤
  python -m src.pipeline -c config.json --steps generate build  # 只执行生成和构建
  python -m src.pipeline -c config.json --resume      # 断点续传
  python -m src.pipeline -c config.json --steps test --start-batch 2   # 从第3个批次开始测试
  python -m src.pipeline -c config.json --steps test --resume-test     # 测试断点续测
        """
    )
    
    parser.add_argument("-c", "--config", required=True, help="配置文件路径")
    parser.add_argument("--steps", nargs="+", choices=["generate", "build", "test"],
                        help="要执行的步骤（默认全部）")
    parser.add_argument("--resume", action="store_true", help="从断点续传")
    parser.add_argument("--start-batch", type=int, default=0, 
                        help="从第几个批次开始测试（0-based，仅test步骤有效）")
    parser.add_argument("--resume-test", action="store_true",
                        help="自动从上次中断的批次继续测试")
    
    args = parser.parse_args()
    
    steps = None
    if args.steps:
        steps = [Step(s) for s in args.steps]
    
    pipeline = Pipeline(
        args.config, 
        start_batch=args.start_batch,
        resume_test=args.resume_test
    )
    pipeline.run(steps=steps, resume=args.resume)


if __name__ == "__main__":
    main()
