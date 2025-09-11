#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据可视化组件
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# 导入自定义样式
from gui.styles import PLOT_STYLE, PLOT_COLORS, COLORS

# 引入信号机制
from PyQt6.QtCore import pyqtSignal, QObject

class DataVisualizer(FigureCanvas):
    """数据可视化组件"""
    # 定义频道列表更新信号
    channels_updated = pyqtSignal(list)
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = []  # Will hold multiple axes for subplots
        
        super(DataVisualizer, self).__init__(self.fig)
        self.setParent(parent)
        
        # 初始化后绑定事件响应
        self.fig.canvas.mpl_connect('draw_event', self.on_draw)
        self.fig.canvas.mpl_connect('button_release_event', self.on_button_release)
        
        self.fig.tight_layout()
        self.data = None
        self.processed_data = None
        self.subplot_heights = {}  # Store custom heights for subplots
        self.sampling_rate = 1.0  # Default sampling rate
        self.sync_mode = True  # Default to synchronized X-axis
        self.current_title = "Data"  # Store the current title
        self.visible_channels = []  # 存储需要显示的通道
        self.original_data = None  # 存储原始数据，以便过滤显示通道
        self.current_time_axis = None  # 存储当前显示的时间轴，供trim操作使用
    
    def plot_data(self, data, title="Data", xlabel="Time (s)", ylabel="Value", sampling_rate=None, channels_to_plot=None):
        """绘制数据 - 使用美化样式"""
        print(f"Plotting data: {type(data)}")
        if isinstance(data, dict):
            print(f"Data keys: {list(data.keys())}")
            for key, value in data.items():
                if isinstance(value, np.ndarray):
                    print(f"Channel {key} shape: {value.shape}, min: {np.min(value)}, max: {np.max(value)}")
                else:
                    print(f"Channel {key} type: {type(value)}")
        
        # 设置图表样式
        for key, value in PLOT_STYLE.items():
            plt.rcParams[key] = value
        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=PLOT_COLORS)
        self.fig.patch.set_facecolor(COLORS["card"])
        
        # **重要修复**: 强制更新存储的数据为处理后的数据
        self.data = data
        self.original_data = data
        
        # 处理需要显示的通道
        if channels_to_plot is not None:
            self.visible_channels = channels_to_plot
        elif not self.visible_channels and data is not None:
            # 如果没有指定通道且visible_channels为空，则显示所有通道
            if isinstance(data, dict):
                # 过滤掉"Time"通道，因为它会单独处理为X轴
                self.visible_channels = [ch for ch in data.keys() if ch.lower() != "time"]
                # 如果过滤后没有通道，添加所有通道
                if not self.visible_channels:
                    self.visible_channels = list(data.keys())
            elif isinstance(data, np.ndarray) and data.ndim == 2:
                self.visible_channels = [f"Channel {i+1}" for i in range(data.shape[1])]
            elif isinstance(data, np.ndarray) and data.ndim == 1:
                self.visible_channels = ["Data"]
        
        # 根据选择的通道过滤数据
        if isinstance(data, dict) and self.visible_channels:
            filtered_data = {k: v for k, v in data.items() if k in self.visible_channels or k.lower() == "time"}
            # 如果filtered_data为空(除了可能的Time通道)，至少保留一个通道
            if all(k.lower() == "time" for k in filtered_data.keys()) and data:
                # 如果只有Time通道，添加一个非Time通道
                for key in data:
                    if key.lower() != "time":
                        filtered_data[key] = data[key]
                        if key not in self.visible_channels:
                            self.visible_channels.append(key)
                        break
            # 如果完全没有通道，添加第一个通道
            if not filtered_data and data:
                first_key = next(iter(data))
                filtered_data = {first_key: data[first_key]}
                self.visible_channels = [first_key]
            # **重要修复**: 更新data为过滤后的数据
            self.data = filtered_data
        elif isinstance(data, np.ndarray) and data.ndim == 2 and self.visible_channels:
            # 对于二维数组，根据通道名称筛选列
            channel_indices = []
            for ch in self.visible_channels:
                if ch.startswith("Channel "):
                    try:
                        idx = int(ch.split(" ")[1]) - 1
                        if 0 <= idx < data.shape[1]:
                            channel_indices.append(idx)
                    except ValueError:
                        pass
            
            # 如果没有有效的通道索引，至少保留第一个通道
            if not channel_indices and data.shape[1] > 0:
                channel_indices = [0]
                self.visible_channels = [f"Channel 1"]
            
            # **重要修复**: 更新data为过滤后的数据
            self.data = data[:, channel_indices] if channel_indices else data[:, :1]
        
        self.current_title = title  # Store the title
        self.fig.clear()
        self.axes = []
        
        # Update sampling rate if provided
        if sampling_rate is not None and sampling_rate > 0:
            self.sampling_rate = sampling_rate
        
        if self.data is not None:
            if isinstance(self.data, dict):
                # 处理多通道数据 - Create a subplot for each channel
                channels = list(self.data.keys())
                
                # 如果有Time通道，将其作为X轴数据而不是独立的通道
                time_data = None
                plot_channels = []
                
                for ch in channels:
                    if ch.lower() == "time":
                        # 提取时间数据
                        time_data = self.data[ch]
                    else:
                        plot_channels.append(ch)
                
                # 如果过滤后没有通道，但有Time通道，显示Time通道
                if not plot_channels and "Time" in channels:
                    plot_channels = ["Time"]
                    time_data = None
                
                num_channels = len(plot_channels)
                
                # 发出通道更新信号
                if isinstance(self.original_data, dict):
                    all_channels = list(self.original_data.keys())
                    self.channels_updated.emit(all_channels)
                
                if num_channels == 0:
                    print("Warning: No channels to plot")
                    return
                
                # Set default subplot heights if not configured
                for channel in channels:
                    if channel not in self.subplot_heights:
                        self.subplot_heights[channel] = 1
                
                # Calculate total height ratio
                total_height = sum(self.subplot_heights.get(ch, 1) for ch in plot_channels)
                
                # Create subplots with appropriate heights
                height_ratios = [self.subplot_heights.get(ch, 1) for ch in plot_channels]
                gs = self.fig.add_gridspec(num_channels, 1, height_ratios=height_ratios)
                
                prev_ax = None
                for i, channel in enumerate(plot_channels):
                    values = self.data[channel]
                    
                    # 检查通道数据是否有效
                    if not isinstance(values, np.ndarray) or len(values) == 0:
                        print(f"Warning: Invalid data for channel {channel}")
                        continue
                    
                    # 创建第一个子图，或根据同步设置决定是否共享X轴
                    if i == 0 or not self.sync_mode:
                        ax = self.fig.add_subplot(gs[i, 0])
                    else:
                        ax = self.fig.add_subplot(gs[i, 0], sharex=prev_ax)
                    
                    prev_ax = ax
                    self.axes.append(ax)
                    
                    # 使用时间数据作为X轴（如果有），否则生成时间轴
                    try:
                        if time_data is not None and len(time_data) == len(values):
                            # **修复**: 直接使用时间数据，不要重置时间轴
                            # 这样trim后的数据会保持用户选择的时间范围
                            current_x_axis = time_data
                            ax.plot(time_data, values)
                            
                            # **关键修复**: 存储当前使用的时间轴，供trim操作参考
                            if i == 0:  # 只在第一个通道时存储时间轴
                                self.current_time_axis = time_data.copy()
                            
                            # 使用真实时间数据时，需要设置X轴标签
                            if i == num_channels - 1 or not self.sync_mode:  # 只在底部图或非同步图中显示X轴标签
                                ax.set_xlabel("Time (s)", fontsize=10, fontweight='bold')
                        else:
                            # 生成基于采样率的时间轴
                            time_axis = np.arange(len(values)) / self.sampling_rate
                            current_x_axis = time_axis
                            ax.plot(time_axis, values)
                            
                            # **关键修复**: 存储当前使用的时间轴，供trim操作参考
                            if i == 0:  # 只在第一个通道时存储时间轴
                                self.current_time_axis = time_axis.copy()
                            
                            # 同步时，只在底部子图显示X轴标签
                            if self.sync_mode and i < num_channels - 1:
                                ax.tick_params(labelbottom=False)
                            else:
                                ax.set_xlabel("Time (s)", fontsize=10, fontweight='bold')
                    except Exception as e:
                        print(f"Error plotting channel {channel}: {str(e)}")
                        
                    # 美化轴标签
                    ax.set_ylabel(channel, fontsize=10, fontweight='bold')
                    ax.tick_params(labelsize=9)
                    ax.grid(True, linestyle='--', alpha=0.7)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                
                # Set main title
                self.fig.suptitle(title, fontsize=12, fontweight='bold', color=COLORS["primary"])
                
                # X轴已经在创建子图时共享，这里不需要再共享
                # 只需要设置标签可见性
                if self.sync_mode and len(self.axes) > 1:
                    # 隐藏中间子图的 x 轴标签
                    for i in range(len(self.axes)-1):
                        plt.setp(self.axes[i].get_xticklabels(), visible=False)
                
            elif isinstance(self.data, np.ndarray):
                if self.data.ndim == 1:
                    # 发出通道更新信号 - 单通道数据
                    self.channels_updated.emit(["Data"])
                    # Single channel data
                    ax = self.fig.add_subplot(111)
                    self.axes = [ax]
                    
                    # Generate time axis
                    time_axis = np.arange(len(self.data)) / self.sampling_rate
                    ax.plot(time_axis, self.data)
                    
                    # **关键修复**: 存储当前使用的时间轴，供trim操作参考
                    self.current_time_axis = time_axis.copy()
                    
                    ax.set_title(title, fontsize=12, fontweight='bold', color=COLORS["primary"])
                    ax.set_xlabel(xlabel, fontsize=10, fontweight='bold')
                    ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
                    ax.tick_params(labelsize=9)
                    ax.grid(True, linestyle='--', alpha=0.7)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    
                elif self.data.ndim == 2:
                    # Multiple channels in columns
                    num_channels = self.data.shape[1]
                    
                    # 发出通道更新信号
                    if isinstance(self.original_data, np.ndarray) and self.original_data.ndim == 2:
                        all_channels = [f"Channel {i+1}" for i in range(self.original_data.shape[1])]
                        self.channels_updated.emit(all_channels)
                    
                    # Set default heights if not configured
                    for i in range(num_channels):
                        channel_key = f"Channel {i+1}"
                        if channel_key not in self.subplot_heights:
                            self.subplot_heights[channel_key] = 1
                    
                    # Calculate height ratios
                    height_ratios = [self.subplot_heights.get(f"Channel {i+1}", 1) 
                                    for i in range(num_channels)]
                    gs = self.fig.add_gridspec(num_channels, 1, height_ratios=height_ratios)
                    
                    prev_ax = None
                    for i in range(num_channels):
                        # 创建子图，并根据同步模式决定是否共享X轴
                        if i == 0 or not self.sync_mode:
                            ax = self.fig.add_subplot(gs[i, 0])
                        else:
                            ax = self.fig.add_subplot(gs[i, 0], sharex=prev_ax)
                        
                        prev_ax = ax
                        self.axes.append(ax)
                        
                        # Generate time axis
                        time_axis = np.arange(self.data.shape[0]) / self.sampling_rate
                        ax.plot(time_axis, self.data[:, i])
                        
                        # **关键修复**: 存储当前使用的时间轴，供trim操作参考
                        if i == 0:  # 只在第一个通道时存储时间轴
                            self.current_time_axis = time_axis.copy()
                        
                        # 美化轴标签
                        ax.set_ylabel(f"Channel {i+1}", fontsize=10, fontweight='bold')
                        ax.tick_params(labelsize=9)
                        ax.grid(True, linestyle='--', alpha=0.7)
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        
                        # Only show x-label on bottom subplot
                        if self.sync_mode and i < num_channels - 1:
                            ax.tick_params(labelbottom=False)
                        else:
                            ax.set_xlabel(xlabel, fontsize=10, fontweight='bold')
                    
                    # Set main title
                    self.fig.suptitle(title, fontsize=12, fontweight='bold', color=COLORS["primary"])
        else:
            # 如果没有数据，显示空白图表和提示
            ax = self.fig.add_subplot(111)
            self.axes = [ax]
            ax.text(0.5, 0.5, 'No data to display', 
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=ax.transAxes,
                    fontsize=14,
                    color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
        
        self.fig.tight_layout()
        self.fig.subplots_adjust(top=0.9)  # Make room for suptitle
        self.draw()
    
    def set_sync_mode(self, sync):
        """设置X轴同步模式"""
        # 如果状态没有改变，不做任何事
        if self.sync_mode == sync:
            return
            
        self.sync_mode = sync
        
        # 如果有数据，重新绘制以应用新的同步设置
        if self.original_data is not None:
            # 保存当前的X轴范围，以便在重绘后恢复
            x_ranges = []
            for ax in self.axes:
                x_ranges.append(ax.get_xlim())
            
            # 重新绘制数据
            self.plot_data(
                self.original_data,
                title=self.current_title,
                sampling_rate=self.sampling_rate,
                channels_to_plot=self.visible_channels
            )
            
            # 如果取消同步，恢复每个轴的原始范围
            if not sync and len(x_ranges) == len(self.axes):
                for i, ax in enumerate(self.axes):
                    ax.set_xlim(x_ranges[i])
                self.draw()
    
    def sync_x_axes(self):
        """同步所有子图的X轴范围"""
        if not self.axes:
            return
            
        # 获取所有子图的X轴范围
        x_min, x_max = float('inf'), float('-inf')
        for ax in self.axes:
            x_limits = ax.get_xlim()
            x_min = min(x_min, x_limits[0])
            x_max = max(x_max, x_limits[1])
        
        # 应用统一的X轴范围
        for ax in self.axes:
            ax.set_xlim(x_min, x_max)

    def set_subplot_height(self, channel, height_ratio):
        """设置子图高度比例"""
        if height_ratio > 0:
            self.subplot_heights[channel] = height_ratio
    
    def set_sampling_rate(self, rate):
        """设置采样率并重绘"""
        if rate > 0:
            self.sampling_rate = rate
            # Redraw with new sampling rate if we have data
            if self.original_data is not None:
                self.plot_data(self.original_data, title=self.current_title, channels_to_plot=self.visible_channels)

    def get_subplot_heights(self):
        """获取所有子图高度设置"""
        return self.subplot_heights
    
    def set_visible_channels(self, channels):
        """设置需要显示的通道"""
        if channels:
            self.visible_channels = channels.copy()
            # 重绘图表以应用新的通道选择
            if self.original_data is not None:
                self.plot_data(self.original_data, title=self.current_title)
    
    def get_sampling_rate(self):
        """获取当前采样率"""
        return self.sampling_rate

    def create_linked_axes(self):
        """创建具有链接 X 轴的子图"""
        if len(self.axes) <= 1:
            return
            
        # 获取所有子图
        for i in range(1, len(self.axes)):
            # 将其余子图的 x 轴与第一个子图的 x 轴关联
            if self.sync_mode:
                # 共享 x 轴
                self.axes[i].sharex(self.axes[0])
            else:
                # 取消共享
                self.axes[i].get_shared_x_axes().remove(self.axes[0])
                self.axes[i].autoscale(enable=True, axis='x')

    def on_draw(self, event):
        """在图形重绘时调用来同步X轴"""
        if self.sync_mode and len(self.axes) > 1:
            self.sync_x_axes()

    def on_button_release(self, event):
        """在鼠标松开时调用，用于处理缩放和平移后的同步"""
        if self.sync_mode and len(self.axes) > 1:
            self.sync_x_axes()
    
    def get_current_time_axis(self):
        """获取当前显示的时间轴，供trim操作使用"""
        return self.current_time_axis
    
    def clear(self):
        """清除图表"""
        self.fig.clear()
        self.axes = []
        self.current_time_axis = None  # 清空时间轴
        self.draw()
