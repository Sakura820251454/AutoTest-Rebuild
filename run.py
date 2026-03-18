#!/usr/bin/env python3
"""
AutoTest 一键执行入口

用法:
    python run.py -c config.json              # 执行全部步骤
    python run.py -c config.json --generate   # 只执行生成
    python run.py -c config.json --build      # 只执行构建
    python run.py -c config.json --test       # 只执行测试
    python run.py -c config.json --resume     # 断点续传
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import Pipeline, Step


def main():
    parser = argparse.ArgumentParser(
        description="AutoTest - TI C2000 DSP 自动化测试框架",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-c", "--config", required=True, help="配置文件路径")
    parser.add_argument("--generate", action="store_true", help="只执行工程生成")
    parser.add_argument("--build", action="store_true", help="只执行工程构建")
    parser.add_argument("--test", action="store_true", help="只执行测试")
    parser.add_argument("--resume", action="store_true", help="从断点续传")
    
    args = parser.parse_args()
    
    steps = None
    if args.generate or args.build or args.test:
        steps = []
        if args.generate:
            steps.append(Step.GENERATE)
        if args.build:
            steps.append(Step.BUILD)
        if args.test:
            steps.append(Step.TEST)
    
    pipeline = Pipeline(args.config)
    pipeline.run(steps=steps, resume=args.resume)


if __name__ == "__main__":
    main()
