"""
工程生成模块

@input Config (配置对象)
@input TemplateNotFoundError, SourceFileError, GeneratorError (异常类)
@output ProjectGenerator类, GenerationResult类, GenerationMode枚举
@pos 核心模块，支持模板生成和手动配置两种模式，批量生成CCS测试工程

两种明确的生成模式（通过配置选择）：
- template: 从模板 + 源文件批量生成
- manual: 验证已手动配置的工程

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import Config
from .exceptions import (
    GeneratorError,
    TemplateNotFoundError,
    SourceFileError,
    ProjectGenerationError,
)
from .logger import get_logger, LogContext

logger = get_logger(__name__)


SUPPORTED_SOURCE_EXTENSIONS = [".asm", ".c", ".cpp", ".s"]


class GenerationMode(Enum):
    """工程生成模式"""
    TEMPLATE = "template"    # 从模板批量生成
    MANUAL = "manual"        # 使用手动配置的工程


@dataclass
class GenerationResult:
    """工程生成结果"""
    project_name: str
    project_dir: Path
    source_file: Optional[Path]
    success: bool
    error: Optional[str] = None


class ProjectGenerator:
    """
    工程生成器
    
    两种明确的工作模式：
    
    模式A - 模板生成（template）：
        所有工程通过模板工程 + 源文件批量生成
        适用于：所有工程配置相同，只有工程名和源文件不同
        
    模式B - 手动配置（manual）：
        所有工程已手动配置好，直接放在 generate_dir 目录
        适用于：各工程配置各不相同
    
    配置方式（config.json）：
        {
            "generation_mode": "template",  // 或 "manual"
            ...
        }
    
    用法：
        generator = ProjectGenerator(config)
        results = generator.generate()  // 根据配置自动选择模式
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.template_dir = config.paths.template_dir
        self.source_dir = config.paths.source_dir
        self.output_dir = config.paths.generate_dir
        self.template_name = self.template_dir.name if self.template_dir.exists() else ""
        
        # 从配置获取生成模式，默认为模板模式
        # 支持两种配置格式：
        # 新格式: { "generation": { "generation_mode": "manual" } }
        # 旧格式: { "generation_mode": "manual" }
        generation_config = config._raw.get("generation", {})
        mode_str = generation_config.get("generation_mode", "template") if isinstance(generation_config, dict) else config._raw.get("generation_mode", "template")
        self.mode = GenerationMode(mode_str)
    
    def validate(self):
        """验证生成环境"""
        if self.mode == GenerationMode.TEMPLATE:
            # 模板模式：需要模板目录和源文件目录
            if not self.template_dir.exists():
                raise TemplateNotFoundError(str(self.template_dir))
            if not self.source_dir.exists():
                raise SourceFileError(str(self.source_dir), "源文件目录不存在")
            
            required_files = [".project", ".cproject"]
            for f in required_files:
                if not (self.template_dir / f).exists():
                    raise GeneratorError(
                        f"模板工程缺少必要文件: {f}",
                        error_code=2004,
                        details={"template_dir": str(self.template_dir), "missing_file": f}
                    )
        
        else:  # MANUAL 模式
            # 手动模式：只需要检查输出目录是否存在工程
            if not self.output_dir.exists():
                raise SourceFileError(
                    str(self.output_dir), 
                    "手动配置模式下，generate_dir 目录必须存在且包含配置好的工程"
                )
    
    def generate(self, clean: bool = True) -> List[GenerationResult]:
        """
        生成/准备所有测试工程
        
        根据配置的 generation_mode 自动选择模式：
        - template: 从模板批量生成
        - manual: 验证手动配置的工程
        
        Args:
            clean: 是否清理已存在的工程目录（仅模板模式有效）
        
        Returns:
            生成结果列表
        """
        if self.mode == GenerationMode.TEMPLATE:
            return self._generate_from_template(clean)
        else:
            return self._validate_manual_projects()
    
    def _generate_from_template(self, clean: bool) -> List[GenerationResult]:
        """
        模板生成模式：从模板工程 + 源文件批量生成
        
        适用于：所有工程配置相同，只有工程名和源文件不同
        """
        with LogContext(logger, "工程生成（模板模式）"):
            self.validate()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            source_files = self._find_source_files()
            if not source_files:
                logger.warning(f"源文件目录中没有找到支持的源文件: {self.source_dir}")
                return []
            
            logger.info(f"模板模式：找到 {len(source_files)} 个源文件，开始批量生成...")
            
            results = []
            for i, source_file in enumerate(source_files, 1):
                logger.info(f"[{i}/{len(source_files)}] 生成工程: {source_file.stem}")
                result = self._generate_single(source_file, clean)
                results.append(result)
                
                if result.success:
                    logger.info(f"  ✓ 成功: {result.project_dir}")
                else:
                    logger.error(f"  ✗ 失败: {result.error}")
            
            success_count = sum(1 for r in results if r.success)
            logger.info(f"工程生成完成: {success_count}/{len(results)} 成功")
            
            return results
    
    def _validate_manual_projects(self) -> List[GenerationResult]:
        """
        手动配置模式：验证已配置好的工程
        
        适用于：各工程配置各不相同，已在CCS中手动配置好
        """
        with LogContext(logger, "工程验证（手动模式）"):
            self.validate()
            
            # 扫描输出目录中的所有工程
            projects = self._find_manual_projects()
            
            if not projects:
                raise GeneratorError(
                    "手动配置模式下，generate_dir 目录中没有找到有效的CCS工程",
                    error_code=2005,
                    details={"generate_dir": str(self.output_dir)}
                )
            
            logger.info(f"手动模式：找到 {len(projects)} 个已配置的工程")
            
            results = []
            for i, project_dir in enumerate(projects, 1):
                project_name = project_dir.name
                logger.info(f"[{i}/{len(projects)}] 验证工程: {project_name}")
                
                # 检查工程有效性
                is_valid = self._validate_project(project_dir)
                
                if is_valid:
                    logger.info(f"  ✓ 有效")
                    results.append(GenerationResult(
                        project_name=project_name,
                        project_dir=project_dir,
                        source_file=None,
                        success=True
                    ))
                else:
                    logger.error(f"  ✗ 无效")
                    results.append(GenerationResult(
                        project_name=project_name,
                        project_dir=project_dir,
                        source_file=None,
                        success=False,
                        error="工程验证失败"
                    ))
            
            success_count = sum(1 for r in results if r.success)
            logger.info(f"工程验证完成: {success_count}/{len(results)} 有效")
            
            return results
    
    def _find_source_files(self) -> List[Path]:
        """查找所有源文件"""
        files = []
        for ext in SUPPORTED_SOURCE_EXTENSIONS:
            files.extend(self.source_dir.glob(f"*{ext}"))
        return sorted(files)
    
    def _find_manual_projects(self) -> List[Path]:
        """查找手动配置的工程目录"""
        projects = []
        for item in self.output_dir.iterdir():
            if item.is_dir() and (item / ".project").exists():
                projects.append(item)
        return sorted(projects)
    
    def _validate_project(self, project_dir: Path) -> bool:
        """验证工程是否有效"""
        required_files = [".project", ".cproject"]
        for f in required_files:
            if not (project_dir / f).exists():
                logger.warning(f"  工程缺少文件: {f}")
                return False
        return True
    
    def _generate_single(self, source_file: Path, clean: bool) -> GenerationResult:
        """生成单个测试工程"""
        project_name = source_file.stem
        project_dir = self.output_dir / project_name
        
        try:
            if project_dir.exists():
                if clean:
                    logger.debug(f"  删除已存在的目录: {project_dir}")
                    shutil.rmtree(project_dir)
                else:
                    return GenerationResult(
                        project_name=project_name,
                        project_dir=project_dir,
                        source_file=source_file,
                        success=True,
                        error="目录已存在，跳过"
                    )
            
            logger.debug(f"  复制模板工程...")
            shutil.copytree(self.template_dir, project_dir)
            
            logger.debug(f"  复制源文件...")
            shutil.copy(source_file, project_dir / source_file.name)
            
            logger.debug(f"  替换工程名...")
            self._replace_project_name(project_dir, project_name)
            
            return GenerationResult(
                project_name=project_name,
                project_dir=project_dir,
                source_file=source_file,
                success=True
            )
            
        except Exception as e:
            logger.exception(f"工程生成失败: {project_name}")
            return GenerationResult(
                project_name=project_name,
                project_dir=project_dir,
                source_file=source_file,
                success=False,
                error=str(e)
            )
    
    def _replace_project_name(self, project_dir: Path, new_name: str):
        """替换工程文件中的工程名"""
        project_file = project_dir / ".project"
        cproject_file = project_dir / ".cproject"
        
        patterns = [
            (re.compile(rf'<name>{re.escape(self.template_name)}</name>'),
             f'<name>{new_name}</name>'),
            (re.compile(rf'<project>{re.escape(self.template_name)}</project>'),
             f'<project>{new_name}</project>'),
            (re.compile(rf'projectName">{re.escape(self.template_name)}</'),
             f'projectName">{new_name}</'),
            (re.compile(rf'projectName={re.escape(self.template_name)}'),
             f'projectName={new_name}'),
        ]
        
        for file_path in [project_file, cproject_file]:
            if not file_path.exists():
                continue
            
            content = file_path.read_text(encoding="utf-8")
            original = content
            
            for pattern, replacement in patterns:
                content = pattern.sub(replacement, content)
            
            if content != original:
                file_path.write_text(content, encoding="utf-8")
                logger.debug(f"    已更新: {file_path.name}")
