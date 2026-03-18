#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件预检测模块

@input platform.system, shutil, subprocess (系统工具和命令)
@output HardwareDetector类, quick_hardware_check()函数
@pos 辅助工具层，提供XDS100调试器USB预检测，避免DSS超时等待

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import re
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, List, Tuple
from .logger import get_logger

logger = get_logger(__name__)


class HardwareDetector:
    """硬件预检测器"""
    
    # XDS100 的 USB VID/PID
    XDS100_VID_PID = [
        ("0451", "bef0"),  # XDS100v1
        ("0451", "bef1"),  # XDS100v2
        ("0451", "bef2"),  # XDS100v3
        ("0451", "bef3"),  # XDS110
    ]
    
    # FTDI 芯片的 VID/PID（XDS100 使用 FTDI 芯片）
    FTDI_VID = "0403"
    
    def __init__(self):
        self.system = platform.system()
        self._check_tools()
    
    def _check_tools(self):
        """检查可用的工具"""
        self.has_wmic = shutil.which("wmic") is not None
        self.has_pnputil = shutil.which("pnputil") is not None
        self.has_powershell = shutil.which("powershell") is not None
        
        logger.debug(f"工具检查: wmic={self.has_wmic}, pnputil={self.has_pnputil}, powershell={self.has_powershell}")
    
    def quick_check(self) -> Tuple[bool, str]:
        """
        快速检查硬件是否存在
        
        Returns:
            (是否存在, 详细信息)
        """
        try:
            if self.system == "Windows":
                return self._check_windows()
            elif self.system == "Linux":
                return self._check_linux()
            else:
                # 其他系统无法预检测，返回 True 让 DSS 去检测
                return True, f"不支持的操作系统: {self.system}，将使用 DSS 检测"
        except Exception as e:
            logger.warning(f"预检测失败: {e}")
            # 预检测失败时，允许继续执行 DSS 检测
            return True, f"预检测异常: {e}，将使用 DSS 检测"
    
    def _check_windows(self) -> Tuple[bool, str]:
        """Windows 系统检测"""
        # 方法1: 使用 pnputil 检查（Windows 10/11 推荐）
        if self.has_pnputil:
            try:
                result = subprocess.run(
                    ["pnputil", "/enum-devices", "/class", "Universal Serial Bus controllers"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    # 检查 XDS100 相关设备
                    if any(vid in result.stdout for vid in ["VID_0451", "VID_0403"]):
                        return True, "检测到 XDS100/FTDI USB 设备 (pnputil)"
            except subprocess.TimeoutExpired:
                logger.warning("pnputil 查询超时")
            except Exception as e:
                logger.warning(f"pnputil 查询失败: {e}")
        
        # 方法2: 使用 wmic 检查 USB 设备
        if self.has_wmic:
            try:
                result = subprocess.run(
                    ["wmic", "path", "win32_pnpentity", "where", 
                     "DeviceID like '%VID_0451%'", "get", "DeviceID,Description", "/value"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0 and "VID_0451" in result.stdout:
                    # 找到了 TI 的设备
                    devices = self._parse_wmic_output(result.stdout)
                    if devices:
                        return True, f"检测到 XDS100 设备: {devices[0]}"
            except subprocess.TimeoutExpired:
                logger.warning("wmic 查询超时")
            except Exception as e:
                logger.warning(f"wmic 查询失败: {e}")
        
        # 方法3: 使用 powershell 检查
        if self.has_powershell:
            try:
                result = subprocess.run(
                    ["powershell", "-Command", 
                     "Get-PnpDevice -Class 'Universal Serial Bus controllers', 'Ports (COM & LPT)' | "
                     "Where-Object { $_.InstanceId -like '*VID_0451*' -or $_.InstanceId -like '*VID_0403*' } | "
                     "Select-Object Name, InstanceId, Status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0 and ("VID_0451" in result.stdout or "VID_0403" in result.stdout):
                    return True, "检测到 XDS100/FTDI 设备 (PowerShell)"
            except subprocess.TimeoutExpired:
                logger.warning("PowerShell 查询超时")
            except Exception as e:
                logger.warning(f"PowerShell 查询失败: {e}")
        
        # 方法4: 使用设备管理器导出（备选方案）
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_PnPEntity | Where-Object { $_.DeviceID -like '*USB*' } | "
                 "Select-Object Name, DeviceID | Format-List"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                output_lower = result.stdout.lower()
                if "xds" in output_lower or "0451" in output_lower or "0403" in output_lower:
                    return True, "检测到可能的 XDS100/FTDI 设备 (WMI)"
        except Exception:
            pass
        
        # 所有预检测方法都失败
        # 如果没有可用工具，返回 True 让 DSS 去检测
        if not self.has_wmic and not self.has_pnputil and not self.has_powershell:
            logger.warning("没有可用的系统工具进行预检测，将使用 DSS 检测")
            return True, "无法执行预检测（缺少系统工具），将使用 DSS 检测"
        
        return False, "未检测到 XDS100 调试器，请检查:\n  1. XDS100 是否正确连接到电脑\n  2. USB 线缆是否正常\n  3. 驱动是否安装"
    
    def _check_linux(self) -> Tuple[bool, str]:
        """Linux 系统检测"""
        try:
            # 使用 lsusb 检查
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for vid, pid in self.XDS100_VID_PID:
                    if f"{vid}:{pid}" in result.stdout.lower():
                        return True, f"检测到 XDS100 设备 (VID:PID = {vid}:{pid})"
                
                # 检查 FTDI 设备
                if f"Vendor={self.FTDI_VID}" in result.stdout or f"{self.FTDI_VID}:" in result.stdout:
                    return True, "检测到 FTDI 设备（可能是 XDS100）"
        except subprocess.TimeoutExpired:
            logger.warning("lsusb 查询超时")
        except Exception as e:
            logger.warning(f"lsusb 查询失败: {e}")
        
        return False, "未检测到 XDS100 调试器"
    
    def _parse_wmic_output(self, output: str) -> List[str]:
        """解析 wmic 输出"""
        devices = []
        current_device = {}
        
        for line in output.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                current_device[key] = value
            elif not line and current_device:
                desc = current_device.get('Description', 'Unknown')
                devices.append(desc)
                current_device = {}
        
        if current_device:
            desc = current_device.get('Description', 'Unknown')
            devices.append(desc)
        
        return devices
    
    def get_detailed_info(self) -> dict:
        """
        获取详细的硬件信息
        
        Returns:
            包含详细信息的字典
        """
        info = {
            "system": self.system,
            "xds100_detected": False,
            "devices": [],
            "drivers": [],
            "tools_available": {
                "wmic": self.has_wmic,
                "pnputil": self.has_pnputil,
                "powershell": self.has_powershell
            }
        }
        
        try:
            if self.system == "Windows" and self.has_powershell:
                # 使用 PowerShell 获取 USB 设备
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-PnpDevice -Class 'Universal Serial Bus controllers', 'Ports (COM & LPT)' | "
                     "Where-Object { $_.InstanceId -match 'USB' } | "
                     "Select-Object Name, InstanceId, Status, Class | Format-List"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    # 解析输出查找 XDS100 相关设备
                    if "xds" in result.stdout.lower() or "0451" in result.stdout or "0403" in result.stdout:
                        info["xds100_detected"] = True
                        # 提取相关设备信息
                        lines = result.stdout.split('\n')
                        for i, line in enumerate(lines):
                            if any(keyword in line.lower() for keyword in ["xds", "0451", "0403"]):
                                # 提取设备名称
                                for j in range(max(0, i-3), min(len(lines), i+3)):
                                    if "Name" in lines[j]:
                                        info["devices"].append(lines[j].strip())
        except Exception as e:
            logger.warning(f"获取详细信息失败: {e}")
        
        return info


def quick_hardware_check() -> Tuple[bool, str]:
    """
    快速硬件检测的便捷函数
    
    Returns:
        (是否存在, 详细信息)
    """
    detector = HardwareDetector()
    return detector.quick_check()
