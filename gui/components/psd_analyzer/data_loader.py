#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据加载器模块 - 支持H5和其他数据文件
"""

import os
import numpy as np
import h5py
from datetime import datetime
from PyQt6.QtWidgets import QProgressDialog
from PyQt6.QtCore import Qt


class DataLoader:
    """数据加载器 - 支持多种文件格式"""
    def __init__(self):
        self.current_data = None  # 用于显示的数据（可能降采样）
        self.original_data = None  # 存储原始数据（用于PSD计算）
        self.file_info = {}
        self.file_path = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.metadata = {}  # 存储额外的元数据
    
    def load_file(self, file_path, parent_widget=None):
        """加载数据文件，支持进度显示"""
        self.file_path = file_path
        self.file_info = {}
        self.metadata = {}
        
        # 根据文件扩展名选择加载方法
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.h5', '.hdf5']:
            return self._load_h5_file(file_path, parent_widget)
        else:
            return False, None, {"Error": f"Unsupported file format: {ext}"}
    
    def _load_h5_file(self, file_path, parent_widget=None):
        """加载H5文件，支持进度显示"""
        try:
            # 首先打开文件以获取数据集总数，用于计算进度
            datasets_total = 0
            with h5py.File(file_path, 'r') as h5file:
                def count_datasets(name, obj):
                    if isinstance(obj, h5py.Dataset) and obj.dtype.kind in 'iuf':
                        nonlocal datasets_total
                        datasets_total += 1
                h5file.visititems(count_datasets)
            
            # 创建进度对话框
            progress = None
            if parent_widget and datasets_total > 0:
                progress = QProgressDialog("Loading H5 file...", "Abort", 0, datasets_total, parent_widget)
                progress.setWindowTitle("Loading File")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(300)  # 显示对话框前的最小延迟毫秒数
                progress.setValue(0)
            
            # 再次打开文件进行实际加载
            with h5py.File(file_path, 'r') as h5file:
                # 获取基本信息
                self.file_info = {
                    "File Type": "HDF5",
                    "File Path": file_path,
                    "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                    "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 获取采样率
                if 'sampling_rate' in h5file.attrs:
                    self.sampling_rate = float(h5file.attrs['sampling_rate'])
                    self.file_info["Sampling Rate"] = f"{self.sampling_rate} Hz"
                
                # 获取其他元数据
                for attr_name in h5file.attrs:
                    if attr_name != 'sampling_rate':
                        attr_value = h5file.attrs[attr_name]
                        self.file_info[attr_name] = str(attr_value)
                        # 存储原始类型的元数据
                        self.metadata[attr_name] = attr_value
                
                # 加载数据集
                self.current_data = {}
                datasets_count = 0
                
                # 遍历所有数据集
                def extract_datasets(name, obj):
                    if isinstance(obj, h5py.Dataset):
                        # 只加载数值型数据集
                        if obj.dtype.kind in 'iuf':  # 整数, 无符号整数, 浮点数
                            try:
                                data = obj[:]
                                # 始终保存原始数据用于计算
                                if self.original_data is None:
                                    self.original_data = {}
                                self.original_data[name] = data
                                
                                # 对非常大的数据集进行降采样用于显示
                                if isinstance(data, np.ndarray) and len(data) > 1000000:
                                    # 计算降采样率以保留约1M点
                                    downsample_factor = max(1, int(len(data) / 1000000))
                                    self.current_data[name] = data[::downsample_factor]
                                    # 记录降采样信息
                                    self.file_info[f"{name} Downsampling"] = f"Original: {len(data)}, Downsampled: {len(data[::downsample_factor])}"
                                else:
                                    self.current_data[name] = data
                                
                                nonlocal datasets_count
                                datasets_count += 1
                                
                                # 更新进度
                                if progress:
                                    progress.setValue(datasets_count)
                                    # 如果用户取消，则中断加载
                                    if progress.wasCanceled():
                                        return
                            except Exception as e:
                                print(f"Error loading dataset {name}: {str(e)}")
                
                h5file.visititems(extract_datasets)
                self.file_info["Datasets Count"] = str(datasets_count)
                
                # 关闭进度对话框
                if progress:
                    progress.setValue(datasets_total)
            
            return True, self.current_data, self.file_info
            
        except Exception as e:
            if 'progress' in locals() and progress:
                progress.close()
            return False, None, {"Error": str(e)}
    
    def get_channel_names(self):
        """获取所有通道名称"""
        if self.current_data:
            return list(self.current_data.keys())
        return []
    
    def get_channel_data(self, channel_name, use_original=False):
        """获取指定通道的数据
        
        Args:
            channel_name: 通道名称
            use_original: 是否使用原始数据（用于PSD计算）
        """
        if use_original and self.original_data and channel_name in self.original_data:
            return self.original_data[channel_name]
        elif self.current_data and channel_name in self.current_data:
            return self.current_data[channel_name]
        return None
    
    def get_time_axis(self, channel_name=None):
        """获取时间轴"""
        if self.current_data:
            if channel_name and channel_name in self.current_data:
                data_length = len(self.current_data[channel_name])
            elif len(self.current_data) > 0:
                first_channel = list(self.current_data.keys())[0]
                data_length = len(self.current_data[first_channel])
            else:
                return None
            
            return np.arange(data_length) / self.sampling_rate
        return None
    
    def get_memory_usage(self):
        """估计当前加载数据的内存使用量"""
        if not self.current_data:
            return 0
        
        total_bytes = 0
        for name, data in self.current_data.items():
            if hasattr(data, 'nbytes'):
                total_bytes += data.nbytes
        
        # 返回MB
        return total_bytes / (1024 * 1024)


# 兼容旧代码的类名别名
H5FileLoader = DataLoader
