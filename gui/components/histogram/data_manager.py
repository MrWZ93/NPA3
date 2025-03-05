#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Data Manager - 直方图数据管理
处理数据加载和通道选择
"""

import os
import numpy as np
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from core.data_processor import FileDataProcessor


class HistogramDataManager:
    """直方图数据管理类"""
    
    def __init__(self, parent=None):
        """初始化数据管理器"""
        self.parent = parent
        self.data = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.selected_channel = None
        self.file_processor = FileDataProcessor()
        self.file_path = None
    
    def load_file(self, file_path=None):
        """加载文件"""
        try:
            # 如果没有提供文件路径，则打开文件选择对话框
            if file_path is None:
                file_path, _ = QFileDialog.getOpenFileName(
                    self.parent,
                    "Open Data File",
                    "",
                    "Data Files (*.h5 *.csv *.tdms *.abf);;All Files (*)"
                )
                
                if not file_path:
                    return False, None, "No file selected"
            
            # 记录文件路径
            self.file_path = file_path
            
            # 使用FileDataProcessor加载文件
            success, data, info = self.file_processor.load_file(file_path)
            
            if not success:
                error_msg = info.get("Error", "Unknown error")
                return False, None, error_msg
            
            # 更新数据
            self.data = data
            
            # 获取采样率
            if "Sampling Rate" in info and isinstance(info["Sampling Rate"], str):
                try:
                    # 如果字符串格式如 "1000 Hz"，提取数字部分
                    sr_str = info["Sampling Rate"].split()[0]  # 取第一部分
                    self.sampling_rate = float(sr_str)
                except:
                    # 如果解析失败，保持默认采样率
                    pass
            elif hasattr(self.file_processor, 'sampling_rate'):
                self.sampling_rate = self.file_processor.sampling_rate
            
            return True, data, info
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, None, str(e)
    
    def get_channels(self):
        """获取通道列表"""
        if self.data is None:
            return []
        
        channels = []
        
        if isinstance(self.data, dict):
            channels = list(self.data.keys())
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim == 1:
                channels = ["Channel 1"]
            elif self.data.ndim == 2:
                channels = [f"Channel {i+1}" for i in range(self.data.shape[1])]
        
        return channels
    
    def get_channel_data(self, channel_name=None):
        """获取指定通道的数据"""
        if self.data is None:
            return None
        
        # 如果没有指定通道名称，使用当前选择的通道
        if channel_name is None:
            channel_name = self.selected_channel
        
        if channel_name is None:
            # 如果仍然没有通道名称，尝试使用第一个可用通道
            channels = self.get_channels()
            if not channels:
                return None
            channel_name = channels[0]
        
        # 设置当前选择的通道
        self.selected_channel = channel_name
        
        # 获取通道数据
        channel_data = None
        
        try:
            if isinstance(self.data, dict):
                if channel_name in self.data:
                    channel_data = self.data[channel_name]
            
            elif isinstance(self.data, np.ndarray):
                if self.data.ndim == 1:
                    channel_data = self.data
                elif self.data.ndim == 2:
                    # 从 "Channel X" 中提取索引
                    channel_parts = channel_name.split()
                    if len(channel_parts) > 1 and channel_parts[-1].isdigit():
                        channel_index = int(channel_parts[-1]) - 1
                    else:
                        # 尝试将整个字符串转换为索引
                        try:
                            channel_index = int(channel_name) - 1
                        except:
                            channel_index = 0
                    
                    if 0 <= channel_index < self.data.shape[1]:
                        channel_data = self.data[:, channel_index]
                    else:
                        # 默认使用第一列
                        channel_data = self.data[:, 0]
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error getting channel data: {str(e)}")
        
        return channel_data
    
    def set_data(self, data, sampling_rate=None):
        """设置数据（外部直接传入）"""
        self.data = data
        if sampling_rate is not None:
            self.sampling_rate = sampling_rate
        
        # 重置选择的通道
        self.selected_channel = None
        
        # 默认选择第一个可用通道
        channels = self.get_channels()
        if channels:
            self.selected_channel = channels[0]
