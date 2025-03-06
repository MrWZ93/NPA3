#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Manager - 设置管理模块
管理程序设置的保存和加载
"""

import os
import json

class SettingsManager:
    """设置管理类，负责保存和加载用户设置"""
    
    # 单例模式实现
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, app_name="NPA3"):
        """初始化设置管理器
        
        Args:
            app_name: 应用程序名称，用于设置文件夹名
        """
        self.app_name = app_name
        self.settings_dir = os.path.expanduser(f"~/.{app_name.lower()}")
        
        # 确保设置目录存在
        os.makedirs(self.settings_dir, exist_ok=True)
    
    def save_settings(self, component_name, settings):
        """保存组件设置
        
        Args:
            component_name: 组件名称
            settings: 设置字典
        
        Returns:
            bool: 保存是否成功
        """
        try:
            settings_path = os.path.join(self.settings_dir, f"{component_name}_settings.json")
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def load_settings(self, component_name):
        """加载组件设置
        
        Args:
            component_name: 组件名称
        
        Returns:
            dict: 设置字典，如果加载失败则返回空字典
        """
        try:
            settings_path = os.path.join(self.settings_dir, f"{component_name}_settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {}
