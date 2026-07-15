#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件检测工作线程

在后台执行硬件连接检测
"""

import sys
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.hardware_detector import quick_hardware_check


class HardwareChecker(QThread):
    """硬件检测工作线程"""
    
    check_completed = pyqtSignal(bool, str)  # 检测完成信号(成功/失败, 消息)
    log_message = pyqtSignal(str)  # 日志消息
    
    def __init__(self, config: Config):
        super().__init__()
        
        self.config = config
        self.is_running = True
    
    def run(self):
        """执行硬件检测"""
        try:
            self.log_message.emit("开始检测硬件连接...")
            
            # 步骤1: USB 设备预检测（快速）
            self.log_message.emit("执行硬件预检测...")
            precheck_passed, precheck_msg = quick_hardware_check()
            
            if not precheck_passed:
                self.log_message.emit(f"硬件预检测失败: {precheck_msg}")
                self.check_completed.emit(False, f"未检测到 XDS100 调试器\n{precheck_msg}")
                return
            
            self.log_message.emit(f"硬件预检测通过: {precheck_msg}")
            
            # 步骤2: DSS 连接检测（验证实际可连接性）
            self.log_message.emit("执行 DSS 连接检测...")
            
            # 创建临时 DSS 脚本
            dss_script = self._create_dss_script()
            
            self.log_message.emit(f"CCXML 文件: {self.config.paths.ccxml}")
            self.log_message.emit(f"设备名称: {self.config.test.device}")
            self.log_message.emit(f"CPU 名称: {self.config.test.cpu}")
            
            # 执行 DSS 脚本
            result = self._run_dss_script(dss_script)
            
            # 清理临时文件
            try:
                os.remove(dss_script)
            except:
                pass
            
            if result and self.is_running:
                self.log_message.emit("硬件连接检测成功")
                self.check_completed.emit(True, "硬件连接正常")
            elif not self.is_running:
                self.log_message.emit("检测被取消")
                self.check_completed.emit(False, "检测被取消")
            else:
                self.log_message.emit("硬件连接检测失败")
                self.check_completed.emit(False, "硬件连接失败，请检查配置")
                
        except Exception as e:
            self.log_message.emit(f"检测出错: {str(e)}")
            self.check_completed.emit(False, f"检测出错: {str(e)}")
    
    def _create_dss_script(self) -> str:
        """
        创建临时 DSS 脚本
        
        Returns:
            脚本文件路径
        """
        ccxml_path = str(self.config.paths.ccxml).replace('\\', '/')
        device_name = self.config.test.device
        cpu_name = self.config.test.cpu
        
        script_content = f'''
// 硬件连接检测脚本
importPackage(Packages.com.ti.debug.engine.scripting);
importPackage(Packages.com.ti.ccstudio.scripting.environment);
importPackage(Packages.java.lang);

print("正在连接目标设备...");

var env = null;
var server = null;
var session = null;

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
    }} catch (e) {{
        print("FAILED: 连接异常 - " + e.message);
        server.stop();
        java.lang.System.exit(1);
    }}

    // 检查连接状态
    if (session.target.isConnected()) {{
        print("SUCCESS: 硬件连接成功");
        session.target.disconnect();
    }} else {{
        print("FAILED: 硬件连接失败");
    }}
}} catch (e) {{
    print("FAILED: 脚本异常 - " + e.message);
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
    print("检测完成");
}}
'''
        
        # 创建临时文件（必须用 UTF-8 编码，DSS/Rhino 默认用 UTF-8 读取 JS 文件）
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            return f.name
    
    def _run_dss_script(self, script_path: str) -> bool:
        """
        运行 DSS 脚本
        
        Args:
            script_path: 脚本文件路径
        
        Returns:
            是否成功
        """
        try:
            # 构建命令：直接调用 eclipsec.exe，绕过 dss.bat 和 cmd.exe，避免中文乱码
            # dss.bat 路径: C:/ti/ccs1210/ccs/ccs_base/scripting/bin/dss.bat
            # eclipsec.exe 路径: C:/ti/ccs1210/ccs/eclipse/eclipsec.exe
            dss_bat = self.config.paths.ccs_dss
            if not dss_bat.exists():
                self.log_message.emit(f"错误: DSS 执行器不存在: {dss_bat}")
                return False

            # 从 dss.bat 路径推导 eclipsec.exe 路径
            dss_dir = dss_bat.parent  # scripting/bin
            eclipsec_path = dss_dir / ".." / ".." / ".." / "eclipse" / "eclipsec.exe"
            eclipsec_path = eclipsec_path.resolve()

            if not eclipsec_path.exists():
                self.log_message.emit(f"错误: eclipsec.exe 不存在: {eclipsec_path}")
                return False

            # eclipsec.exe 启动参数（与 dss.bat 中一致）
            cmd = [
                str(eclipsec_path),
                "-nosplash",
                "-application", "com.ti.ccstudio.apps.runScript",
                "-product", "com.ti.ccstudio.branding.product",
                "-dss.rhinoArgs", script_path
            ]

            self.log_message.emit(f"执行命令: {' '.join(cmd)}")

            # DSS Java 进程环境变量
            dss_env = os.environ.copy()

            # 执行脚本，等待完成后一次性读取输出
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=dss_env
            )

            # DSS 输出为 UTF-8 编码，一次性读取不会截断
            if result.stdout:
                output = result.stdout.decode('utf-8', errors='replace')
                for line in output.splitlines():
                    line = line.strip()
                    if line:
                        self.log_message.emit(line)
                        if "SUCCESS" in line:
                            return True
                        elif "FAILED" in line:
                            return False

            if result.stderr:
                err_output = result.stderr.decode('utf-8', errors='replace')
                for line in err_output.splitlines():
                    line = line.strip()
                    if line:
                        self.log_message.emit(f"[错误] {line}")

            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            self.log_message.emit("错误: 检测超时")
            return False
        except Exception as e:
            self.log_message.emit(f"错误: {str(e)}")
            return False
    
    def stop(self):
        """停止检测"""
        self.is_running = False
        self.log_message.emit("正在取消检测...")
