# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包描述（GUI 单入口，onedir + 无控制台）

@input run_gui.py（唯一入口）、templates/（随包兜底资源）
@output dist/AutoTestGUI/AutoTestGUI.exe 及 runtime/
@pos 构建脚本，只在打包时使用，不参与运行时

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

from pathlib import Path
import datetime
import json
import subprocess
import tempfile

PROJECT_ROOT = Path(SPECPATH).resolve().parent


def _git_short_commit():
    """构建时的 git 短哈希；没有仓库时返回空串（关于对话框显示 "-"）"""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT), text=True, timeout=5).strip()
    except Exception:
        return ""


# 关于对话框的构建信息：打包时固化提交与构建时间（运行时无 git 仓库）
_stamp_dir = Path(tempfile.mkdtemp(prefix="autotest_build_"))
_stamp = _stamp_dir / "build_info.json"
_stamp.write_text(json.dumps({
    "commit": _git_short_commit(),
    "build_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}, ensure_ascii=False), encoding="utf-8")

a = Analysis(
    [str(PROJECT_ROOT / "run_gui.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "templates"), "templates"),
        # 窗口/任务栏图标（源码模式从仓库取，打包后从 runtime/gui/assets 取）
        (str(PROJECT_ROOT / "gui" / "assets" / "app.ico"), "gui/assets"),
        # 构建信息（版本/提交/构建时间），供“帮助 → 关于”读取
        (str(_stamp), "gui/assets"),
        # FLASH 段加密脚本：包内兜底一份，现场也可放在 exe 同级目录覆盖
        (str(PROJECT_ROOT / "encrypt_flash_dat.py"), "."),
    ],
    hiddenimports=[
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        "et_xmlfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "IPython",
        "pytest",
        # 交付版只出 CSV：不打包 pandas，避免体积膨胀；
        # 代码里 import pandas 失败会走 except 分支跳过 xlsx 生成
        "pandas",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtQml",
        "PyQt5.QtQuick",
        "PyQt5.QtMultimedia",
        "PyQt5.QtBluetooth",
        "PyQt5.QtDesigner",
        "PyQt5.QtSql",
        "PyQt5.QtTest",
        "PyQt5.QtHelp",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoTestGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(PROJECT_ROOT / "gui" / "assets" / "app.ico"),
    contents_directory="runtime",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoTestGUI",
)
