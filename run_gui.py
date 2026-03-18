#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoTest GUI 启动脚本

@input PyQt5 (GUI框架)
@input gui.main_window.MainWindow (主窗口)
@output main()函数
@pos GUI程序入口，检查依赖、初始化PyQt5应用、启动主窗口

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import PyQt5
        return True
    except ImportError:
        return False

def install_dependencies():
    """尝试安装依赖"""
    import subprocess
    print("正在安装 PyQt5...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt5"])
        print("PyQt5 安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装失败: {e}")
        return False

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AutoTest GUI - TI C2000 DSP 自动化测试工具")
    parser.add_argument(
        "-c", "--config",
        help="指定配置文件路径",
        default=None
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="自动安装依赖"
    )
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        print("错误: 未找到 PyQt5")
        if args.install_deps:
            if not install_dependencies():
                sys.exit(1)
        else:
            print("请安装 PyQt5: pip install PyQt5")
            print("或使用 --install-deps 参数自动安装")
            sys.exit(1)
    
    # 导入 GUI 模块
    from PyQt5.QtWidgets import QApplication
    from gui.main_window import MainWindow
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName("AutoTest GUI")
    app.setApplicationVersion("1.0.0")
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = MainWindow(config_path=args.config)
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
