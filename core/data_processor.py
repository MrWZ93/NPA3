#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件数据处理模块 - 重构版本
按功能拆分，提高代码可维护性
"""

import os
import numpy as np
import pandas as pd
import h5py
from datetime import datetime
from scipy import signal
import traceback

# 导入示波器CSV文件加载模块
try:
    from core.load_oscilloscope_csv import load_oscilloscope_csv
    OSCILLOSCOPE_CSV_SUPPORT = True
except ImportError:
    OSCILLOSCOPE_CSV_SUPPORT = False
    print("load_oscilloscope_csv module not found, oscilloscope CSV support will be limited")

# 尝试导入不同文件格式的库
try:
    import nptdms
    TDMS_SUPPORT = True
except ImportError:
    TDMS_SUPPORT = False
    print("nptdms library not installed, TDMS format support will not be available")

try:
    import pyabf
    ABF_SUPPORT = True
except ImportError:
    ABF_SUPPORT = False
    print("pyabf library not installed, ABF format support will not be available")

# 设置CSV格式支持
CSV_SUPPORT = True
print("CSV format support enabled")


class DataProcessorBase:
    """数据处理基类，包含通用方法和工具函数"""
    
    def __init__(self):
        self.sampling_rate = 1000.0  # Default sampling rate
    
    def validate_parameters(self, operation, params):
        """验证处理参数"""
        if not params:
            return False, "No parameters provided"
        
        # 获取采样率
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        if sampling_rate <= 0:
            return False, "Invalid sampling rate"
        
        # 验证具体操作的参数
        if operation == "裁切":
            start_time = params.get("start_time", 0)
            end_time = params.get("end_time", 10)
            if start_time >= end_time:
                return False, "Start time must be less than end time"
            if start_time < 0 or end_time < 0:
                return False, "Time values must be non-negative"
        
        elif operation in ["低通滤波", "高通滤波"]:
            cutoff_hz = params.get("cutoff_hz", 1000)
            nyquist = sampling_rate / 2
            if cutoff_hz <= 0:
                return False, "Cutoff frequency must be positive"
            if cutoff_hz >= nyquist:
                return False, f"Cutoff frequency must be less than Nyquist frequency ({nyquist} Hz)"
        
        elif operation == "基线校正":
            fit_start = params.get("fit_start_time", 0)
            fit_end = params.get("fit_end_time", 6)
            if fit_start >= fit_end:
                return False, "Fit start time must be less than fit end time"
        
        return True, "Parameters valid"
    
    def get_time_axis(self, data_length, current_time_axis=None):
        """获取或生成时间轴"""
        if current_time_axis is not None and len(current_time_axis) == data_length:
            return current_time_axis
        else:
            return np.arange(data_length) / self.sampling_rate
    
    def ensure_channel_consistency(self, processed_data, original_data):
        """确保处理后的数据通道一致性"""
        if isinstance(processed_data, dict) and isinstance(original_data, dict):
            # 确保所有通道长度一致
            lengths = [len(data) for data in processed_data.values() if isinstance(data, np.ndarray)]
            if lengths and len(set(lengths)) > 1:
                # 如果长度不一致，以最短的为准
                min_length = min(lengths)
                for channel in processed_data:
                    if isinstance(processed_data[channel], np.ndarray):
                        processed_data[channel] = processed_data[channel][:min_length]
        
        return processed_data


class TrimProcessor(DataProcessorBase):
    """数据裁切处理器 - 支持正剪切和负剪切"""
    
    def process(self, data, params, current_time_axis=None):
        """执行数据裁切"""
        start_time = params.get("start_time", 0)
        end_time = params.get("end_time", 10.0)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        trim_mode = params.get("trim_mode", "positive")  # 默认正剪切
        negative_strategy = params.get("negative_strategy", "smart_fill")  # 默认智能填补
        
        print(f"TRIM: Operation=trim, mode={trim_mode}, start_time={start_time}, end_time={end_time}")
        if trim_mode == "negative":
            print(f"TRIM: Negative strategy={negative_strategy}")
        
        processed_data = {}
        
        if isinstance(data, dict):
            # 处理字典格式数据
            channels_to_process = [selected_channel] if selected_channel else data.keys()
            has_time_channel = "Time" in data
            
            # 如果没有Time通道但有current_time_axis，且是正剪切，需要创建保持原始时间轴的Time通道
            if not has_time_channel and current_time_axis is not None and trim_mode == "positive":
                # 计算裁切区间的索引
                start_indices = np.where(current_time_axis >= start_time)[0]
                end_indices = np.where(current_time_axis <= end_time)[0]
                
                if len(start_indices) > 0 and len(end_indices) > 0:
                    start_sample = start_indices[0]
                    end_sample = end_indices[-1] + 1
                    
                    # 创建保持原始时间值的Time通道
                    trimmed_time_axis = current_time_axis[start_sample:end_sample]
                    processed_data["Time"] = trimmed_time_axis
                    print(f"TRIM: Created Time channel with original time values: {trimmed_time_axis[0]:.3f}s - {trimmed_time_axis[-1]:.3f}s")
            
            for channel in data.keys():
                channel_data = data[channel]
                
                if channel in channels_to_process or channel == "Time":
                    if isinstance(channel_data, np.ndarray):
                        if trim_mode == "positive":
                            processed_data[channel] = self._positive_trim_channel_data(
                                channel, channel_data, start_time, end_time, 
                                sampling_rate, current_time_axis, has_time_channel, data
                            )
                        else:  # negative trim
                            processed_data[channel] = self._negative_trim_channel_data(
                                channel, channel_data, start_time, end_time,
                                sampling_rate, current_time_axis, has_time_channel, data,
                                negative_strategy
                            )
                    else:
                        processed_data[channel] = channel_data
                else:
                    processed_data[channel] = channel_data
        
        elif isinstance(data, np.ndarray):
            # 处理NumPy数组格式数据
            if trim_mode == "positive":
                processed_data = self._positive_trim_array_data(data, start_time, end_time, sampling_rate)
                
                # 如果有current_time_axis，也需要保持原始时间轴
                if current_time_axis is not None:
                    start_indices = np.where(current_time_axis >= start_time)[0]
                    end_indices = np.where(current_time_axis <= end_time)[0]
                    
                    if len(start_indices) > 0 and len(end_indices) > 0:
                        start_sample = start_indices[0]
                        end_sample = end_indices[-1] + 1
                        trimmed_time_axis = current_time_axis[start_sample:end_sample]
                        
                        # 返回字典格式以包含时间轴
                        processed_data = {
                            "Time": trimmed_time_axis,
                            "Data": processed_data
                        }
                        print(f"TRIM: Added Time channel with original time values: {trimmed_time_axis[0]:.3f}s - {trimmed_time_axis[-1]:.3f}s")
            else:  # negative trim
                processed_data = self._negative_trim_array_data(
                    data, start_time, end_time, sampling_rate, current_time_axis, negative_strategy
                )
        
        return processed_data
    
    def _positive_trim_channel_data(self, channel, data, start_time, end_time, sampling_rate, 
                          current_time_axis, has_time_channel, all_data):
        """正剪切：保留指定区间内的数据，保持原始时间轴"""
        print(f"POSITIVE_TRIM: Processing channel={channel}, data_length={len(data)}")
        
        if current_time_axis is not None and len(current_time_axis) == len(data):
            # 使用可视化组件提供的时间轴
            time_axis = current_time_axis
            start_indices = np.where(time_axis >= start_time)[0]
            end_indices = np.where(time_axis <= end_time)[0]
            
            if len(start_indices) == 0 or len(end_indices) == 0:
                raise ValueError(f"时间范围超出数据范围")
            
            start_sample = start_indices[0]
            end_sample = end_indices[-1] + 1
            
        elif channel == "Time" and has_time_channel:
            # 处理Time通道 - 保持原始时间轴值
            start_indices = np.where(data >= start_time)[0]
            end_indices = np.where(data <= end_time)[0]
            
            if len(start_indices) == 0 or len(end_indices) == 0:
                raise ValueError(f"时间范围超出数据范围")
            
            start_sample = start_indices[0]
            end_sample = end_indices[-1] + 1
            
            # 直接返回裁切后的原始时间轴数据（不重置为从0开始）
            trimmed_data = data[start_sample:end_sample]
            print(f"POSITIVE_TRIM: Channel {channel} kept samples {start_sample} to {end_sample-1}, time range: {trimmed_data[0]:.3f}s - {trimmed_data[-1]:.3f}s")
            return trimmed_data
        
        else:
            # 使用采样率计算索引
            start_sample = int(start_time * sampling_rate)
            end_sample = int(end_time * sampling_rate)
            
            # 如果没有Time通道但有current_time_axis，需要保持时间对应关系
            if current_time_axis is not None and not has_time_channel:
                # 使用时间轴计算的索引来裁切数据
                time_axis = current_time_axis
                start_indices = np.where(time_axis >= start_time)[0]
                end_indices = np.where(time_axis <= end_time)[0]
                
                if len(start_indices) > 0 and len(end_indices) > 0:
                    start_sample = start_indices[0]
                    end_sample = end_indices[-1] + 1
        
        # 确保索引范围有效
        start_sample = max(0, min(start_sample, len(data) - 1))
        end_sample = max(start_sample + 1, min(end_sample, len(data)))
        
        trimmed_data = data[start_sample:end_sample]
        print(f"POSITIVE_TRIM: Channel {channel} kept samples {start_sample} to {end_sample-1}")
        
        return trimmed_data
    
    def _positive_trim_array_data(self, data, start_time, end_time, sampling_rate):
        """正剪切NumPy数组数据"""
        start_sample = int(start_time * sampling_rate)
        end_sample = int(end_time * sampling_rate)
        
        start_sample = max(0, min(start_sample, data.shape[0] - 1))
        end_sample = max(start_sample + 1, min(end_sample, data.shape[0]))
        
        return data[start_sample:end_sample]
    
    def _negative_trim_channel_data(self, channel, data, start_time, end_time, sampling_rate,
                                  current_time_axis, has_time_channel, all_data, strategy):
        """负剪切：删除指定区间内的数据，保留区间外数据"""
        print(f"NEGATIVE_TRIM: Processing channel={channel}, data_length={len(data)}, strategy={strategy}")
        
        # 计算区间的索引
        if current_time_axis is not None and len(current_time_axis) == len(data):
            time_axis = current_time_axis
            start_indices = np.where(time_axis >= start_time)[0]
            end_indices = np.where(time_axis <= end_time)[0]
            
            if len(start_indices) == 0 or len(end_indices) == 0:
                print(f"NEGATIVE_TRIM: Time range outside data range, returning original data")
                return data.copy()
            
            start_sample = start_indices[0]
            end_sample = end_indices[-1] + 1
            
        elif channel == "Time" and has_time_channel:
            start_indices = np.where(data >= start_time)[0]
            end_indices = np.where(data <= end_time)[0]
            
            if len(start_indices) == 0 or len(end_indices) == 0:
                print(f"NEGATIVE_TRIM: Time range outside data range, returning original data")
                return data.copy()
            
            start_sample = start_indices[0]
            end_sample = end_indices[-1] + 1
        else:
            start_sample = int(start_time * sampling_rate)
            end_sample = int(end_time * sampling_rate)
        
        # 确保索引范围有效
        start_sample = max(0, min(start_sample, len(data) - 1))
        end_sample = max(start_sample + 1, min(end_sample, len(data)))
        
        if strategy == "delete_shift":
            # 策略一：删除区间数据 + 后续数据平移
            before_data = data[:start_sample]
            after_data = data[end_sample:]
            
            # 特殊处理 Time 通道:需要平移时间轴使其连续
            if channel == "Time" or (current_time_axis is not None and len(current_time_axis) == len(data)):
                # 计算被删除的时间长度
                if len(before_data) > 0 and len(after_data) > 0:
                    time_gap = after_data[0] - before_data[-1]  # 删除区间造成的时间间隔
                    # 将后半部分的时间平移,使时间轴连续
                    processed_data = np.concatenate([before_data, after_data - time_gap])
                    print(f"NEGATIVE_TRIM: Channel {channel} time shifted by {time_gap:.6f}s to make continuous")
                    print(f"NEGATIVE_TRIM: Time range after shift: {processed_data[0]:.3f}s - {processed_data[-1]:.3f}s")
                else:
                    processed_data = np.concatenate([before_data, after_data])
            else:
                processed_data = np.concatenate([before_data, after_data])
            
            print(f"NEGATIVE_TRIM: Channel {channel} deleted samples {start_sample}-{end_sample-1}, new length={len(processed_data)}")
            
        else:  # smart_fill
            # 策略二：智能数据填补
            processed_data = self._smart_fill_data(data, start_sample, end_sample, channel)
        
        return processed_data
    
    def _negative_trim_array_data(self, data, start_time, end_time, sampling_rate, current_time_axis, strategy):
        """负剪切NumPy数组数据"""
        start_sample = int(start_time * sampling_rate)
        end_sample = int(end_time * sampling_rate)
        
        start_sample = max(0, min(start_sample, data.shape[0] - 1))
        end_sample = max(start_sample + 1, min(end_sample, data.shape[0]))
        
        if strategy == "delete_shift":
            if data.ndim == 1:
                before_data = data[:start_sample]
                after_data = data[end_sample:]
                result = np.concatenate([before_data, after_data])
                
                # 如果有时间轴,也需要处理时间平移
                if current_time_axis is not None:
                    time_before = current_time_axis[:start_sample]
                    time_after = current_time_axis[end_sample:]
                    if len(time_before) > 0 and len(time_after) > 0:
                        time_gap = time_after[0] - time_before[-1]
                        shifted_time = np.concatenate([time_before, time_after - time_gap])
                        # 返回字典格式,包含时间轴
                        return {"Time": shifted_time, "Data": result}
                return result
            else:
                # 多通道数据
                before_data = data[:start_sample, :]
                after_data = data[end_sample:, :]
                result = np.concatenate([before_data, after_data], axis=0)
                
                # 如果有时间轴,也需要处理时间平移
                if current_time_axis is not None:
                    time_before = current_time_axis[:start_sample]
                    time_after = current_time_axis[end_sample:]
                    if len(time_before) > 0 and len(time_after) > 0:
                        time_gap = time_after[0] - time_before[-1]
                        shifted_time = np.concatenate([time_before, time_after - time_gap])
                        # 返回字典格式,包含时间轴
                        return {"Time": shifted_time, "Data": result}
                return result
        else:  # smart_fill
            if data.ndim == 1:
                return self._smart_fill_data(data, start_sample, end_sample, "array_data")
            else:
                processed_data = data.copy()
                for i in range(data.shape[1]):
                    processed_data[:, i] = self._smart_fill_data(data[:, i], start_sample, end_sample, f"channel_{i}")
                return processed_data
    
    def _smart_fill_data(self, data, start_sample, end_sample, channel_name):
        """智能数据填补：基于前后10个数据点的统计特征生成新数据"""
        print(f"SMART_FILL: Filling interval [{start_sample}, {end_sample}) for {channel_name}")
        
        # 获取前10个和后10个数据点
        before_start = max(0, start_sample - 10)
        before_data = data[before_start:start_sample]
        
        after_end = min(len(data), end_sample + 10)
        after_data = data[end_sample:after_end]
        
        # 计算统计特征
        if len(before_data) > 0 and len(after_data) > 0:
            # 基准值：前后数据的均值
            before_mean = np.mean(before_data)
            after_mean = np.mean(after_data)
            fill_mean = (before_mean + after_mean) / 2.0
            
            # 标准差：前后数据的标准差
            before_std = np.std(before_data)
            after_std = np.std(after_data)
            fill_std = (before_std + after_std) / 2.0
            
        elif len(before_data) > 0:
            # 只有前面数据
            fill_mean = np.mean(before_data)
            fill_std = np.std(before_data)
        elif len(after_data) > 0:
            # 只有后面数据
            fill_mean = np.mean(after_data)
            fill_std = np.std(after_data)
        else:
            # 没有参考数据，使用默认值
            fill_mean = 0.0
            fill_std = 1.0
        
        # 防止标准差为0
        if fill_std == 0:
            fill_std = 0.01
        
        # 生成新数据
        fill_length = end_sample - start_sample
        fill_data = np.random.normal(fill_mean, fill_std, fill_length)
        
        print(f"SMART_FILL: Generated {fill_length} points with mean={fill_mean:.6f}, std={fill_std:.6f}")
        
        # 填补数据
        processed_data = data.copy()
        processed_data[start_sample:end_sample] = fill_data
        
        return processed_data


class FilterProcessor(DataProcessorBase):
    """滤波处理器"""
    
    def design_filter(self, filter_type, cutoff_hz, sampling_rate, order=4):
        """设计滤波器"""
        nyquist = sampling_rate / 2
        
        # 安全检查：确保截止频率小于奈奎斯特频率
        if cutoff_hz >= nyquist:
            cutoff_hz = 0.99 * nyquist
        
        # 转换为归一化频率
        cutoff_norm = cutoff_hz / nyquist
        
        try:
            b, a = signal.butter(order, cutoff_norm, filter_type)
            return b, a
        except Exception as e:
            raise ValueError(f"滤波器设计失败: {str(e)}")
    
    def apply_filter(self, data, b, a):
        """应用滤波器"""
        if data.ndim == 1:
            return signal.filtfilt(b, a, data)
        else:
            # 多通道数据
            filtered_data = np.zeros_like(data)
            for i in range(data.shape[1]):
                filtered_data[:, i] = signal.filtfilt(b, a, data[:, i])
            return filtered_data
    
    def process_lowpass(self, data, params, current_time_axis=None):
        """低通滤波处理"""
        cutoff_hz = params.get("cutoff_hz", 1000)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        
        b, a = self.design_filter('low', cutoff_hz, sampling_rate)
        return self._apply_filter_to_data(data, b, a, selected_channel)
    
    def process_highpass(self, data, params, current_time_axis=None):
        """高通滤波处理"""
        cutoff_hz = params.get("cutoff_hz", 1000)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        
        b, a = self.design_filter('high', cutoff_hz, sampling_rate)
        return self._apply_filter_to_data(data, b, a, selected_channel)
    
    def _apply_filter_to_data(self, data, b, a, selected_channel=None):
        """将滤波器应用到数据"""
        processed_data = {}
        
        if isinstance(data, dict):
            channels_to_process = [selected_channel] if selected_channel else data.keys()
            
            for channel in data.keys():
                channel_data = data[channel]
                
                if channel in channels_to_process or channel == "Time":
                    if isinstance(channel_data, np.ndarray):
                        if channel == "Time":
                            # 时间通道不进行滤波
                            processed_data[channel] = channel_data.copy()
                        else:
                            # 应用滤波
                            processed_data[channel] = signal.filtfilt(b, a, channel_data)
                    else:
                        processed_data[channel] = channel_data
                else:
                    processed_data[channel] = channel_data
        
        elif isinstance(data, np.ndarray):
            processed_data = self.apply_filter(data, b, a)
        
        return processed_data


class NotchFilterProcessor(DataProcessorBase):
    """陷波滤波处理器"""
    
    def design_notch_filter(self, freq, quality_factor, sampling_rate):
        """设计陷波滤波器"""
        try:
            b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
            return b, a
        except Exception as e:
            raise ValueError(f"陷波滤波器设计失败: {str(e)}")
    
    def get_frequencies_to_remove(self, base_freq, remove_harmonics, max_harmonic, sampling_rate):
        """获取需要移除的频率列表"""
        frequencies = [base_freq]
        
        if remove_harmonics:
            nyquist = sampling_rate / 2
            for harmonic in range(2, max_harmonic + 1):
                harmonic_freq = base_freq * harmonic
                if harmonic_freq < nyquist * 0.95:  # 留5%余量
                    frequencies.append(harmonic_freq)
        
        return frequencies
    
    def process_ac_notch(self, data, params, current_time_axis=None):
        """AC陷波滤波处理"""
        power_freq = params.get("power_frequency", 60)
        quality_factor = params.get("quality_factor", 30)
        remove_harmonics = params.get("remove_harmonics", True)
        max_harmonic = params.get("max_harmonic", 5)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        
        frequencies_to_remove = self.get_frequencies_to_remove(
            power_freq, remove_harmonics, max_harmonic, sampling_rate
        )
        
        return self._apply_notch_filters(data, frequencies_to_remove, quality_factor, 
                                       sampling_rate, selected_channel)
    
    def process_notch(self, data, params, current_time_axis=None):
        """通用陷波滤波处理"""
        notch_freq = params.get("notch_freq", 50)
        quality_factor = params.get("quality_factor", 30)
        remove_harmonics = params.get("remove_harmonics", True)
        max_harmonic = params.get("max_harmonic", 5)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        
        frequencies_to_remove = self.get_frequencies_to_remove(
            notch_freq, remove_harmonics, max_harmonic, sampling_rate
        )
        
        return self._apply_notch_filters(data, frequencies_to_remove, quality_factor, 
                                       sampling_rate, selected_channel)
    
    def _apply_notch_filters(self, data, frequencies_to_remove, quality_factor, 
                           sampling_rate, selected_channel=None):
        """应用陷波滤波器"""
        processed_data = {}
        
        if isinstance(data, dict):
            channels_to_process = [selected_channel] if selected_channel else data.keys()
            
            for channel in data.keys():
                channel_data = data[channel]
                
                if channel in channels_to_process or channel == "Time":
                    if isinstance(channel_data, np.ndarray):
                        if channel == "Time":
                            # 时间通道不进行滤波
                            processed_data[channel] = channel_data.copy()
                        else:
                            # 应用陷波滤波器组
                            filtered_data = channel_data.copy().astype(np.float64)
                            for freq in frequencies_to_remove:
                                b, a = self.design_notch_filter(freq, quality_factor, sampling_rate)
                                filtered_data = signal.filtfilt(b, a, filtered_data)
                            processed_data[channel] = filtered_data
                    else:
                        processed_data[channel] = channel_data
                else:
                    processed_data[channel] = channel_data
        
        elif isinstance(data, np.ndarray):
            if data.ndim == 1:
                filtered_data = data.copy().astype(np.float64)
                for freq in frequencies_to_remove:
                    b, a = self.design_notch_filter(freq, quality_factor, sampling_rate)
                    filtered_data = signal.filtfilt(b, a, filtered_data)
                processed_data = filtered_data
            else:
                processed_data = np.zeros_like(data, dtype=np.float64)
                for i in range(data.shape[1]):
                    filtered_data = data[:, i].copy().astype(np.float64)
                    for freq in frequencies_to_remove:
                        b, a = self.design_notch_filter(freq, quality_factor, sampling_rate)
                        filtered_data = signal.filtfilt(b, a, filtered_data)
                    processed_data[:, i] = filtered_data
        
        print(f"陷波滤波应用: 移除频率 {frequencies_to_remove} Hz")
        return processed_data


class BaselineCorrectionProcessor(DataProcessorBase):
    """基线校正处理器 - 基于用户参考代码实现"""
    
    def process(self, data, params, current_time_axis=None):
        """基线校正处理"""
        fit_start_time = params.get("fit_start_time", 0.0)
        fit_end_time = params.get("fit_end_time", 6.0)
        correction_method = params.get("correction_method", "linear")
        preserve_mean = params.get("preserve_mean", True)
        sampling_rate = params.get("sampling_rate", self.sampling_rate)
        selected_channel = params.get("channel", None)
        
        print(f"BASELINE_CORRECTION: fit_start={fit_start_time}s, fit_end={fit_end_time}s, method={correction_method}")
        print(f"BASELINE_CORRECTION: preserve_mean={preserve_mean}")
        
        processed_data = {}
        
        if isinstance(data, dict):
            channels_to_process = [selected_channel] if selected_channel else data.keys()
            
            for channel in data.keys():
                channel_data = data[channel]
                
                if channel in channels_to_process or channel == "Time":
                    if isinstance(channel_data, np.ndarray):
                        if channel == "Time":
                            # 时间通道不进行校正
                            processed_data[channel] = channel_data.copy()
                        else:
                            # 进行基线校正
                            baseline_method = params.get("baseline_method", "first_n_seconds")
                            first_n_seconds = params.get("first_n_seconds", 4.0)
                            processed_data[channel] = self._correct_baseline_reference_style(
                                channel, channel_data, fit_start_time, fit_end_time,
                                correction_method, preserve_mean, sampling_rate, 
                                current_time_axis, data, baseline_method, first_n_seconds
                            )
                    else:
                        processed_data[channel] = channel_data
                else:
                    processed_data[channel] = channel_data
        
        elif isinstance(data, np.ndarray):
            # 对NumPy数组进行基线校正
            time_axis = self.get_time_axis(len(data), current_time_axis)
            baseline_method = params.get("baseline_method", "first_n_seconds")
            first_n_seconds = params.get("first_n_seconds", 4.0)
            processed_data = self._correct_baseline_array_reference_style(
                data, time_axis, fit_start_time, fit_end_time,
                correction_method, preserve_mean, baseline_method, first_n_seconds
            )
        
        return processed_data
    
    def _correct_baseline_reference_style(self, channel, data, fit_start_time, fit_end_time,
                                         correction_method, preserve_mean, sampling_rate, 
                                         current_time_axis, all_data, baseline_method=None, first_n_seconds=None):
        """对单个通道进行基线校正 - 参考用户代码实现"""
        # 获取时间轴数据
        if current_time_axis is not None and len(current_time_axis) == len(data):
            time_data = current_time_axis
            print(f"BASELINE_CORRECTION: 使用可视化时间轴")
        elif "Time" in all_data:
            time_data = all_data["Time"]
            print(f"BASELINE_CORRECTION: 使用数据中的Time通道")
        else:
            time_data = np.arange(len(data)) / sampling_rate
            print(f"BASELINE_CORRECTION: 使用采样率生成时间轴")
        
        print(f"BASELINE_CORRECTION: 时间轴范围: {np.min(time_data):.3f}s 到 {np.max(time_data):.3f}s")
        print(f"BASELINE_CORRECTION: 数据长度: {len(data)}, 时间轴长度: {len(time_data)}")
        
        # 计算相对时间（从0开始）- 与用户参考代码一致
        time_start = time_data[0]
        relative_time = time_data - time_start
        
        print(f"BASELINE_CORRECTION: time_start = {time_start:.3f}s")
        print(f"BASELINE_CORRECTION: 相对时间范围: {np.min(relative_time):.3f}s 到 {np.max(relative_time):.3f}s")
        
        # 根据基线校正方法选择拟合区域
        if baseline_method == "first_n_seconds" and first_n_seconds is not None:
            # 方法1：选择前N秒（与用户参考代码一致）
            print(f"BASELINE_CORRECTION: 使用前N秒方式，N = {first_n_seconds:.3f}s")
            fit_mask = relative_time <= first_n_seconds  # 与用户参考代码完全一致
        else:
            # 方法2：选择时间范围（高级方式）
            print(f"BASELINE_CORRECTION: 使用时间范围方式: {fit_start_time:.3f}s 到 {fit_end_time:.3f}s")
            fit_mask = (relative_time >= fit_start_time) & (relative_time <= fit_end_time)
        
        if not np.any(fit_mask):
            if baseline_method == "first_n_seconds":
                raise ValueError(f"前N秒参数 {first_n_seconds:.3f}s 超出数据范围 [{np.min(relative_time):.3f}s, {np.max(relative_time):.3f}s]")
            else:
                raise ValueError(f"拟合时间区间 [{fit_start_time:.3f}s, {fit_end_time:.3f}s] 超出数据范围 [{np.min(relative_time):.3f}s, {np.max(relative_time):.3f}s]")
        
        fit_time = relative_time[fit_mask]
        fit_data = data[fit_mask]
        
        print(f"BASELINE_CORRECTION: 拟合区域数据点数量: {len(fit_data)}")
        print(f"BASELINE_CORRECTION: 拟合时间范围: {np.min(fit_time):.3f}s 到 {np.max(fit_time):.3f}s")
        
        # 进行线性拟合 - 与用户参考代码一致
        if correction_method == "linear":
            # 使用线性拟合 (y = ax + b)
            coeffs = np.polyfit(fit_time, fit_data, 1)
            slope = coeffs[0]  # 斜率
            intercept = coeffs[1]  # 截距
            
            print(f"BASELINE_CORRECTION: 线性拟合结果: 斜率 = {slope:.6f}, 截距 = {intercept:.6f}")
            
            # 计算拟合线在所有时间点的值（使用相对时间）- 与用户参考代码一致
            fitted_line = slope * relative_time + intercept
            
        else:
            # 对于非线性拟合，使用通用方法
            fitted_line = self._fit_baseline_reference_style(fit_time, fit_data, relative_time, correction_method)
        
        # 用整体数据减去拟合的斜率趋势（去趋势化处理）- 与用户参考代码一致
        if preserve_mean:
            original_mean = np.mean(data)
            processed_data = data - fitted_line + intercept
            print(f"BASELINE_CORRECTION: 保持原始均值: {intercept:.6f}")
        else:
            processed_data = data - fitted_line
            print(f"BASELINE_CORRECTION: 直接减去基线")
        
        print(f"BASELINE_CORRECTION: Channel {channel} 基线校正完成")
        print(f"BASELINE_CORRECTION: 处理前数据范围: [{np.min(data):.6f}, {np.max(data):.6f}]")
        print(f"BASELINE_CORRECTION: 处理后数据范围: [{np.min(processed_data):.6f}, {np.max(processed_data):.6f}]")
        
        return processed_data
    
    def _correct_baseline_array_reference_style(self, data, time_axis, fit_start_time, fit_end_time,
                                               correction_method, preserve_mean, baseline_method=None, first_n_seconds=None):
        """对NumPy数组进行基线校正 - 参考用户代码实现"""
        # 计算相对时间（从0开始）
        time_start = time_axis[0]
        relative_time = time_axis - time_start
        
        # 根据基线校正方法选择拟合区域
        if baseline_method == "first_n_seconds" and first_n_seconds is not None:
            fit_mask = relative_time <= first_n_seconds
        else:
            fit_mask = (relative_time >= fit_start_time) & (relative_time <= fit_end_time)
        
        if not np.any(fit_mask):
            raise ValueError(f"拟合时间区间超出数据范围")
        
        if data.ndim == 1:
            fit_time = relative_time[fit_mask]
            fit_data = data[fit_mask]
            
            if correction_method == "linear":
                # 线性拟合
                coeffs = np.polyfit(fit_time, fit_data, 1)
                slope, intercept = coeffs[0], coeffs[1]
                fitted_line = slope * relative_time + intercept
            else:
                fitted_line = self._fit_baseline_reference_style(fit_time, fit_data, relative_time, correction_method)
            
            if preserve_mean:
                return data - fitted_line + np.mean(data)
            else:
                return data - fitted_line
        else:
            # 多通道数据
            corrected_data = np.zeros_like(data)
            for i in range(data.shape[1]):
                fit_time = relative_time[fit_mask]
                fit_data = data[fit_mask, i]
                
                if correction_method == "linear":
                    coeffs = np.polyfit(fit_time, fit_data, 1)
                    slope, intercept = coeffs[0], coeffs[1]
                    fitted_line = slope * relative_time + intercept
                else:
                    fitted_line = self._fit_baseline_reference_style(fit_time, fit_data, relative_time, correction_method)
                
                if preserve_mean:
                    corrected_data[:, i] = data[:, i] - fitted_line + np.mean(data[:, i])
                else:
                    corrected_data[:, i] = data[:, i] - fitted_line
            
            return corrected_data
    
    def _fit_baseline_reference_style(self, fit_time, fit_data, full_time, method):
        """拟合基线 - 参考用户代码实现"""
        if method == "linear":
            coeffs = np.polyfit(fit_time, fit_data, 1)
            slope, intercept = coeffs[0], coeffs[1]
            fitted_baseline = slope * full_time + intercept
        elif method == "poly2":
            coeffs = np.polyfit(fit_time, fit_data, 2)
            fitted_baseline = np.polyval(coeffs, full_time)
        elif method == "poly3":
            coeffs = np.polyfit(fit_time, fit_data, 3)
            fitted_baseline = np.polyval(coeffs, full_time)
        else:
            # 默认使用线性拟合
            coeffs = np.polyfit(fit_time, fit_data, 1)
            slope, intercept = coeffs[0], coeffs[1]
            fitted_baseline = slope * full_time + intercept
        
        print(f"BASELINE_CORRECTION: 拟合系数: {coeffs}")
        return fitted_baseline
    
    def _fit_baseline(self, fit_time, fit_data, full_time, method):
        """拟合基线 - 保留旧版本兼容性"""
        if method == "linear":
            coeffs = np.polyfit(fit_time, fit_data, 1)
        elif method == "poly2":
            coeffs = np.polyfit(fit_time, fit_data, 2)
        elif method == "poly3":
            coeffs = np.polyfit(fit_time, fit_data, 3)
        else:
            # 默认使用线性拟合
            coeffs = np.polyfit(fit_time, fit_data, 1)
        
        fitted_baseline = np.polyval(coeffs, full_time)
        print(f"BASELINE_CORRECTION: 拟合系数: {coeffs}")
        return fitted_baseline


class FileDataProcessor:
    """文件数据处理类 - 重构版本"""
    def __init__(self):
        self.current_data = None
        self.file_info = {}
        self.file_path = None
        self.file_type = None
        self.sampling_rate = 1000.0  # Default sampling rate
        
        # 初始化处理器
        self.trim_processor = TrimProcessor()
        self.filter_processor = FilterProcessor()
        self.notch_processor = NotchFilterProcessor()
        self.baseline_processor = BaselineCorrectionProcessor()
        
        # 设置采样率
        self._update_processors_sampling_rate()
    
    def _update_processors_sampling_rate(self):
        """更新所有处理器的采样率"""
        processors = [self.trim_processor, self.filter_processor, 
                     self.notch_processor, self.baseline_processor]
        for processor in processors:
            processor.sampling_rate = self.sampling_rate
    
    def load_file(self, file_path):
        """加载文件"""
        self.file_path = file_path
        self.file_type = os.path.splitext(file_path)[1].lower()
        
        try:
            if self.file_type == '.tdms' and TDMS_SUPPORT:
                self._load_tdms(file_path)
            elif self.file_type == '.h5':
                self._load_h5(file_path)
            elif self.file_type == '.abf' and ABF_SUPPORT:
                self._load_abf(file_path)
            elif self.file_type == '.csv' and CSV_SUPPORT:
                self._load_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {self.file_type}")
            
            return True, self.current_data, self.file_info
            
        except Exception as e:
            return False, None, {"Error": str(e)}
    
    def _load_tdms(self, file_path):
        """加载TDMS文件"""
        tdms_file = nptdms.TdmsFile.read(file_path)
        
        # 获取基本信息
        self.file_info = {
            "File Type": "TDMS",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": len(tdms_file.groups())
        }
        
        # 加载数据
        self.current_data = {}
        for group in tdms_file.groups():
            for channel in group.channels():
                channel_name = f"{group.name}/{channel.name}"
                self.current_data[channel_name] = channel[:]
    
    def _load_h5(self, file_path):
        """加载H5文件"""
        with h5py.File(file_path, 'r') as h5file:
            # 获取基本信息
            self.file_info = {
                "File Type": "HDF5",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Dataset Count": len(h5file.keys())
            }
            
            # 加载主要数据集
            self.current_data = {}
            
            def extract_datasets(name, obj):
                if isinstance(obj, h5py.Dataset):
                    # 只加载数值型数据集
                    if obj.dtype.kind in 'iuf':  # 整数, 无符号整数, 浮点数
                        try:
                            self.current_data[name] = obj[:]
                        except Exception as e:
                            import logging
                            logging.warning(f"Could not load dataset {name}: {str(e)}")
                            self.current_data[name] = "Dataset too large or incompatible format"
            
            h5file.visititems(extract_datasets)
    
    def _load_abf(self, file_path):
        """加载ABF文件"""
        abf = pyabf.ABF(file_path)
        
        # 获取基本信息
        self.file_info = {
            "File Type": "ABF",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": abf.channelCount,
            "Sampling Rate": f"{abf.dataRate} Hz",
            "Sample Points": abf.sweepPointCount,
            "Protocol": abf.protocol,
            "Creation Time": abf.abfDateTime
        }
        
        # 加载数据
        self.current_data = {}
        for i in range(abf.channelCount):
            abf.setSweep(sweepNumber=0, channel=i)
            self.current_data[f"Channel {i+1}"] = abf.sweepY
        
        # Store the sampling rate
        self.sampling_rate = abf.dataRate
        self._update_processors_sampling_rate()
    
    def _load_csv(self, file_path):
        """加载CSV文件 - 优化版本，添加示波器CSV支持"""
        # 初始化变量，防止finally块引用未声明的变量
        old_thread_count = None
        
        try:
            import logging
            logging.info(f"Loading CSV file: {file_path}")
            
            # 检查文件路径是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 控制pandas的多线程设置
            try:
                old_thread_count = pd.options.io_thread_count
                pd.options.io_thread_count = 1  # 强制使用单线程模式
            except Exception as thread_exc:
                logging.warning(f"Failed to set thread count: {str(thread_exc)}")
            
            # 首先尝试使用示波器CSV加载器
            if OSCILLOSCOPE_CSV_SUPPORT:
                try:
                    # 判断是否可能是示波器CSV格式
                    is_oscilloscope = False
                    with open(file_path, 'r', errors='replace') as f:
                        for i in range(10):  # 检查前10行
                            line = f.readline()
                            if not line:
                                break
                            if any(keyword in line for keyword in ["Model", "BlockNumber", "TraceName", "Xviewer", "HResolution"]):
                                is_oscilloscope = True
                                break
                    
                    if is_oscilloscope:
                        logging.info("Detected possible oscilloscope CSV format, using specialized loader")
                        # 调用示波器CSV加载器，设置force_time_from_zero=True使时间轴从0开始
                        data_dict, file_info, sampling_rate = load_oscilloscope_csv(file_path, force_time_from_zero=True)
                        if data_dict is not None and file_info is not None:
                            # 示波器CSV文件成功加载
                            self.current_data = data_dict
                            self.file_info = file_info
                            if sampling_rate is not None and sampling_rate > 0:
                                self.sampling_rate = sampling_rate
                                self._update_processors_sampling_rate()
                            return
                except Exception as osc_error:
                    logging.warning(f"Oscilloscope CSV loader failed: {str(osc_error)}")
                    traceback.print_exc()
            
            # 如果不是示波器格式或示波器加载器不可用，继续使用标准CSV加载
            # 先读取文件内容来分析文件结构
            with open(file_path, 'r', errors='replace', encoding='utf-8-sig') as f:
                file_content = f.read()
            
            # 统一处理行结尾符，将\r\n和\r都转换为\n
            file_content = file_content.replace('\r\n', '\n').replace('\r', '\n')
            lines = file_content.split('\n')
            
            # 检测可能的分隔符（基于前几行非注释行）
            possible_delimiters = [',', '\t', ';', ' ']
            delimiter = ','
            for line in lines[:10]:
                if not line.startswith('#') and line.strip():
                    for d in possible_delimiters:
                        if line.count(d) > 1:
                            delimiter = d
                            break
                    break
            
            # 检测文件是否有头部元数据/注释行和采样率信息
            skip_rows = 0
            sampling_rate_found = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line == "" or line.startswith("#"):
                    skip_rows += 1
                    # 尝试提取采样率信息
                    if "sampling rate" in line.lower() or "sample rate" in line.lower():
                        import re
                        # 查找数字（可能是整数或浮点数）
                        numbers = re.findall(r'[0-9]+\.?[0-9]*', line)
                        if numbers:
                            try:
                                rate = float(numbers[0])
                                if rate > 0:
                                    sampling_rate_found = rate
                                    logging.info(f"Found sampling rate in header: {rate} Hz")
                            except ValueError:
                                pass
                else:
                    break
            
            # 如果找到了采样率，更新默认值
            if sampling_rate_found:
                self.sampling_rate = sampling_rate_found
                self._update_processors_sampling_rate()
            
            # 使用不同方法尝试读取CSV数据
            df = None
            
            # 方法1：使用pandas直接读取
            try:
                # 使用StringIO来处理预处理的内容
                from io import StringIO
                processed_content = '\n'.join(lines[skip_rows:])
                
                df = pd.read_csv(StringIO(processed_content),
                                delimiter=delimiter,
                                on_bad_lines='skip',
                                low_memory=True,
                                dtype=None)
            except Exception as e:
                logging.warning(f"StringIO CSV parsing failed: {str(e)}, trying direct file reading")
            
            # 方法2：如果方法1失败，尝试直接从文件读取
            if df is None:
                try:
                    df = pd.read_csv(file_path,
                                    delimiter=delimiter,
                                    skiprows=skip_rows,
                                    on_bad_lines='skip',
                                    encoding='utf-8-sig',
                                    engine='python')  # 使用python引擎处理特殊情况
                except Exception as e:
                    logging.warning(f"Direct file CSV parsing failed: {str(e)}, trying manual parsing")
            
            # 方法3：如果前两种方法都失败，使用手动解析
            if df is None:
                try:
                    # 手动解析CSV数据
                    import csv
                    from io import StringIO
                    processed_content = '\n'.join(lines[skip_rows:])
                    
                    # 使用csv模块解析
                    reader = csv.reader(StringIO(processed_content), delimiter=delimiter)
                    rows = [row for row in reader if row]  # 过滤空行
                    
                    if not rows:
                        raise ValueError("Cannot parse CSV file, no valid data rows found")
                    
                    # 第一行作为列标题
                    header = [col.strip() for col in rows[0]]
                    data_rows = rows[1:]
                    
                    # 创建DataFrame
                    df = pd.DataFrame(data_rows, columns=header)
                    
                except Exception as e:
                    logging.error(f"Manual CSV parsing also failed: {str(e)}")
                    raise ValueError(f"Cannot parse CSV file: {str(e)}")
            
            # 如果df仍然为空，抛出错误
            if df is None or df.empty:
                raise ValueError("No valid data found in CSV file")
            
            # 尝试将所有可能的列转换为数值
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass  # 无法转换的列保持原样
            
            # 获取基本信息
            self.file_info = {
                "File Type": "CSV",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Rows": len(df),
                "Columns": len(df.columns),
                "Column Names": ", ".join(df.columns.tolist())
            }
            
            # 检查数据类型
            numeric_columns = df.select_dtypes(include=np.number).columns.tolist()
            if numeric_columns:
                self.file_info["Numeric Columns"] = ", ".join(numeric_columns)
            
            # 如果找到了采样率，添加到文件信息中
            if sampling_rate_found:
                self.file_info["Sampling Rate"] = f"{sampling_rate_found} Hz"
            
            # 清理列名（移除两端空格和特殊字符）
            df.columns = [col.strip() for col in df.columns]
            
            # 检查是否有时间相关的列（更广泛的检测）
            time_cols = []
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['time', 'date', '时间', '日期', 'index']):
                    time_cols.append(col)
            
            # 构建数据字典
            self.current_data = {}
            
            # 如果有时间相关列，尝试使用第一个作为时间轴
            time_column_used = None
            if time_cols:
                time_col = time_cols[0]
                try:
                    # 尝试转换为数值类型（对于time_index类型）
                    time_data = pd.to_numeric(df[time_col], errors='coerce')
                    if not time_data.isna().all():  # 如果成功转换为数值
                        self.current_data[time_col] = time_data.values
                        time_column_used = time_col
                        self.file_info["Time Column"] = time_col
                        logging.info(f"Using column '{time_col}' as time axis")
                except Exception as e:
                    logging.warning(f"Failed to process time column '{time_col}': {str(e)}")
            
            # 将所有数值列加载为数据通道
            data_channels_count = 0
            for col in df.columns:
                if col == time_column_used:
                    continue  # 已经处理过的时间列
                    
                try:
                    # 尝试转换为数值类型
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_data.isna().all():  # 如果有有效的数值数据
                        # 将NaN值替换为0
                        self.current_data[col] = numeric_data.fillna(0).values
                        data_channels_count += 1
                    else:
                        logging.warning(f"Column '{col}' contains no valid numeric data, skipping")
                except Exception as e:
                    logging.warning(f"Failed to process column '{col}': {str(e)}")
            
            # 检查是否有有效数据
            if data_channels_count == 0:
                raise ValueError("Cannot find any valid numeric data columns in CSV file")
            
            logging.info(f"Successfully loaded {data_channels_count} data channels from CSV file")
            if time_column_used:
                logging.info(f"Time column: {time_column_used}")
            
            # 添加加载的通道数到文件信息
            self.file_info["Data Channels Loaded"] = data_channels_count
                
        except Exception as e:
            self.file_info = {
                "File Type": "CSV",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Error": f"Error reading CSV file: {str(e)}"
            }
            
            # 错误情况下的示例数据
            self.current_data = {"Error": np.zeros(100)}
            
            # 打印堆栈跟踪信息以便调试
            traceback.print_exc()
            
        finally:
            # 恢复原始pandas设置
            if old_thread_count is not None:
                try:
                    pd.options.io_thread_count = old_thread_count
                except Exception:
                    pass  # 忽略恢复设置时的错误
    
    def process_data(self, operation, params=None, current_time_axis=None):
        """处理数据 - 重构版本，作为调度器"""
        if self.current_data is None:
            return False, None, "No data to process"
        
        try:
            # 更新参数中的采样率
            if params is None:
                params = {}
            params["sampling_rate"] = params.get("sampling_rate", self.sampling_rate)
            
            # 参数验证
            is_valid, error_msg = self.trim_processor.validate_parameters(operation, params)
            if not is_valid:
                return False, None, error_msg
            
            # 根据操作类型调用相应的处理器
            if operation == "裁切":
                processed_data = self.trim_processor.process(self.current_data, params, current_time_axis)
                # 移除自动添加时间轴的逻辑，保持原有通道结构
            
            elif operation == "低通滤波":
                processed_data = self.filter_processor.process_lowpass(self.current_data, params, current_time_axis)
            
            elif operation == "高通滤波":
                processed_data = self.filter_processor.process_highpass(self.current_data, params, current_time_axis)
            
            elif operation == "AC_Notch_Filter":
                processed_data = self.notch_processor.process_ac_notch(self.current_data, params, current_time_axis)
            
            elif operation in ["陷波滤波", "交流电去噪"]:
                processed_data = self.notch_processor.process_notch(self.current_data, params, current_time_axis)
            
            elif operation == "基线校正":
                processed_data = self.baseline_processor.process(self.current_data, params, current_time_axis)
            
            else:
                return False, None, f"Unknown operation: {operation}"
            
            # 数据后处理
            processed_data = self._post_process_data(processed_data)
            
            # 构建返回信息
            success_msg = self._build_success_message(operation, params, processed_data)
            
            return True, processed_data, success_msg
            
        except Exception as e:
            return False, None, f"Processing error: {str(e)}"
    
    def _post_process_data(self, processed_data):
        """数据后处理"""
        # 将悬浮的NaN值设为0
        if isinstance(processed_data, dict):
            for channel in processed_data:
                if isinstance(processed_data[channel], np.ndarray):
                    processed_data[channel] = np.nan_to_num(processed_data[channel])
        elif isinstance(processed_data, np.ndarray):
            processed_data = np.nan_to_num(processed_data)
        
        return processed_data
    
    def _build_success_message(self, operation, params, processed_data):
        """构建成功处理的消息"""
        if operation == "裁切":
            trim_mode = params.get("trim_mode", "positive")
            
            # 计算处理后数据长度
            if isinstance(processed_data, dict):
                data_lengths = [len(data) for data in processed_data.values() if isinstance(data, np.ndarray)]
                if data_lengths:
                    avg_length = int(np.mean(data_lengths))
                    
                    if trim_mode == "positive":
                        if "Time" in processed_data:
                            time_data = processed_data["Time"]
                            if len(time_data) > 0:
                                actual_start = np.min(time_data)
                                actual_end = np.max(time_data)
                                return f"正剪切成功: 保留时间范围 {actual_start:.3f}s - {actual_end:.3f}s (数据点: {len(time_data)})"
                        else:
                            start_time = params.get("start_time", 0)
                            end_time = params.get("end_time", 10)
                            return f"正剪切成功: 保留时间范围 {start_time:.3f}s - {end_time:.3f}s (数据点: {avg_length})"
                    else:  # negative
                        strategy = params.get("negative_strategy", "smart_fill")
                        strategy_name = "智能填补" if strategy == "smart_fill" else "删除平移"
                        start_time = params.get("start_time", 0)
                        end_time = params.get("end_time", 10)
                        return f"负剪切成功 ({strategy_name}): 处理时间范围 {start_time:.3f}s - {end_time:.3f}s (数据点: {avg_length})"
            
            elif isinstance(processed_data, np.ndarray):
                trim_mode_name = "正剪切" if trim_mode == "positive" else "负剪切"
                return f"{trim_mode_name}成功: 数据点 {len(processed_data)}"
        
        return "Processing successful"
    
    def save_processed_data(self, data, save_path):
        """保存处理后的数据为H5格式"""
        try:
            with h5py.File(save_path, 'w') as h5file:
                # 添加元数据
                h5file.attrs['source_file'] = self.file_path
                h5file.attrs['source_type'] = self.file_type
                h5file.attrs['processed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                h5file.attrs['sampling_rate'] = self.sampling_rate
                
                # 存储数据
                if isinstance(data, dict):
                    for channel, values in data.items():
                        if isinstance(values, np.ndarray):
                            h5file.create_dataset(channel, data=values)
                        
                elif isinstance(data, np.ndarray):
                    h5file.create_dataset('data', data=data)
                
                return True, "Data saved successfully"
                
        except Exception as e:
            return False, f"Save error: {str(e)}"
