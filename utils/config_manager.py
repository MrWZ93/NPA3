#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - 保存和加载用户配置
"""

import os
import json
import logging

class ConfigManager:
    """用户配置管理类"""
    def __init__(self, config_file='config.json'):
        # 配置文件路径
        self.config_dir = os.path.join(os.path.expanduser('~'), '.npa')
        self.config_file = os.path.join(self.config_dir, config_file)
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                # 创建默认配置
                return self.save_config({
                    'recent_folders': [],
                    'sampling_rate': 1000.0,
                    'theme': 'default',
                    'window_size': [1200, 800],
                    'visible_channels': [],
                    'splitter_sizes': [200, 800, 200]
                })
            
            with open(self.config_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logging.warning(f"Error loading config: {str(e)}, using defaults")
            return {
                'recent_folders': [],
                'sampling_rate': 1000.0,
                'theme': 'default',
                'window_size': [1200, 800],
                'visible_channels': [],
                'splitter_sizes': [200, 800, 200]
            }
    
    def save_config(self, config=None):
        """保存配置到文件"""
        if config is not None:
            self.config = config
        
        try:
            # 确保配置目录存在
            os.makedirs(self.config_dir, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            return self.config
        except Exception as e:
            logging.error(f"Error saving config: {str(e)}")
            return self.config
    
    def update_config(self, key, value):
        """更新单个配置项"""
        self.config[key] = value
        return self.save_config()
    
    def add_recent_folder(self, folder_path):
        """添加最近使用的文件夹"""
        if 'recent_folders' not in self.config:
            self.config['recent_folders'] = []
        
        # 如果已在列表中，则移除旧的条目
        if folder_path in self.config['recent_folders']:
            self.config['recent_folders'].remove(folder_path)
        
        # 添加到列表开头
        self.config['recent_folders'].insert(0, folder_path)
        
        # 保持列表长度不超过10
        self.config['recent_folders'] = self.config['recent_folders'][:10]
        
        self.save_config()
    
    def get_recent_folders(self):
        """获取最近使用的文件夹列表"""
        return self.config.get('recent_folders', [])
