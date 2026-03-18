#!/usr/bin/env python3
"""
直接导入已有 CCS 工程并运行测试

用法:
    python scripts/import_and_run.py -c config.json -p "工程路径"
    python scripts/import_and_run.py -c config.json --workspace "工作空间路径"

说明:
    这个脚本跳过工程生成步骤，直接导入已有的 CCS 工程到工作空间，
    然后构建并运行测试。
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import Config, setup_logger, get_logger
from src.builder import ProjectBuilder
from src.executor import TestExecutor
from src.pipeline import Step

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="直接导入已有 CCS 工程并运行测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入指定工程并运行测试
  python scripts/import_and_run.py -c config.json -p "D:/projects/my_project"
  
  # 扫描工作空间中的所有工程
  python scripts/import_and_run.py -c config.json --workspace "D:/projects"
  
  # 只导入和构建，不运行测试
  python scripts/import_and_run.py -c config.json -p "D:/projects/my_project" --no-test
        """
    )
    
    parser.add_argument("-c", "--config", required=True, help="配置文件路径")
    parser.add_argument("-p", "--project", help="单个工程路径")
    parser.add_argument("-w", "--workspace", help="工作空间路径（扫描所有工程）")
    parser.add_argument("--no-build", action="store_true", help="跳过构建步骤")
    parser