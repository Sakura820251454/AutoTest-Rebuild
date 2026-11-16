#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoTest GUI 启动脚本

@input PyQt5 (GUI框架)
@input gui.main_window.MainWindow (主窗口)
@output main()函数
@pos GUI程序入口，检查依赖、初始化PyQt5应用（加载 Qt 中文翻译）、启动主窗口；
     兼容源码运行与 --windowed 打包运行，并在冻结态显式锁定随包 Qt 插件路径
     （不受外部 QT_* 环境变量影响）

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

from src.runtime_paths import app_root, app_path, bundle_root, is_frozen, resource_path


def _qt_plugin_root():
    """
    随包的 Qt 插件根目录；源码模式返回 None（交给本机 PyQt5 自己处理）

    冻结态下 PyQt5 包位于 bundle_root() 内，插件在其 Qt5/plugins（PyQt5 5.15 wheel 布局），
    老版本 PyQt5 为 Qt/plugins。不写死 _internal/runtime 之类目录名。
    """
    if not is_frozen():
        return None
    candidates = [
        bundle_root() / "PyQt5" / "Qt5" / "plugins",
        bundle_root() / "PyQt5" / "Qt" / "plugins",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def _prepare_qt_environment():
    """
    创建 QApplication 之前把 Qt 插件路径锁定到随包目录

    外部环境的 QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH / QT_QPA_PLATFORM
    会让 Qt 去别处找平台插件，或去找一个根本没随包提供的平台插件，
    表现就是启动时弹 "no Qt platform plugin could be initialized"。
    这里一律显式覆盖（不是“缺失时才设置”），保证不依赖外部环境。
    """
    plugin_root = _qt_plugin_root()
    if plugin_root is None:
        return None

    platforms_dir = plugin_root / "platforms"
    os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)

    # QT_QPA_PLATFORM 指向没随包提供的平台插件时 Qt 会直接致命退出，清掉让它回落默认
    requested = os.environ.get("QT_QPA_PLATFORM", "").split(":")[0].strip().lower()
    if requested and not (platforms_dir / f"q{requested}.dll").is_file():
        os.environ.pop("QT_QPA_PLATFORM", None)

    # 让随包 Qt DLL 目录参与依赖解析，避免平台插件本身因依赖找不到而加载失败
    if hasattr(os, "add_dll_directory"):
        for dll_dir in (plugin_root.parent / "bin", bundle_root()):
            if dll_dir.is_dir():
                try:
                    os.add_dll_directory(str(dll_dir))
                except OSError:
                    pass
    return plugin_root


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


def _install_qt_translator(app):
    """
    加载 Qt 自带中文翻译，让 QMessageBox 等标准按钮显示“确定/取消”

    找不到 qt_zh_CN.qm 时静默跳过（只是按钮回到英文，不影响功能）。
    """
    try:
        from PyQt5.QtCore import QLibraryInfo, QTranslator
        translator = QTranslator(app)
        translations = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
        if not translator.load("qt_zh_CN", translations):
            return
        app.installTranslator(translator)
        app._qt_zh_translator = translator  # 保持引用，避免被 GC 回收
    except Exception:
        pass


def _install_chinese_button_filter(app):
    """
    所有 QMessageBox 显示时把标准按钮改成中文

    部分 PyQt 发行版只有 qt_zh_CN.qm、没有 qtbase_zh_CN.qm，翻译后按钮仍是 OK/Cancel，
    这里统一兜底，保证弹窗按钮为“确定/取消/是/否”。
    """
    try:
        from PyQt5.QtCore import QEvent, QObject
        from PyQt5.QtWidgets import QMessageBox
        from gui.utils.message_boxes import localize_buttons

        class _MessageBoxFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Show and isinstance(obj, QMessageBox):
                    localize_buttons(obj)
                return False

        app._qt_msgbox_filter = _MessageBoxFilter(app)
        app.installEventFilter(app._qt_msgbox_filter)
    except Exception:
        pass


def _enable_high_dpi():
    """
    启用高 DPI 缩放与高分辨率图标

    必须在创建 QApplication 之前调用，否则 Qt 已按默认策略初始化窗口。
    PassThrough 让 Windows 125%/150% 等非整数缩放下窗口不被二次取整放大。
    """
    from PyQt5.QtCore import Qt, QCoreApplication

    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        from PyQt5.QtGui import QGuiApplication
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass


def _apply_app_identity(app):
    """
    应用标识与图标：组织名、窗口图标（任务栏/标题栏共用）

    图标随包放在 gui/assets/app.ico，源码模式与打包模式都能通过 resource_path 找到。
    """
    from PyQt5.QtGui import QIcon
    from gui.utils.build_info import VERSION

    app.setOrganizationName("AutoTest")
    app.setApplicationName("AutoTest GUI")
    app.setApplicationVersion(VERSION)

    icon_path = resource_path("gui/assets/app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))


def _hide_internal_dirs(root: Path) -> None:
    """
    把程序目录下的模板/源码/结果输出/runtime 打上 Hidden 属性

    zip / rar / 邮件附件 不保留 NTFS 属性，用户解压后这些目录会普通可见；
    启动时重打一次属性，保证不管用什么方式分发，程序跑过之后都能回到隐藏状态。
    失败静默处理（不影响功能）。
    """
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        HIDDEN = 0x2
        for name in ("1_project_templete", "2_source_file", "4_result_out", "runtime"):
            p = root / name
            if not p.is_dir():
                continue
            attrs = k32.GetFileAttributesW(str(p))
            if attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                continue
            k32.SetFileAttributesW(str(p), attrs | HIDDEN)
    except Exception:
        pass


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

    # zip / rar 等分发方式不保留 NTFS Hidden 属性，启动时把内部目录重新打隐藏
    _hide_internal_dirs(app_root())

    # 必须在导入 PyQt5 / 创建 QApplication 之前完成，否则 Qt 已经按外部环境找过插件了
    qt_plugins = _prepare_qt_environment()
    if qt_plugins is not None:
        platforms_dir = qt_plugins / "platforms"
        if not any(platforms_dir.glob("q*.dll")):
            message = (
                "错误: 程序包不完整，缺少 Qt 平台插件。\n\n"
                f"期望位置: {platforms_dir}\n\n"
                "请重新解压完整的程序目录（不要只复制 exe 文件）。"
            )
            _write_crash_log(message + "\n", "qt_plugin_missing")
            _show_message_box(message, "AutoTest GUI 启动失败")
            sys.exit(1)

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

    # 高 DPI 必须在 QApplication 创建前启用
    _enable_high_dpi()

    # 创建应用程序
    app = QApplication(sys.argv)

    # 兜底：把随包插件目录以绝对路径插到库路径首位（QApplication 创建后才有效）
    if qt_plugins is not None:
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.addLibraryPath(str(qt_plugins))

    # 组织名/应用名/窗口图标（标题栏与任务栏共用）
    _apply_app_identity(app)

    # 标准对话框按钮中文化（确定/取消/是/否）
    _install_qt_translator(app)
    _install_chinese_button_filter(app)

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
