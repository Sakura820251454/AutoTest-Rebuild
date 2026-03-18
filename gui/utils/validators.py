#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入验证工具

提供各种输入验证功能
"""

from pathlib import Path
from typing import Tuple, Optional


class Validators:
    """验证器类"""
    
    @staticmethod
    def validate_path(path: str, must_exist: bool = False, is_file: bool = False) -> Tuple[bool, Optional[str]]:
        """
        验证路径
        
        Args:
            path: 路径字符串
            must_exist: 是否必须存在
            is_file: 是否是文件（False 表示目录）
        
        Returns:
            (是否有效, 错误信息)
        """
        if not path:
            return False, "路径不能为空"
        
        path_obj = Path(path)
        
        if must_exist:
            if not path_obj.exists():
                return False, f"路径不存在: {path}"
            
            if is_file and not path_obj.is_file():
                return False, f"不是文件: {path}"
            
            if not is_file and not path_obj.is_dir():
                return False, f"不是目录: {path}"
        
        return True, None
    
    @staticmethod
    def validate_number(value: str, min_val: float = None, max_val: float = None) -> Tuple[bool, Optional[str]]:
        """
        验证数字
        
        Args:
            value: 数值字符串
            min_val: 最小值
            max_val: 最大值
        
        Returns:
            (是否有效, 错误信息)
        """
        try:
            num = float(value)
        except ValueError:
            return False, f"不是有效的数字: {value}"
        
        if min_val is not None and num < min_val:
            return False, f"数值不能小于 {min_val}"
        
        if max_val is not None and num > max_val:
            return False, f"数值不能大于 {max_val}"
        
        return True, None
    
    @staticmethod
    def validate_integer(value: str, min_val: int = None, max_val: int = None) -> Tuple[bool, Optional[str]]:
        """
        验证整数
        
        Args:
            value: 整数字符串
            min_val: 最小值
            max_val: 最大值
        
        Returns:
            (是否有效, 错误信息)
        """
        try:
            num = int(value)
        except ValueError:
            return False, f"不是有效的整数: {value}"
        
        if min_val is not None and num < min_val:
            return False, f"数值不能小于 {min_val}"
        
        if max_val is not None and num > max_val:
            return False, f"数值不能大于 {max_val}"
        
        return True, None
    
    @staticmethod
    def validate_not_empty(value: str, field_name: str = "字段") -> Tuple[bool, Optional[str]]:
        """
        验证非空
        
        Args:
            value: 值
            field_name: 字段名称
        
        Returns:
            (是否有效, 错误信息)
        """
        if not value or not value.strip():
            return False, f"{field_name}不能为空"
        
        return True, None
