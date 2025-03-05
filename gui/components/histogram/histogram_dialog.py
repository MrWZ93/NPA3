#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Dialog - 直方图分析对话框
用于分析和可视化数据的直方图
"""

import os
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                            QTabWidget, QFileDialog, QMessageBox, QGroupBox, 
                            QStatusBar, QWidget, QSplitter, QSlider, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector
import matplotlib.patches as patches

# 导入文件数据处理器
from core.data_processor import FileDataProcessor


class HistogramPlot(FigureCanvas):
    """直方图可视化画布"""
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(HistogramPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        # 创建三个子图，按照要求布局
        self.setup_subplots()
        
        # 初始化数据
        self.data = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.highlight_min = 0
        self.highlight_max = 0
        self.highlight_region = None
        self.bins = 50  # 默认直方图箱数
        
    def setup_subplots(self):
        """设置三个子图的布局"""
        # 创建一个Gridspec来管理子图的布局
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[2, 1])
        
        # 创建三个子图
        self.ax1 = self.fig.add_subplot(gs[0, :])  # 顶部跨列的子图
        self.ax2 = self.fig.add_subplot(gs[1, 0])  # 左下子图
        self.ax3 = self.fig.add_subplot(gs[1, 1])  # 右下子图
        
        # 旋转右下角子图90度，使X轴与左下角子图的Y轴对齐
        self.ax3.set_xticklabels([])  # 隐藏X轴刻度标签
        self.ax3.set_xticks([])       # 隐藏X轴刻度线
        
        # 共享左下角子图的Y轴
        self.ax2.sharey(self.ax3)
        self.ax3.invert_xaxis()  # 反转X轴方向以对齐
        
        # 设置标题和标签
        self.ax1.set_title("Full Data")
        self.ax2.set_title("Highlighted Region")
        self.ax3.set_title("Histogram")
        
        self.ax1.set_xlabel("Time (s)")
        self.ax1.set_ylabel("Amplitude")
        self.ax2.set_xlabel("Time (s)")
        self.ax2.set_ylabel("Amplitude")
        self.ax3.set_xlabel("Count")
        
        # 调整布局
        self.fig.tight_layout()
        
    def plot_data(self, data, sampling_rate=1000.0, bins=50):
        """绘制数据并设置初始高亮区域"""
        # 保存数据和参数
        self.data = data
        self.sampling_rate = sampling_rate
        self.bins = bins
        
        # 清除子图
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        
        # 重设标题和标签
        self.ax1.set_title("Full Data")
        self.ax2.set_title("Highlighted Region")
        self.ax3.set_title("Histogram")
        
        self.ax1.set_xlabel("Time (s)")
        self.ax1.set_ylabel("Amplitude")
        self.ax2.set_xlabel("Time (s)")
        self.ax2.set_ylabel("Amplitude")
        self.ax3.set_xlabel("Count")
        
        # 计算时间轴
        time_axis = np.arange(len(data)) / sampling_rate
        
        # 绘制全数据图
        self.ax1.plot(time_axis, data)
        
        # 设置初始高亮区域（默认为前10%的数据）
        self.highlight_min = 0
        self.highlight_max = len(data) // 10
        if self.highlight_max <= 0:
            self.highlight_max = len(data)
        
        # 绘制高亮区域
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 绘制高亮区域数据
        highlighted_data = data[self.highlight_min:self.highlight_max]
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        self.ax2.plot(highlighted_time, highlighted_data)
        
        # 绘制直方图
        counts, bins, _ = self.ax3.hist(
            highlighted_data, 
            bins=self.bins, 
            orientation='horizontal',
            alpha=0.7
        )
        
        # 设置适当的轴范围
        self.ax1.set_xlim(time_axis[0], time_axis[-1])
        self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 自定义直方图Y轴范围与高亮区域的幅度范围一致
        if len(highlighted_data) > 0:
            y_min = np.min(highlighted_data) - 0.05 * (np.max(highlighted_data) - np.min(highlighted_data))
            y_max = np.max(highlighted_data) + 0.05 * (np.max(highlighted_data) - np.min(highlighted_data))
            self.ax3.set_ylim(y_min, y_max)
            self.ax2.set_ylim(y_min, y_max)
        
        # 创建SpanSelector，允许用户在全数据图上选择高亮区域
        self.span_selector = SpanSelector(
            self.ax1, 
            self.on_select_span, 
            'horizontal', 
            useblit=True,
            props=dict(alpha=0.3, facecolor='yellow'),
            interactive=True, 
            drag_from_anywhere=True
        )
        
        # 调整布局
        self.fig.tight_layout()
        
        # 重绘
        self.draw()
    
    def on_select_span(self, xmin, xmax):
        """处理用户在全数据图上选择的区域"""
        # 将时间转换为数据点索引
        min_idx = max(0, int(xmin * self.sampling_rate))
        max_idx = min(len(self.data) - 1, int(xmax * self.sampling_rate))
        
        # 更新高亮区域
        self.highlight_min = min_idx
        self.highlight_max = max_idx
        
        # 更新高亮区域绘图
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()
    
    def update_highlighted_plots(self):
        """更新高亮区域和直方图"""
        if self.data is None:
            return
            
        # 清除子图2和子图3
        self.ax2.clear()
        self.ax3.clear()
        
        # 重设标题和标签
        self.ax2.set_title("Highlighted Region")
        self.ax3.set_title("Histogram")
        
        self.ax2.set_xlabel("Time (s)")
        self.ax2.set_ylabel("Amplitude")
        self.ax3.set_xlabel("Count")
        
        # 获取高亮区域数据
        highlighted_data = self.data[self.highlight_min:self.highlight_max]
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        
        # 绘制高亮区域数据
        self.ax2.plot(highlighted_time, highlighted_data)
        
        # 绘制直方图
        counts, bins, _ = self.ax3.hist(
            highlighted_data, 
            bins=self.bins, 
            orientation='horizontal',
            alpha=0.7
        )
        
        # 设置适当的轴范围
        self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 自定义直方图Y轴范围与高亮区域的幅度范围一致
        if len(highlighted_data) > 0:
            y_min = np.min(highlighted_data) - 0.05 * (np.max(highlighted_data) - np.min(highlighted_data))
            y_max = np.max(highlighted_data) + 0.05 * (np.max(highlighted_data) - np.min(highlighted_data))
            self.ax3.set_ylim(y_min, y_max)
            self.ax2.set_ylim(y_min, y_max)
    
    def update_bins(self, bins):
        """更新直方图箱数"""
        self.bins = bins
        self.update_highlighted_plots()
        self.draw()
    
    def update_highlight_size(self, size_percent):
        """更新高亮区域大小"""
        if self.data is None:
            return
        
        # 计算新的高亮区域大小
        center_idx = (self.highlight_min + self.highlight_max) // 2
        
        # 处理特殊情况：100%应该覆盖全部数据
        if size_percent >= 100:
            self.highlight_min = 0
            self.highlight_max = len(self.data) - 1
        else:
            # 计算与中心点的距离（单侧）
            half_size = int(len(self.data) * size_percent / 100) // 2  # 除以100把百分比转为小数，再除以2得到单侧距离
            
            # 更新高亮区域
            self.highlight_min = max(0, center_idx - half_size)
            self.highlight_max = min(len(self.data) - 1, center_idx + half_size)
        
        # 更新高亮区域绘图
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()
    
    def move_highlight(self, position_percent):
        """移动高亮区域位置"""
        if self.data is None:
            return
        
        # 计算高亮区域大小
        highlight_size = self.highlight_max - self.highlight_min
        
        # 处理特殊情况：100%大小
        if highlight_size >= len(self.data) - 1:
            self.highlight_min = 0
            self.highlight_max = len(self.data) - 1
        else:
            # 根据百分比计算新的中心位置
            max_position = len(self.data) - 1
            new_center = int(max_position * position_percent / 100)
            
            # 算出新的边界
            new_min = new_center - highlight_size // 2
            new_max = new_min + highlight_size
            
            # 处理右边界超出情况
            if new_max > max_position:
                # 将右边界调整到数据结尾
                new_max = max_position
                # 相应地调整左边界，保持高亮区域大小不变
                new_min = max(0, new_max - highlight_size)
            
            # 处理左边界超出情况
            if new_min < 0:
                new_min = 0
                # 相应地调整右边界，保持高亮区域大小不变
                new_max = min(max_position, new_min + highlight_size)
            
            # 更新高亮区域
            self.highlight_min = new_min
            self.highlight_max = new_max
        
        # 更新高亮区域绘图
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()


class HistogramDialog(QDialog):
    """直方图分析对话框"""
    
    def __init__(self, parent=None):
        super(HistogramDialog, self).__init__(parent)
        self.setWindowTitle("Histogram Analysis")
        self.resize(1000, 800)  # 设置初始大小
        
        # 初始化数据
        self.data = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.selected_channel = None
        
        # 初始化文件数据处理器
        self.file_processor = FileDataProcessor()
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        
        # 设置界面
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置用户界面"""
        # ================ 顶部区域：文件和通道控制 ================
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # 文件和通道部分
        file_group = QGroupBox("File & Channel")
        file_layout = QVBoxLayout(file_group)
        
        # 文件选择
        file_select_layout = QHBoxLayout()
        self.load_file_btn = QPushButton("Load File")
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: gray; font-style: italic;")
        file_select_layout.addWidget(self.load_file_btn)
        file_select_layout.addWidget(self.file_label, 1)
        
        # 通道选择
        channel_select_layout = QHBoxLayout()
        channel_select_layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("Select a channel")
        channel_select_layout.addWidget(self.channel_combo, 1)
        
        # 采样率设置
        sampling_rate_layout = QHBoxLayout()
        sampling_rate_layout.addWidget(QLabel("Sampling Rate (Hz):"))
        self.sampling_rate_spin = QDoubleSpinBox()
        self.sampling_rate_spin.setRange(1, 1000000)
        self.sampling_rate_spin.setValue(1000.0)
        self.sampling_rate_spin.setDecimals(1)
        self.sampling_rate_spin.setSingleStep(100)
        sampling_rate_layout.addWidget(self.sampling_rate_spin, 1)
        
        # 添加到文件分组布局
        file_layout.addLayout(file_select_layout)
        file_layout.addLayout(channel_select_layout)
        file_layout.addLayout(sampling_rate_layout)
        
        # 绘图控制部分
        plot_controls_group = QGroupBox("Plot Controls")
        plot_controls_layout = QVBoxLayout(plot_controls_group)
        
        # 直方图箱数设置
        bins_layout = QFormLayout()
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(5, 500)
        self.bins_spin.setValue(50)
        self.bins_spin.setSingleStep(5)
        bins_layout.addRow("Histogram Bins:", self.bins_spin)
        
        # 高亮区域大小设置
        highlight_size_layout = QHBoxLayout()
        highlight_size_layout.addWidget(QLabel("Highlight Size:"))
        self.highlight_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_size_slider.setRange(1, 100)  # 1-100% 范围
        self.highlight_size_slider.setValue(10)  # 默认10%
        self.highlight_size_label = QLabel("10%")
        highlight_size_layout.addWidget(self.highlight_size_slider)
        highlight_size_layout.addWidget(self.highlight_size_label)
        
        # 高亮区域位置设置
        highlight_pos_layout = QHBoxLayout()
        highlight_pos_layout.addWidget(QLabel("Highlight Position:"))
        self.highlight_pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_pos_slider.setRange(0, 100)  # 0-100% 范围
        self.highlight_pos_slider.setValue(5)  # 默认位于数据开始附近
        self.highlight_pos_label = QLabel("5%")
        highlight_pos_layout.addWidget(self.highlight_pos_slider)
        highlight_pos_layout.addWidget(self.highlight_pos_label)
        
        # 添加到绘图控制布局
        plot_controls_layout.addLayout(bins_layout)
        plot_controls_layout.addLayout(highlight_size_layout)
        plot_controls_layout.addLayout(highlight_pos_layout)
        
        # 添加到顶部布局
        top_layout.addWidget(file_group)
        top_layout.addWidget(plot_controls_group)
        
        # ================ 中间区域：绘图区 ================
        # 创建绘图区
        self.plot_canvas = HistogramPlot(self, width=8, height=6, dpi=100)
        self.plot_toolbar = NavigationToolbar(self.plot_canvas, self)
        
        # 将绘图区添加到布局
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.addWidget(self.plot_toolbar)
        plot_layout.addWidget(self.plot_canvas)
        
        # ================ 状态栏 ================
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        
        # ================ 将各部分添加到主布局 ================
        self.main_layout.addWidget(top_widget)
        self.main_layout.addWidget(plot_widget, 1)  # 绘图区占大部分空间
        self.main_layout.addWidget(self.status_bar)
    
    def connect_signals(self):
        """连接信号和槽"""
        # 文件加载
        self.load_file_btn.clicked.connect(self.load_file)
        
        # 通道选择
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        
        # 采样率变化
        self.sampling_rate_spin.valueChanged.connect(self.on_sampling_rate_changed)
        
        # 直方图箱数变化
        self.bins_spin.valueChanged.connect(self.on_bins_changed)
        
        # 高亮区域大小变化
        self.highlight_size_slider.valueChanged.connect(self.on_highlight_size_changed)
        
        # 高亮区域位置变化
        self.highlight_pos_slider.valueChanged.connect(self.on_highlight_position_changed)
    
    def load_file(self):
        """加载文件对话框"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Data File",
                "",
                "Data Files (*.h5 *.csv *.tdms *.abf);;All Files (*)"
            )
            
            if not file_path:
                return
                
            # 更新文件标签
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setToolTip(file_path)
            self.file_label.setStyleSheet("color: black; font-style: normal;")
            
            # 显示加载中消息
            self.status_bar.showMessage(f"Loading file: {os.path.basename(file_path)}...")
            
            # 使用FileDataProcessor加载文件
            success, data, info = self.file_processor.load_file(file_path)
            
            if not success:
                error_msg = info.get("Error", "Unknown error")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load file: {error_msg}"
                )
                self.status_bar.showMessage(f"Error: {error_msg}")
                return
            
            # 更新数据
            self.data = data
            
            # 获取采样率
            if "Sampling Rate" in info and isinstance(info["Sampling Rate"], str):
                try:
                    # 如果字符串格式如 "1000 Hz"，提取数字部分
                    sr_str = info["Sampling Rate"].split()[0]  # 取第一部分
                    self.sampling_rate = float(sr_str)
                    self.sampling_rate_spin.setValue(self.sampling_rate)
                except:
                    # 如果解析失败，保持默认采样率
                    pass
            elif hasattr(self.file_processor, 'sampling_rate'):
                self.sampling_rate = self.file_processor.sampling_rate
                self.sampling_rate_spin.setValue(self.sampling_rate)
            
            # 更新通道选择器
            self.channel_combo.clear()
            self.selected_channel = None
            
            if isinstance(data, dict):
                # 如果数据是字典格式（多通道）
                for channel in data.keys():
                    self.channel_combo.addItem(str(channel))
                
                # 默认选择第一个通道
                if data:
                    first_channel = next(iter(data.keys()))
                    self.selected_channel = first_channel
                    self.channel_combo.setCurrentText(first_channel)
                    self.plot_canvas.plot_data(data[first_channel], self.sampling_rate, self.bins_spin.value())
            
            elif isinstance(data, np.ndarray):
                if data.ndim == 1:
                    # 单通道数据
                    self.channel_combo.addItem("Channel 1")
                    self.selected_channel = "Channel 1"
                    self.channel_combo.setCurrentText("Channel 1")
                    self.plot_canvas.plot_data(data, self.sampling_rate, self.bins_spin.value())
                
                elif data.ndim == 2:
                    # 多通道数据
                    for i in range(data.shape[1]):
                        self.channel_combo.addItem(f"Channel {i+1}")
                    
                    # 默认选择第一个通道
                    self.selected_channel = "Channel 1"
                    self.channel_combo.setCurrentText("Channel 1")
                    self.plot_canvas.plot_data(data[:, 0], self.sampling_rate, self.bins_spin.value())
            
            # 文件信息摘要
            summary = ", ".join([f"{k}: {v}" for k, v in info.items() 
                            if k not in ['File Path', 'Modified Time']])
            
            self.status_bar.showMessage(f"Loaded file: {os.path.basename(file_path)} - {summary}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error loading file: {str(e)}"
            )
            self.status_bar.showMessage(f"Error loading file: {str(e)}")
            print(f"Error in load_file: {str(e)}")
    
    def set_data(self, data, sampling_rate=None):
        """设置数据（外部调用）"""
        self.data = data
        if sampling_rate is not None:
            self.sampling_rate = sampling_rate
            self.sampling_rate_spin.setValue(sampling_rate)
        
        # 清除通道选择器并更新
        self.channel_combo.clear()
        
        # 默认选定的通道数据
        selected_data = None
        
        # 根据数据类型处理
        if isinstance(data, dict):
            # 字典数据（多通道）
            for channel in data.keys():
                self.channel_combo.addItem(channel)
                
            # 默认选择第一个通道
            if len(data) > 0:
                first_channel = next(iter(data.keys()))
                self.channel_combo.setCurrentText(first_channel)
                self.selected_channel = first_channel
                selected_data = data[first_channel]
        
        elif isinstance(data, np.ndarray):
            if data.ndim == 1:
                # 单通道数据
                self.channel_combo.addItem("Channel 1")
                self.channel_combo.setCurrentText("Channel 1")
                self.selected_channel = "Channel 1"
                selected_data = data
            
            elif data.ndim == 2:
                # 多通道数据（二维数组）
                for i in range(data.shape[1]):
                    self.channel_combo.addItem(f"Channel {i+1}")
                
                # 默认选择第一个通道
                self.channel_combo.setCurrentText("Channel 1")
                self.selected_channel = "Channel 1"
                selected_data = data[:, 0]
        
        # 绘制数据
        if selected_data is not None:
            self.plot_canvas.plot_data(selected_data, self.sampling_rate, self.bins_spin.value())
        
        self.status_bar.showMessage("Data loaded")
    
    def on_channel_changed(self, index):
        """处理通道选择变化"""
        if index < 0 or self.data is None:
            return
                
        # 获取选中的通道名称
        selected_channel = self.channel_combo.currentText()
        self.selected_channel = selected_channel
        
        try:
            # 确定选择的通道数据
            channel_data = None
            
            # 检查数据类型并提取对应通道数据
            if isinstance(self.data, dict):
                # 字典类型数据，直接获取通道数据
                if selected_channel in self.data:
                    channel_data = self.data[selected_channel]
                    self.status_bar.showMessage(f"Selected channel: {selected_channel}")
                else:
                    self.status_bar.showMessage(f"Error: Channel '{selected_channel}' not found in data")
                    return
            
            elif isinstance(self.data, np.ndarray):
                if self.data.ndim == 1:
                    # 单通道数据
                    channel_data = self.data
                    self.status_bar.showMessage(f"Selected channel: {selected_channel}")
                
                elif self.data.ndim == 2:
                    # 二维数组，选择对应的列
                    try:
                        # 从 "Channel X" 中提取索引
                        channel_parts = selected_channel.split()
                        if len(channel_parts) > 1 and channel_parts[-1].isdigit():
                            channel_index = int(channel_parts[-1]) - 1
                        else:
                            # 尝试将整个字符串转换为索引
                            channel_index = int(selected_channel) - 1
                        
                        if 0 <= channel_index < self.data.shape[1]:
                            channel_data = self.data[:, channel_index]
                            self.status_bar.showMessage(f"Selected channel: {selected_channel}")
                        else:
                            self.status_bar.showMessage(f"Error: Channel index {channel_index+1} out of range")
                            return
                    except ValueError:
                        self.status_bar.showMessage(f"Error: Cannot parse channel index from '{selected_channel}'")
                        return
                    except Exception as e:
                        self.status_bar.showMessage(f"Error selecting channel: {str(e)}")
                        print(f"Error selecting channel: {str(e)}")
                        return
            
            # 如果没有成功获取通道数据，退出
            if channel_data is None:
                self.status_bar.showMessage("Error: Failed to get channel data")
                return
            
            # 绘制数据
            self.plot_canvas.plot_data(channel_data, self.sampling_rate, self.bins_spin.value())
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Error during channel change: {str(e)}")
            print(f"Error in on_channel_changed: {str(e)}")
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变化"""
        self.sampling_rate = value
        
        # 更新图表的时间轴
        if self.data is None or self.selected_channel is None:
            return
        
        # 获取当前选择的通道数据
        channel_data = None
        if isinstance(self.data, dict) and self.selected_channel in self.data:
            channel_data = self.data[self.selected_channel]
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim == 1:
                channel_data = self.data
            elif self.data.ndim == 2 and self.selected_channel.startswith("Channel "):
                try:
                    channel_idx = int(self.selected_channel.split(" ")[1]) - 1
                    if 0 <= channel_idx < self.data.shape[1]:
                        channel_data = self.data[:, channel_idx]
                except:
                    pass
        
        # 更新图表
        if channel_data is not None:
            self.plot_canvas.plot_data(channel_data, self.sampling_rate, self.bins_spin.value())
    
    def on_bins_changed(self, value):
        """处理直方图箱数变化"""
        self.plot_canvas.update_bins(value)
    
    def on_highlight_size_changed(self, value):
        """处理高亮区域大小变化"""
        self.highlight_size_label.setText(f"{value}%")
        self.plot_canvas.update_highlight_size(value)
    
    def on_highlight_position_changed(self, value):
        """处理高亮区域位置变化"""
        self.highlight_pos_label.setText(f"{value}%")
        self.plot_canvas.move_highlight(value)
