#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Segment Data Manager - 数据分段管理器
用于将大数据集分段处理，并保存每个段的处理结果
"""

import numpy as np
from typing import Dict, Tuple, Optional, Any


class SegmentDataManager:
    """数据分段管理器
    
    负责将完整数据集分成多个段，管理每个段的处理结果，
    并提供段之间的切换和结果保存功能。
    """
    
    def __init__(self, data=None, sampling_rate=1000.0, num_segments=10):
        """初始化分段管理器
        
        参数:
            data: numpy数组，完整的数据
            sampling_rate: 采样率（Hz）
            num_segments: 分段数量
        """
        self.full_data = None
        self.sampling_rate = sampling_rate
        self.num_segments = num_segments
        
        # 分段信息
        self.segment_indices = []  # [(start_idx, end_idx), ...]
        self.segment_results = {}  # {segment_idx: {'auto_peaks': ..., 'manual_peaks': ...}}
        
        if data is not None:
            self.set_data(data, sampling_rate, num_segments)
    
    def set_data(self, data, sampling_rate=1000.0, num_segments=10):
        """设置数据并计算分段
        
        参数:
            data: numpy数组，完整的数据
            sampling_rate: 采样率（Hz）
            num_segments: 分段数量
        """
        self.full_data = data
        self.sampling_rate = sampling_rate
        self.num_segments = max(1, num_segments)
        
        # 清空之前的结果
        self.segment_results = {}
        
        # 计算分段索引
        self._calculate_segment_indices()
    
    def _calculate_segment_indices(self):
        """计算每个段的起止索引"""
        if self.full_data is None:
            self.segment_indices = []
            return
        
        data_length = len(self.full_data)
        segment_size = data_length // self.num_segments
        
        self.segment_indices = []
        for i in range(self.num_segments):
            start_idx = i * segment_size
            # 最后一段包含所有剩余数据
            if i == self.num_segments - 1:
                end_idx = data_length
            else:
                end_idx = (i + 1) * segment_size
            
            self.segment_indices.append((start_idx, end_idx))
    
    def get_segment_data(self, segment_index):
        """获取指定段的数据
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            numpy数组，该段的数据
        """
        if self.full_data is None or not self.segment_indices:
            return None
        
        if segment_index < 0 or segment_index >= len(self.segment_indices):
            return None
        
        start_idx, end_idx = self.segment_indices[segment_index]
        return self.full_data[start_idx:end_idx]
    
    def get_segment_info(self, segment_index):
        """获取指定段的信息
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            字典，包含段的详细信息
        """
        if not self.segment_indices or segment_index < 0 or segment_index >= len(self.segment_indices):
            return None
        
        start_idx, end_idx = self.segment_indices[segment_index]
        segment_length = end_idx - start_idx
        
        # 计算时间信息
        start_time = start_idx / self.sampling_rate
        end_time = end_idx / self.sampling_rate
        duration = segment_length / self.sampling_rate
        
        return {
            'segment_index': segment_index,
            'start_sample': start_idx,
            'end_sample': end_idx,
            'length_samples': segment_length,
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'sampling_rate': self.sampling_rate
        }
    
    def get_global_time_offset(self, segment_index):
        """获取指定段的全局时间偏移
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            浮点数，时间偏移（秒）
        """
        if not self.segment_indices or segment_index < 0 or segment_index >= len(self.segment_indices):
            return 0.0
        
        start_idx, _ = self.segment_indices[segment_index]
        return start_idx / self.sampling_rate
    
    def get_global_sample_offset(self, segment_index):
        """获取指定段的全局样本偏移
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            整数，样本偏移
        """
        if not self.segment_indices or segment_index < 0 or segment_index >= len(self.segment_indices):
            return 0
        
        start_idx, _ = self.segment_indices[segment_index]
        return start_idx
    
    def save_segment_results(self, segment_index, auto_results=None, manual_results=None):
        """保存指定段的处理结果
        
        参数:
            segment_index: 段索引（0-based）
            auto_results: 自动检测结果，字典 {'peaks': [...], 'durations': {...}}
            manual_results: 手动标记结果，列表 [...]
        """
        if segment_index < 0 or segment_index >= self.num_segments:
            return
        
        if segment_index not in self.segment_results:
            self.segment_results[segment_index] = {}
        
        if auto_results is not None:
            self.segment_results[segment_index]['auto'] = auto_results
        
        if manual_results is not None:
            self.segment_results[segment_index]['manual'] = manual_results
    
    def get_segment_results(self, segment_index):
        """获取指定段的处理结果
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            元组 (auto_results, manual_results)
        """
        if segment_index not in self.segment_results:
            return None, None
        
        results = self.segment_results[segment_index]
        auto_results = results.get('auto', None)
        manual_results = results.get('manual', None)
        
        return auto_results, manual_results
    
    def has_segment_results(self, segment_index):
        """检查指定段是否有处理结果
        
        参数:
            segment_index: 段索引（0-based）
            
        返回:
            布尔值
        """
        if segment_index not in self.segment_results:
            return False
        
        results = self.segment_results[segment_index]
        has_auto = 'auto' in results and results['auto'] is not None
        has_manual = 'manual' in results and results['manual'] is not None
        
        return has_auto or has_manual
    
    def get_all_results_combined(self):
        """获取所有段的结果（转换为全局坐标）
        
        返回:
            字典 {'auto_peaks': [...], 'manual_peaks': [...]}
            所有峰值都使用全局时间和样本索引
        """
        all_auto_peaks = []
        all_manual_peaks = []
        
        for segment_idx in sorted(self.segment_results.keys()):
            auto_results, manual_results = self.get_segment_results(segment_idx)
            time_offset = self.get_global_time_offset(segment_idx)
            sample_offset = self.get_global_sample_offset(segment_idx)
            
            # 处理自动检测结果
            if auto_results and 'peaks' in auto_results:
                for peak in auto_results['peaks']:
                    # 复制峰值数据并调整为全局坐标
                    global_peak = peak.copy()
                    if 'index' in global_peak:
                        global_peak['index'] += sample_offset
                    if 'time' in global_peak:
                        global_peak['time'] += time_offset
                    global_peak['segment'] = segment_idx + 1  # 1-based for display
                    all_auto_peaks.append(global_peak)
            
            # 处理手动标记结果
            if manual_results:
                for peak in manual_results:
                    # 复制峰值数据并调整为全局坐标
                    global_peak = peak.copy()
                    if 'index' in global_peak:
                        global_peak['index'] += sample_offset
                    if 'time' in global_peak:
                        global_peak['time'] += time_offset
                    if 'peak_time' in global_peak:
                        global_peak['peak_time'] += time_offset
                    if 'start_time' in global_peak:
                        global_peak['start_time'] += time_offset
                    if 'end_time' in global_peak:
                        global_peak['end_time'] += time_offset
                    global_peak['segment'] = segment_idx + 1  # 1-based for display
                    all_manual_peaks.append(global_peak)
        
        return {
            'auto_peaks': all_auto_peaks,
            'manual_peaks': all_manual_peaks
        }
    
    def clear_all_results(self):
        """清空所有段的处理结果"""
        self.segment_results = {}
    
    def clear_segment_results(self, segment_index):
        """清空指定段的处理结果
        
        参数:
            segment_index: 段索引（0-based）
        """
        if segment_index in self.segment_results:
            del self.segment_results[segment_index]
    
    def get_total_data_length(self):
        """获取完整数据的长度"""
        if self.full_data is None:
            return 0
        return len(self.full_data)
    
    def get_total_duration(self):
        """获取完整数据的时长（秒）"""
        if self.full_data is None:
            return 0.0
        return len(self.full_data) / self.sampling_rate
