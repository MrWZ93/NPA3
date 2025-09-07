#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot Utils - 绘图工具函数
提供通用的绘图辅助功能
"""

import numpy as np
import time
from PyQt6.QtCore import QTimer


class RecursionGuard:
    """递归防护工具类"""
    
    def __init__(self):
        self._updating_flags = {}
        self._drawing = False
        self._last_draw_time = 0
        self._draw_throttle_interval = 0.05  # 50ms的绘制间隔限制
        self._signal_emitting = set()  # 记录正在发送的信号
    
    def is_updating(self, key):
        """检查是否正在更新指定操作"""
        return self._updating_flags.get(key, False)
    
    def set_updating(self, key, value):
        """设置更新状态"""
        self._updating_flags[key] = value
    
    def is_signal_emitting(self, signal_name):
        """检查信号是否正在发送"""
        return signal_name in self._signal_emitting
    
    def set_signal_emitting(self, signal_name, emitting):
        """设置信号发送状态"""
        if emitting:
            self._signal_emitting.add(signal_name)
        else:
            self._signal_emitting.discard(signal_name)
    
    def throttled_draw(self, canvas):
        """限制频率的绘制方法"""
        if self._drawing or self.is_updating("draw"):
            return
            
        current_time = time.time()
        
        if current_time - self._last_draw_time < self._draw_throttle_interval:
            return
        
        try:
            self._drawing = True
            self.set_updating("draw", True)
            self._last_draw_time = current_time
            canvas.draw()
        except Exception as e:
            print(f"Error in throttled_draw: {e}")
        finally:
            self._drawing = False
            self.set_updating("draw", False)


class DataCleaner:
    """数据清理工具类"""
    
    @staticmethod
    def clean_data(data):
        """清理数据，移除NaN和Inf值"""
        if data is None:
            return None
            
        try:
            data = np.asarray(data, dtype=np.float64)
            
            invalid_mask = np.isnan(data) | np.isinf(data)
            
            if np.any(invalid_mask):
                print(f"Warning: Found {np.sum(invalid_mask)} invalid values (NaN/Inf) in data")
                
                if np.all(invalid_mask):
                    print("Error: All data values are invalid (NaN/Inf)")
                    return None
                
                if np.sum(~invalid_mask) >= 2:
                    valid_indices = np.where(~invalid_mask)[0]
                    invalid_indices = np.where(invalid_mask)[0]
                    
                    data[invalid_indices] = np.interp(
                        invalid_indices, 
                        valid_indices, 
                        data[valid_indices]
                    )
                    print(f"Interpolated {len(invalid_indices)} invalid values")
                else:
                    data = data[~invalid_mask]
                    print(f"Removed {np.sum(invalid_mask)} invalid values")
            
            if len(data) == 0:
                print("Error: No valid data remaining after cleaning")
                return None
                
            return data
            
        except Exception as e:
            print(f"Error cleaning data: {e}")
            return None


class AxisCalculator:
    """轴计算工具类"""
    
    @staticmethod
    def calculate_safe_ylim(data):
        """安全计算Y轴限制，避免NaN和Inf"""
        try:
            if data is None or len(data) == 0:
                return -1, 1
            
            data = DataCleaner.clean_data(data)
            if data is None or len(data) == 0:
                return -1, 1
            
            data_min = np.min(data)
            data_max = np.max(data)
            
            if not (np.isfinite(data_min) and np.isfinite(data_max)):
                print(f"Warning: Invalid data range: min={data_min}, max={data_max}")
                return -1, 1
            
            if data_min == data_max:
                center_val = data_min if np.isfinite(data_min) else 0
                return center_val - 0.1, center_val + 0.1
            
            data_range = data_max - data_min
            if not np.isfinite(data_range) or data_range == 0:
                return data_min - 0.1, data_max + 0.1
            
            margin = 0.005 * data_range
            y_min = data_min - margin
            y_max = data_max + margin
            
            if not (np.isfinite(y_min) and np.isfinite(y_max)):
                print(f"Warning: Calculated invalid y limits: y_min={y_min}, y_max={y_max}")
                return -1, 1
            
            return y_min, y_max
            
        except Exception as e:
            print(f"Error calculating safe y limits: {e}")
            return -1, 1


class SignalThrottler:
    """信号节流工具类"""
    
    def __init__(self, interval=150):
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(interval)
        self._emitting = False
        self._pending_value = None
        self._callback = None
    
    def setup(self, callback):
        """设置回调函数"""
        self._callback = callback
        self.timer.timeout.connect(self._emit_signal)
    
    def throttle(self, value):
        """节流处理"""
        self._pending_value = value
        self.timer.start()
    
    def _emit_signal(self):
        """发送信号"""
        if self._emitting or self._callback is None:
            return
        try:
            self._emitting = True
            self._callback(self._pending_value)
        finally:
            self._emitting = False


class ColorManager:
    """颜色管理工具类"""
    
    @staticmethod
    def get_cursor_colors():
        """获取cursor颜色列表"""
        return ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    @staticmethod
    def get_fit_colors():
        """获取拟合曲线颜色列表"""
        return ['red', 'blue', 'purple', 'orange', 'green', 'magenta', 'cyan', 'brown', 'olive', 'teal']
    
    @staticmethod
    def get_color_by_index(index, color_type='cursor'):
        """根据索引获取颜色"""
        if color_type == 'cursor':
            colors = ColorManager.get_cursor_colors()
        else:
            colors = ColorManager.get_fit_colors()
        
        return colors[index % len(colors)]


class DataHasher:
    """数据哈希工具类"""
    
    @staticmethod
    def calculate_data_hash(data):
        """计算数据哈希值用于检测数据变化"""
        try:
            if data is not None and len(data) > 0:
                stats_str = f"{len(data)}_{data.min():.6f}_{data.max():.6f}_{data.mean():.6f}_{data.std():.6f}"
                return hash(stats_str)
            return None
        except:
            return None
