#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoTest GUI 启动脚本

@input PyQt5 (GUI框架)
@input gui.main_window.MainWindow (主窗口)
@output main()函数
@pos GUI程序入口，检查依赖、初始化PyQt5应用、启动主窗口；兼容源码运行与 --windowed 打包运行

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import os
import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# 源码模式把项目根加入 sys.path；打包后模块已在 sys.path 中，无需再插入
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.runtime_paths import app_root, app_path, is_frozen


def _setup_console_streams():
    """
    --windowed 打包后没有控制台，sys.stdout / sys.stderr 为 None

    统一指向 devnull，避免 logging.StreamHandler 与 print 在无控制台时抛错。
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _write_crash_log(text: str, prefix: str = "crash") -> str:
    """把异常文本写入程序目录 logs/YYYY-MM-DD/ 下，返回日志路径；失败返回空串"""
    try:
        log_dir = app_path("logs") / datetime.now().strftime("%Y-%m-%d")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{prefix}_{datetime.now().strftime('%H%M%S')}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(text)
        return str(log_file)
    except Exception:
        return ""


def _show_message_box(message: str, title: str = "AutoTest GUI"):
    """无控制台时用原生 MessageBox 兜底（Qt 可能尚未初始化）"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


def _install_excepthook():
    """
    全局异常钩子：无控制台时 stderr 不可见，改为写日志 + 弹窗，避免“双击没反应/闪退”
    """
    def handle(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_file = _write_crash_log(text, "crash")
        summary = f"{exc_type.__name__}: {exc_value}"
        detail = f"{summary}\n\n日志: {log_file}" if log_file else summary
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(None, "程序异常", detail)
                return
        except Exception:
            pass
        _show_message_box(detail, "AutoTest GUI 运行异常")

    sys.excepthook = handle


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import PyQt5
        return True
    except ImportError:
        return False


def install_dependencies():
    """尝试安装依赖（仅源码模式；打包后依赖已内置，禁止再调用 pip）"""
    if is_frozen():
        return False

    import subprocess
    print("正在安装 PyQt5...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt5"])
        print("PyQt5 安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装失败: {e}")
        return False


def _run(args):
    """解析参数后的实际启动流程"""
    # 相对配置路径先按“启动时的工作目录”解析，再切换到程序目录，避免 chdir 后路径失效
    config_path = args.config
    if config_path:
        config_path = str(Path(config_path).expanduser().resolve())

    os.chdir(app_root())

    if not check_dependencies():
        # 仅源码模式允许自动安装；打包模式 install_dependencies 会直接返回 False
        installed = args.install_deps and install_dependencies() and check_dependencies()
        if not installed:
            message = (
                "错误: 未找到 PyQt5。\n\n"
                "打包版本应已内置依赖；源码模式请先安装: pip install PyQt5"
            )
            print(message)
            _show_message_box(message, "AutoTest GUI 启动失败")
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
    window = MainWindow(config_path=config_path)
    window.show()

    # 运行应用程序
    sys.exit(app.exec())


def main():
    """主函数"""
    _setup_console_streams()
    _install_excepthook()

    try:
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
            help="自动安装依赖（仅源码模式可用）"
        )

        args = parser.parse_args()
        _run(args)
    except SystemExit:
        raise
    except BaseException:
        # 启动阶段失败（缺 DLL、配置损坏等）：写日志 + 原生弹窗，避免静默退出
        text = traceback.format_exc()
        log_file = _write_crash_log(text, "startup_error")
        last_line = text.strip().splitlines()[-1] if text.strip() else "未知错误"
        detail = f"程序启动失败:\n\n{last_line}"
        if log_file:
            detail += f"\n\n日志: {log_file}"
        _show_message_box(detail, "AutoTest GUI 启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
