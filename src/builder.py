"""
工程构建模块

@input Config (配置对象)
@input CCSNotFoundError, ProjectImportError, ProjectBuildError (异常类)
@output ProjectBuilder类, BuildResult类
@pos 核心模块，多线程并行构建CCS工程，自动导入和收集构建产物

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from .config import Config
from .exceptions import (
    BuildError,
    CCSNotFoundError,
    ProjectImportError,
    ProjectBuildError,
    BuildTimeoutError,
)
from .logger import get_logger, LogContext

logger = get_logger(__name__)


@dataclass
class BuildResult:
    """构建结果"""
    project_name: str
    out_file: Optional[Path]
    success: bool
    error: Optional[str] = None
    build_time: float = 0.0
    stdout: Optional[str] = None


class ProjectBuilder:
    """
    工程构建器
    
    用法：
        builder = ProjectBuilder(config)
        results = builder.build_all()
        for r in results:
            print(f"{r.project_name}: {'成功' if r.success else '失败'}")
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.ccs_exe = config.paths.ccs_executable
        self.workspace = config.paths.ccs_workspace
        self.result_dir = config.paths.result_dir
        self.build_config = config.build.build_config
        self.timeout = config.build.build_timeout
        self.max_threads = config.build.max_build_threads

        # 回调函数（供 GUI 进度显示）
        self.on_project_start: Optional[callable] = None  # (project_name: str)
        self.on_project_finish: Optional[callable] = None  # (project_name: str, success: bool, duration_s: float)
        self.should_stop: Optional[callable] = None  # 返回 True 时停止构建
    
    def validate(self):
        """验证构建环境"""
        if not self.ccs_exe.exists():
            raise CCSNotFoundError(str(self.ccs_exe))
    
    def find_projects(self) -> List[Path]:
        """查找工作空间中的所有有效工程"""
        projects = []
        for item in self.workspace.iterdir():
            if item.is_dir() and (item / ".project").exists():
                projects.append(item)
        return sorted(projects)
    
    def build_all(self, import_projects: bool = True) -> List[BuildResult]:
        """
        构建所有工程

        Args:
            import_projects: 是否先清理并导入工程（现已通过 -ccs.autoImport 在构建时自动处理）

        Returns:
            构建结果列表
        """
        with LogContext(logger, "工程构建"):
            self.validate()

            self.result_dir.mkdir(parents=True, exist_ok=True)

            projects = self.find_projects()
            if not projects:
                logger.warning(f"工作空间中没有找到有效工程: {self.workspace}")
                return []

            logger.info(f"找到 {len(projects)} 个工程")

            # 清理旧的 .metadata，确保构建时工作空间干净
            # 不再单独导入工程（importProject 多次调用会触发 Eclipse bug:
            # "null parent found while sorting trees"），
            # 改为依靠构建命令的 -ccs.autoImport true 自动导入
            metadata_dir = self.workspace / ".metadata"
            if metadata_dir.exists():
                shutil.rmtree(metadata_dir, ignore_errors=True)
                logger.debug("  已清理旧的 .metadata 目录")

            results = self._build_projects(projects)
            
            success_count = sum(1 for r in results if r.success)
            logger.info(f"工程构建完成: {success_count}/{len(results)} 成功")
            
            self._print_summary(results)
            
            return results
    
    def _import_projects(self, projects: List[Path]):
        """逐个导入工程到工作空间（导入成功即完成，退出码非零通常为工作空间保存时的 Eclipse 内部 bug"""
        logger.info("开始导入工程...")

        # 清理旧的 .metadata，避免 Eclipse 工作空间元数据累积损坏
        metadata_dir = self.workspace / ".metadata"
        if metadata_dir.exists():
            shutil.rmtree(metadata_dir, ignore_errors=True)
            logger.debug("  已清理旧的 .metadata 目录")

        for i, project_path in enumerate(projects, 1):
            project_name = project_path.name
            logger.info(f"[{i}/{len(projects)}] 导入: {project_name}")

            cmd = [
                str(self.ccs_exe),
                "-noSplash",
                "-data", str(self.workspace),
                "-application", "com.ti.ccstudio.apps.importProject",
                "-ccs.location", str(project_path),
                "-ccs.autoBuild", "false"
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.workspace)
                )

                # 退出码非零通常是工作空间保存时的 Eclipse bug
                # ("null parent found while sorting trees")，工程实际已成功导入
                if result.returncode != 0:
                    logger.warning(f"  导入返回非零: {result.returncode}（工程可能已成功导入）")
                    if result.stderr:
                        logger.debug(f"  stderr: {result.stderr[:500]}")
                else:
                    logger.debug(f"  导入成功")

            except subprocess.TimeoutExpired:
                logger.error(f"  导入超时")
            except Exception as e:
                logger.error(f"  导入异常: {e}")
    
    def _build_projects(self, projects: List[Path]) -> List[BuildResult]:
        """串行构建所有工程（Eclipse 工作空间不支持并发访问）"""
        logger.info(f"开始串行构建 {len(projects)} 个工程...")

        results = []

        for i, project_path in enumerate(projects, 1):
            logger.info(f"[{i}/{len(projects)}] 构建: {project_path.name}")
            try:
                result = self._build_single(project_path)
                results.append(result)

                status = "✓" if result.success else "✗"
                logger.info(f"  {status} {result.project_name} ({result.build_time:.1f}s)")

            except Exception as e:
                logger.exception(f"构建异常: {project_path.name}")
                results.append(BuildResult(
                    project_name=project_path.name,
                    out_file=None,
                    success=False,
                    error=str(e)
                ))

        return results
    
    def _build_single(self, project_path: Path) -> BuildResult:
        """构建单个工程"""
        project_name = project_path.name
        start_time = datetime.now()

        # 通知 GUI：开始构建
        if self.on_project_start:
            self.on_project_start(project_name)

        # 检查是否已有 .out 文件，如果存在则直接复制，跳过构建
        out_file = self.workspace / project_name / self.build_config / f"{project_name}.out"
        if out_file.exists():
            logger.info(f"  {project_name}: 已存在 .out 文件，跳过构建")
            dest_file = self.result_dir / f"{project_name}.out"
            shutil.copy(out_file, dest_file)
            logger.debug(f"    复制: {out_file} -> {dest_file}")
            build_time = 0.0
            if self.on_project_finish:
                self.on_project_finish(project_name, True, build_time)
            return BuildResult(
                project_name=project_name,
                out_file=dest_file,
                success=True,
                build_time=build_time
            )

        cmd = [
            str(self.ccs_exe),
            "-noSplash",
            "-data", str(self.workspace),
            "-application", "com.ti.ccstudio.apps.buildProject",
            "-ccs.projects", project_name,
            "-ccs.configuration", self.build_config,
            "-ccs.autoImport", "true"
        ]

        stdout_text = ""

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.workspace)
            )
            stdout_text = result.stdout + result.stderr
            
            out_file = self.workspace / project_name / self.build_config / f"{project_name}.out"
            
            if out_file.exists():
                dest_file = self.result_dir / f"{project_name}.out"
                shutil.copy(out_file, dest_file)
                logger.debug(f"    复制: {out_file} -> {dest_file}")

                build_time = (datetime.now() - start_time).total_seconds()
                if self.on_project_finish:
                    self.on_project_finish(project_name, True, build_time)
                return BuildResult(
                    project_name=project_name,
                    out_file=dest_file,
                    success=True,
                    build_time=build_time
                )
            else:
                error_msg = "构建产物 .out 文件不存在"
                logger.debug(f"    {error_msg}")
                logger.debug(f"    构建输出: {stdout_text[:500]}")

                build_time = (datetime.now() - start_time).total_seconds()
                if self.on_project_finish:
                    self.on_project_finish(project_name, False, build_time)
                return BuildResult(
                    project_name=project_name,
                    out_file=None,
                    success=False,
                    error=error_msg,
                    build_time=build_time,
                    stdout=stdout_text
                )

        except subprocess.TimeoutExpired:
            logger.error(f"    构建超时 ({self.timeout}s)")
            if self.on_project_finish:
                self.on_project_finish(project_name, False, self.timeout)
            return BuildResult(
                project_name=project_name,
                out_file=None,
                success=False,
                error=f"构建超时 ({self.timeout}秒)",
                build_time=self.timeout
            )

        except Exception as e:
            logger.exception(f"    构建异常")
            if self.on_project_finish:
                self.on_project_finish(project_name, False, 0)
            return BuildResult(
                project_name=project_name,
                out_file=None,
                success=False,
                error=str(e),
                stdout=stdout_text
            )
    
    def _print_summary(self, results: List[BuildResult]):
        """打印构建摘要"""
        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        total_time = sum(r.build_time for r in results)
        
        logger.info("=" * 60)
        logger.info(f"构建摘要: {len(succeeded)}/{len(results)} 成功, 总耗时 {total_time:.1f}s")
        
        if failed:
            logger.info("失败的工程:")
            for r in failed:
                logger.info(f"  - {r.project_name}: {r.error}")
        
        logger.info("=" * 60)
