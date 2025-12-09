#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spikes Detector Dialog - 峰值检测器对话框
用于检测和分析时间序列数据中的峰值(spikes)
"""

import os
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                            QTabWidget, QFileDialog, QMessageBox, QGroupBox, 
                            QStatusBar, QWidget, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# 导入自定义样式
from gui.styles import PLOT_STYLE, PLOT_COLORS, COLORS

# 导入文件数据处理器
from core.data_processor import FileDataProcessor

# 导入自定义模块
from .modules.spike_plot import SpikesDataPlot
from .modules.auto_detector import AutoSpikeDetector
from .modules.manual_selector import ManualSpikeSelector
from .modules.segment_manager import SegmentDataManager


class SpikesDetectorDialog(QDialog):
    """峰值检测器对话框"""
    
    def __init__(self, parent=None):
        super(SpikesDetectorDialog, self).__init__(parent)
        self.setWindowTitle("Spikes Detector")
        self.resize(1000, 700)  # 设置初始大小
        
        # 设置窗口标志，保持窗口在合理的层级
        # Qt.WindowType.Window 让它成为独立窗口
        # 不使用 StaysOnTopHint，避免总是置顶
        self.setWindowFlags(Qt.WindowType.Window)
        
        # 初始化数据
        self.data = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.selected_channel = None
        
        # 初始化文件数据处理器
        self.file_processor = FileDataProcessor()
        
        # 初始化分段管理器
        self.segment_manager = None
        self.current_segment = 1  # 当前段索引（1-based）
        self.num_segments = 10  # 总段数
        self.segmentation_enabled = False  # 是否启用分段
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        
        # 设置界面
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置用户界面"""
        # ================ 主标签页控件 ================
        self.main_tabs = QTabWidget()
        
        # ================ 1. Setup 标签页 ================
        setup_tab = QWidget()
        setup_layout = QVBoxLayout(setup_tab)
        
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
        
        # 数据分段部分
        segment_group = QGroupBox("Data Segmentation")
        segment_group.setFixedHeight(110)  # 进一步降低固定高度
        segment_layout = QVBoxLayout(segment_group)
        
        # 分段数量设置
        segment_count_layout = QHBoxLayout()
        segment_count_layout.addWidget(QLabel("Number of Segments:"))
        self.segment_count_spin = QSpinBox()
        self.segment_count_spin.setRange(1, 100)
        self.segment_count_spin.setValue(10)
        self.segment_count_spin.setToolTip("Split data into N segments for faster processing")
        segment_count_layout.addWidget(self.segment_count_spin)
        
        self.apply_segmentation_btn = QPushButton("Apply Segmentation")
        self.apply_segmentation_btn.setEnabled(False)
        self.apply_segmentation_btn.setToolTip("Click to split data into segments")
        segment_count_layout.addWidget(self.apply_segmentation_btn)
        segment_count_layout.addStretch()
        
        # 当前段选择
        current_segment_layout = QHBoxLayout()
        current_segment_layout.addWidget(QLabel("Current Segment:"))
        self.current_segment_spin = QSpinBox()
        self.current_segment_spin.setRange(1, 1)
        self.current_segment_spin.setValue(1)
        self.current_segment_spin.setEnabled(False)
        self.current_segment_spin.setToolTip("Select which segment to process")
        current_segment_layout.addWidget(self.current_segment_spin)
        
        # 前后段导航按钮
        self.prev_segment_btn = QPushButton("← Prev")
        self.prev_segment_btn.setEnabled(False)
        self.prev_segment_btn.setMinimumWidth(80)
        self.prev_segment_btn.setToolTip("Go to previous segment")
        current_segment_layout.addWidget(self.prev_segment_btn)
        
        self.next_segment_btn = QPushButton("Next →")
        self.next_segment_btn.setEnabled(False)
        self.next_segment_btn.setMinimumWidth(80)
        self.next_segment_btn.setToolTip("Go to next segment")
        current_segment_layout.addWidget(self.next_segment_btn)
        current_segment_layout.addStretch()
        
        # 段信息显示
        self.segment_info_label = QLabel("No segmentation applied")
        self.segment_info_label.setStyleSheet("color: gray; font-style: italic;")
        
        # 添加到分段布局
        segment_layout.addLayout(segment_count_layout)
        segment_layout.addLayout(current_segment_layout)
        segment_layout.addWidget(self.segment_info_label)
        
        # 添加到 Setup 标签页布局
        setup_layout.addWidget(file_group)
        setup_layout.addWidget(segment_group)
        setup_layout.addStretch(1)  # 添加伸展空间，将控件推到顶部
        
        # ================ 2. 自动检测标签页 ================
        auto_tab = QWidget()
        auto_layout = QVBoxLayout(auto_tab)
        
        # 分段控制条（自动检测页）
        self.auto_segment_bar = self._create_segment_control_bar()
        auto_layout.addWidget(self.auto_segment_bar)
        
        # 创建自动检测页的绘图部分
        # 首先创建自动检测器
        self.auto_detector = AutoSpikeDetector()
        
        # 创建画布和工具栏
        self.auto_canvas = SpikesDataPlot(self, width=8, height=4, dpi=100)
        self.auto_toolbar = NavigationToolbar(self.auto_canvas, self)
        
        # 设置自动检测器的画布引用
        self.auto_detector.plot_canvas = self.auto_canvas  
        self.auto_detector.toolbar = self.auto_toolbar
        
        # 将画布和工具栏设置到自动检测器的绘图区域
        self.auto_detector.set_plot_canvas(self.auto_canvas, self.auto_toolbar)
        
        # 将自动检测器添加到自动检测页面
        auto_layout.addWidget(self.auto_detector)
        
        # ================ 3. 手动选择标签页 ================
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        
        # 分段控制条（手动选择页）
        self.manual_segment_bar = self._create_segment_control_bar()
        manual_layout.addWidget(self.manual_segment_bar)
        
        # 创建手动选择器
        self.manual_selector = ManualSpikeSelector()
        
        # 创建手动选择页的画布和工具栏
        self.manual_canvas = SpikesDataPlot(self, width=8, height=4, dpi=100)
        self.manual_toolbar = NavigationToolbar(self.manual_canvas, self)
        self.manual_canvas.toolbar = self.manual_toolbar  # 保存工具栏引用
        
        # 设置手动选择器的画布引用
        self.manual_selector.plot_canvas = self.manual_canvas
        
        # 调用手动选择器的set_plot_canvas方法设置画布
        self.manual_selector.set_plot_canvas(self.manual_canvas)
        
        # 将手动选择器添加到手动选择页面
        manual_layout.addWidget(self.manual_selector)
        
        # ================ 添加所有标签页 ================
        self.main_tabs.addTab(setup_tab, "Setup")
        self.main_tabs.addTab(auto_tab, "Auto Detection")
        self.main_tabs.addTab(manual_tab, "Manual Selection")
        
        # ================ 状态栏 ================
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        
        # ================ 将各部分添加到主布局 ================
        self.main_layout.addWidget(self.main_tabs, 1)  # 主标签页占所有空间
        self.main_layout.addWidget(self.status_bar)
        
        # 设置标签页切换信号
        self.main_tabs.currentChanged.connect(self.on_tab_changed)
    
    def _create_segment_control_bar(self):
        """创建分段控制条（用于 Auto 和 Manual 标签页）"""
        segment_bar = QGroupBox("Data Segmentation")
        segment_bar.setFixedHeight(65)  # 固定高度，防止窗口扩大时变高
        segment_bar_layout = QHBoxLayout(segment_bar)
        segment_bar_layout.setContentsMargins(5, 5, 5, 5)
        
        # 分段数量
        segment_bar_layout.addWidget(QLabel("Segments:"))
        segment_count_display = QSpinBox()
        segment_count_display.setRange(1, 100)
        segment_count_display.setValue(10)
        segment_count_display.setFixedWidth(70)
        segment_count_display.setToolTip("Number of segments to split data into")
        # 连接到主分段计数器（稍后设置）
        if hasattr(self, 'segment_count_spin'):
            segment_count_display.setValue(self.segment_count_spin.value())
        segment_bar_layout.addWidget(segment_count_display)
        
        # 应用分段按钮
        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(70)
        apply_btn.setEnabled(False)
        apply_btn.setToolTip("Apply segmentation with current settings")
        segment_bar_layout.addWidget(apply_btn)
        
        segment_bar_layout.addSpacing(20)
        
        # 当前段控制
        segment_bar_layout.addWidget(QLabel("Current:"))
        current_seg_spin = QSpinBox()
        current_seg_spin.setRange(1, 1)
        current_seg_spin.setValue(1)
        current_seg_spin.setEnabled(False)
        current_seg_spin.setFixedWidth(60)
        current_seg_spin.setToolTip("Current segment being displayed")
        segment_bar_layout.addWidget(current_seg_spin)
        
        # 前后导航按钮
        prev_btn = QPushButton("←")
        prev_btn.setEnabled(False)
        prev_btn.setMinimumWidth(50)
        prev_btn.setToolTip("Previous segment")
        segment_bar_layout.addWidget(prev_btn)
        
        next_btn = QPushButton("→")
        next_btn.setEnabled(False)
        next_btn.setMinimumWidth(50)
        next_btn.setToolTip("Next segment")
        segment_bar_layout.addWidget(next_btn)
        
        segment_bar_layout.addSpacing(20)
        
        # 段信息显示
        info_label = QLabel("No segmentation")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        segment_bar_layout.addWidget(info_label)
        
        segment_bar_layout.addStretch()
        
        # 保存引用以便后续同步状态
        # 使用对象属性存储这些控件的引用
        segment_bar.segment_count_spin = segment_count_display
        segment_bar.apply_btn = apply_btn
        segment_bar.current_seg_spin = current_seg_spin
        segment_bar.prev_btn = prev_btn
        segment_bar.next_btn = next_btn
        segment_bar.info_label = info_label
        
        # 连接信号
        segment_count_display.valueChanged.connect(lambda v: self.segment_count_spin.setValue(v))
        apply_btn.clicked.connect(self.apply_segmentation)
        current_seg_spin.valueChanged.connect(lambda v: self._on_inline_segment_changed(v, current_seg_spin))
        prev_btn.clicked.connect(self.go_to_prev_segment)
        next_btn.clicked.connect(self.go_to_next_segment)
        
        # 默认隐藏（直到数据加载）
        segment_bar.setVisible(False)
        
        return segment_bar
    
    def on_tab_changed(self, index):
        """处理标签页切换"""
        if index == 0:  # Setup 标签页
            self.status_bar.showMessage("Setup mode - Load data file and select channel")
                    
        elif index == 1:  # 自动检测标签页
            self.status_bar.showMessage("Auto detection mode activated")
            
            # 确保自动检测页面的画布正确设置
            if hasattr(self, 'data') and self.data is not None and self.selected_channel is not None:
                # 重新设置画布和数据，而不是简单地同步
                try:
                    # 重新设置自动检测器的画布
                    self.auto_detector.plot_canvas = self.auto_canvas
                    self.auto_detector.toolbar = self.auto_toolbar
                    self.auto_detector.set_plot_canvas(self.auto_canvas, self.auto_toolbar)
                    
                    # 如果启用了分段，加载当前段数据
                    if self.segmentation_enabled and self.segment_manager is not None:
                        segment_index = self.current_segment - 1
                        self.load_segment_data(segment_index)
                    else:
                        # 否则同步完整数据到画布
                        self.sync_data_to_canvas(self.auto_canvas)
                        
                        # 确保自动检测器知道数据已更改
                        if hasattr(self.auto_detector, 'reset_detection'):
                            self.auto_detector.reset_detection()
                    
                except Exception as e:
                    print(f"Error setting up auto detection tab: {e}")
                    import traceback
                    traceback.print_exc()
                    
        elif index == 2:  # 手动选择标签页
            self.status_bar.showMessage("Manual selection mode activated")
            
            # 确保手动选择页面的画布正确设置
            if hasattr(self, 'data') and self.data is not None and self.selected_channel is not None:
                try:
                    # 重新设置手动选择器的画布
                    self.manual_selector.plot_canvas = self.manual_canvas
                    self.manual_selector.set_plot_canvas(self.manual_canvas)
                    
                    # 如果启用了分段，加载当前段数据
                    if self.segmentation_enabled and self.segment_manager is not None:
                        segment_index = self.current_segment - 1
                        self.load_segment_data(segment_index)
                    else:
                        # 否则同步完整数据到画布
                        self.sync_data_to_canvas(self.manual_canvas)
                        
                        # 确保手动选择器知道数据已更改
                        if hasattr(self.manual_selector, 'update_manual_plot'):
                            self.manual_selector.update_manual_plot()
                    
                except Exception as e:
                    print(f"Error setting up manual selection tab: {e}")
                    import traceback
                    traceback.print_exc()
    
    def sync_data_to_canvas(self, canvas):
        """将当前数据同步到指定的画布"""
        if self.data is None:
            print("No data to sync to canvas")
            return
            
        try:
            # 确定选择的通道数据
            channel_data = None
            
            # 设置当前通道数据
            if isinstance(self.data, dict):
                if self.selected_channel in self.data:
                    channel_data = self.data[self.selected_channel]
                    print(f"Set channel data from dict: {self.selected_channel}")
                else:
                    print(f"Warning: Channel '{self.selected_channel}' not found in data dictionary")
                    # 如果选择的通道不存在，尝试使用第一个可用通道
                    if self.data:
                        first_channel = next(iter(self.data.keys()))
                        channel_data = self.data[first_channel]
                        self.selected_channel = first_channel
                        print(f"Using first available channel: {first_channel}")
            
            elif isinstance(self.data, np.ndarray):
                if self.data.ndim == 1:
                    channel_data = self.data
                    print("Set channel data from 1D array")
                
                elif self.data.ndim == 2:
                    try:
                        if self.selected_channel:
                            # 从 "Channel X" 中提取索引
                            channel_parts = self.selected_channel.split()
                            if len(channel_parts) > 1 and channel_parts[-1].isdigit():
                                channel_index = int(channel_parts[-1]) - 1
                            else:
                                # 尝试将整个字符串转换为索引
                                channel_index = int(self.selected_channel) - 1
                            
                            if 0 <= channel_index < self.data.shape[1]:
                                channel_data = self.data[:, channel_index]
                                print(f"Set channel data from 2D array: {channel_index}")
                            else:
                                print(f"Warning: Channel index {channel_index+1} out of range")
                                # 使用第一列作为后备选项
                                channel_data = self.data[:, 0]
                                print("Using first column as fallback")
                        else:
                            # 如果没有选择通道，使用第一列
                            channel_data = self.data[:, 0]
                            self.selected_channel = "Channel 1"
                            print("No channel selected, using first column")
                    except ValueError:
                        print(f"Warning: Cannot parse channel index from '{self.selected_channel}'")
                        # 使用第一列作为后备选项
                        channel_data = self.data[:, 0]
                        print("Using first column as fallback due to parsing error")
                    except Exception as e:
                        print(f"Error parsing channel: {e}")
                        # 使用第一列作为后备选项
                        channel_data = self.data[:, 0]
                        print("Using first column as fallback due to error")
            
            # 设置画布数据并绘制
            if channel_data is not None:
                # 清除之前的峰值数据
                canvas.peaks_data = {}
                canvas.current_channel_data = channel_data
                canvas.plot_data(channel_data, self.sampling_rate)
                print(f"Plot data called with sampling rate: {self.sampling_rate}")
            else:
                print("Warning: No channel data to plot")
                
        except Exception as e:
            print(f"Error syncing data to canvas: {e}")
            import traceback
            traceback.print_exc()
    
    def _sync_segment_controls(self):
        """同步所有分段控件的状态"""
        # 设置标志防止递归调用
        self._syncing_controls = True
        
        # 同步分段数量
        segment_count = self.segment_count_spin.value()
        self.auto_segment_bar.segment_count_spin.setValue(segment_count)
        self.manual_segment_bar.segment_count_spin.setValue(segment_count)
        
        # 同步当前段
        current_segment = self.current_segment_spin.value()
        self.auto_segment_bar.current_seg_spin.setValue(current_segment)
        self.manual_segment_bar.current_seg_spin.setValue(current_segment)
        
        # 同步启用状态
        apply_enabled = self.apply_segmentation_btn.isEnabled()
        self.auto_segment_bar.apply_btn.setEnabled(apply_enabled)
        self.manual_segment_bar.apply_btn.setEnabled(apply_enabled)
        
        current_enabled = self.current_segment_spin.isEnabled()
        self.auto_segment_bar.current_seg_spin.setEnabled(current_enabled)
        self.manual_segment_bar.current_seg_spin.setEnabled(current_enabled)
        
        # 同步范围
        seg_range_max = self.current_segment_spin.maximum()
        self.auto_segment_bar.current_seg_spin.setRange(1, seg_range_max)
        self.manual_segment_bar.current_seg_spin.setRange(1, seg_range_max)
        
        # 同步导航按钮
        prev_enabled = self.prev_segment_btn.isEnabled()
        next_enabled = self.next_segment_btn.isEnabled()
        self.auto_segment_bar.prev_btn.setEnabled(prev_enabled)
        self.auto_segment_bar.next_btn.setEnabled(next_enabled)
        self.manual_segment_bar.prev_btn.setEnabled(prev_enabled)
        self.manual_segment_bar.next_btn.setEnabled(next_enabled)
        
        # 同步信息标签
        info_text = self.segment_info_label.text()
        info_style = self.segment_info_label.styleSheet()
        self.auto_segment_bar.info_label.setText(info_text)
        self.auto_segment_bar.info_label.setStyleSheet(info_style)
        self.manual_segment_bar.info_label.setText(info_text)
        self.manual_segment_bar.info_label.setStyleSheet(info_style)
        
        # 显示/隐藏控制条（如果有数据则显示）
        has_data = self.data is not None
        self.auto_segment_bar.setVisible(has_data)
        self.manual_segment_bar.setVisible(has_data)
        
        # 重置标志
        self._syncing_controls = False
    
    def connect_signals(self):
        """连接信号和槽"""
        # 文件加载
        self.load_file_btn.clicked.connect(self.load_file)
        
        # 通道选择
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        
        # 采样率变化
        self.sampling_rate_spin.valueChanged.connect(self.on_sampling_rate_changed)
        
        # 分段控制
        self.apply_segmentation_btn.clicked.connect(self.apply_segmentation)
        self.current_segment_spin.valueChanged.connect(self.on_segment_changed)
        self.prev_segment_btn.clicked.connect(self.go_to_prev_segment)
        self.next_segment_btn.clicked.connect(self.go_to_next_segment)
        
        # 自动检测器结果信号
        self.auto_detector.detection_finished.connect(self.on_detection_finished)
        self.auto_detector.duration_calculated.connect(self.on_duration_calculated)
        
        # 手动选择器结果信号
        self.manual_selector.peak_added.connect(self.on_manual_peak_added)
    
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
                    
                    # 清除旧的峰值数据
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.peaks_data = {}
                    if hasattr(self, 'manual_canvas'):
                        self.manual_canvas.peaks_data = {}
                    if hasattr(self, 'manual_selector'):
                        self.manual_selector.manual_spikes = []
                        self.manual_selector.manual_spike_count = 0
                        if hasattr(self.manual_selector, 'peak_count_label'):
                            self.manual_selector.peak_count_label.setText("No manual peaks")
                    
                    # 自动切换到 Auto Detection 标签页
                    self.main_tabs.setCurrentIndex(1)  # Auto Detection tab
                    
                    # 更新自动检测画布
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.current_channel_data = data[first_channel]
                        self.auto_canvas.plot_data(data[first_channel], self.sampling_rate)
            
            elif isinstance(data, np.ndarray):
                # 如果数据是数组格式
                if data.ndim == 1:
                    # 单通道数据
                    self.channel_combo.addItem("Channel 1")
                    self.selected_channel = "Channel 1"
                    self.channel_combo.setCurrentText("Channel 1")
                    
                    # 清除旧的峰值数据
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.peaks_data = {}
                    if hasattr(self, 'manual_canvas'):
                        self.manual_canvas.peaks_data = {}
                    if hasattr(self, 'manual_selector'):
                        self.manual_selector.manual_spikes = []
                        self.manual_selector.manual_spike_count = 0
                        if hasattr(self.manual_selector, 'peak_count_label'):
                            self.manual_selector.peak_count_label.setText("No manual peaks")
                    
                    # 自动切换到 Auto Detection 标签页
                    self.main_tabs.setCurrentIndex(1)  # Auto Detection tab
                    
                    # 更新自动检测画布
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.current_channel_data = data
                        self.auto_canvas.plot_data(data, self.sampling_rate)
                
                elif data.ndim == 2:
                    # 多通道数据
                    for i in range(data.shape[1]):
                        self.channel_combo.addItem(f"Channel {i+1}")
                    
                    # 默认选择第一个通道
                    self.selected_channel = "Channel 1"
                    self.channel_combo.setCurrentText("Channel 1")
                    
                    # 清除旧的峰值数据
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.peaks_data = {}
                    if hasattr(self, 'manual_canvas'):
                        self.manual_canvas.peaks_data = {}
                    if hasattr(self, 'manual_selector'):
                        self.manual_selector.manual_spikes = []
                        self.manual_selector.manual_spike_count = 0
                        if hasattr(self.manual_selector, 'peak_count_label'):
                            self.manual_selector.peak_count_label.setText("No manual peaks")
                    
                    # 自动切换到 Auto Detection 标签页
                    self.main_tabs.setCurrentIndex(1)  # Auto Detection tab
                    
                    # 更新自动检测画布
                    if hasattr(self, 'auto_canvas'):
                        self.auto_canvas.current_channel_data = data[:, 0]
                        self.auto_canvas.plot_data(data[:, 0], self.sampling_rate)
            
            # 文件信息摘要
            summary = ", ".join([f"{k}: {v}" for k, v in info.items() 
                            if k not in ['File Path', 'Modified Time']])
            
            self.status_bar.showMessage(f"Loaded file: {os.path.basename(file_path)} - {summary}")
            
            # 通知自动检测器和手动选择器数据已更改
            if hasattr(self, 'auto_detector') and self.auto_detector is not None:
                if hasattr(self.auto_detector, 'reset_detection'):
                    self.auto_detector.reset_detection()
            
            if hasattr(self, 'manual_selector') and self.manual_selector is not None:
                if hasattr(self.manual_selector, 'update_manual_plot'):
                    self.manual_selector.update_manual_plot()
            
            # 启用分段按钮
            self.apply_segmentation_btn.setEnabled(True)
            
            # 重置分段状态（加载新文件时）
            self.segmentation_enabled = False
            self.segment_manager = None
            self.current_segment_spin.setEnabled(False)
            self.prev_segment_btn.setEnabled(False)
            self.next_segment_btn.setEnabled(False)
            self.segment_info_label.setText("No segmentation applied")
            self.segment_info_label.setStyleSheet("color: gray; font-style: italic;")
            
            # 同步所有分段控件
            self._sync_segment_controls()
            
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
        # 如果有手动标记的 spikes，询问用户是否要清除
        if hasattr(self, 'manual_selector') and self.manual_selector is not None:
            if hasattr(self.manual_selector, 'manual_spikes') and len(self.manual_selector.manual_spikes) > 0:
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self,
                    "Clear Previous Spikes?",
                    f"You have {len(self.manual_selector.manual_spikes)} manually marked spikes from the previous data.\n\nDo you want to clear them and start fresh with the new data?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # 清空 manual spikes
                    self.manual_selector.manual_spikes.clear()
                    self.manual_selector.manual_spike_count = 0
                    if hasattr(self.manual_selector, 'peak_count_label'):
                        self.manual_selector.peak_count_label.setText("No manual peaks")
                    if hasattr(self.manual_selector, 'update_manual_plot'):
                        self.manual_selector.update_manual_plot()
                    if hasattr(self.manual_selector, 'update_spikes_table'):
                        self.manual_selector.update_spikes_table()
        
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
        
        # 更新当前活动画布
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 1:  # Auto Detection tab
            self.auto_canvas.current_channel_data = selected_data
            self.auto_canvas.plot_data(selected_data, self.sampling_rate)
        elif current_tab == 2:  # Manual Selection tab
            self.manual_canvas.current_channel_data = selected_data
            self.manual_canvas.plot_data(selected_data, self.sampling_rate)
        
        # 启用分段按钮（数据已加载）
        if selected_data is not None:
            self.apply_segmentation_btn.setEnabled(True)
        
        # 同步所有分段控件状态
        self._sync_segment_controls()
        
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
            
            # 更新所有画布的数据 - 确保两个标签页都得到更新
            # 更新自动检测页面
            if hasattr(self, 'auto_canvas') and self.auto_canvas is not None:
                # 清除之前的峰值数据
                self.auto_canvas.peaks_data = {}
                self.auto_canvas.current_channel_data = channel_data
                self.auto_canvas.plot_data(channel_data, self.sampling_rate)
                
            # 更新手动选择页面
            if hasattr(self, 'manual_canvas') and self.manual_canvas is not None:
                # 清除之前的手动标记数据
                if hasattr(self, 'manual_selector') and self.manual_selector is not None:
                    self.manual_selector.manual_spikes = []
                    self.manual_selector.manual_spike_count = 0
                    if hasattr(self.manual_selector, 'peak_count_label'):
                        self.manual_selector.peak_count_label.setText("No manual peaks")
                
                self.manual_canvas.peaks_data = {}
                self.manual_canvas.current_channel_data = channel_data
                self.manual_canvas.plot_data(channel_data, self.sampling_rate)
            
            # 通知自动检测器数据已更改
            if hasattr(self, 'auto_detector') and self.auto_detector is not None:
                # 重置检测参数和结果
                if hasattr(self.auto_detector, 'reset_detection'):
                    self.auto_detector.reset_detection()
            
            # 通知手动选择器数据已更改
            if hasattr(self, 'manual_selector') and self.manual_selector is not None:
                # 更新手动选择器的图表
                if hasattr(self.manual_selector, 'update_manual_plot'):
                    self.manual_selector.update_manual_plot()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Error during channel change: {str(e)}")
            print(f"Error in on_channel_changed: {str(e)}")
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变化"""
        self.sampling_rate = value
        
        # 更新图表的时间轴
        if self.data is None:
            return
        
        # 获取当前活动的画布
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 1:  # Auto Detection tab
            active_canvas = self.auto_canvas
        elif current_tab == 2:  # Manual Selection tab
            active_canvas = self.manual_canvas
        else:
            return  # Setup tab - no canvas to update
        
        # 更新活动画布的数据
        if active_canvas.current_channel_data is not None:
            active_canvas.plot_data(active_canvas.current_channel_data, self.sampling_rate)
    
    def on_detection_finished(self, peaks_indices):
        """处理检测完成"""
        # 主要是显示状态信息
        self.status_bar.showMessage(f"Detection completed: {len(peaks_indices)} peaks found")
    
    def on_duration_calculated(self, durations_data):
        """处理持续时间计算完成"""
        # 主要是显示状态信息
        self.status_bar.showMessage(f"Duration calculation completed for {len(durations_data)} peaks")
    
    def on_manual_peak_added(self, peak_data):
        """处理手动峰值添加"""
        self.status_bar.showMessage(f"Manual peak added: Time={peak_data['time']:.4f}s, Amplitude={peak_data['amplitude']:.4f}")
    
    # ========== 数据分段功能方法 ==========
    
    def apply_segmentation(self):
        """应用数据分段"""
        if self.data is None:
            QMessageBox.warning(self, "Warning", "Please load data first")
            return
        
        if self.selected_channel is None:
            QMessageBox.warning(self, "Warning", "Please select a channel first")
            return
        
        # 获取当前通道数据
        channel_data = self._get_current_channel_data()
        if channel_data is None:
            QMessageBox.warning(self, "Warning", "Failed to get channel data")
            return
        
        # 获取分段数量
        num_segments = self.segment_count_spin.value()
        
        # 创建分段管理器
        self.segment_manager = SegmentDataManager(channel_data, self.sampling_rate, num_segments)
        self.num_segments = num_segments
        self.segmentation_enabled = True
        
        # 更新UI状态
        self.current_segment_spin.setRange(1, num_segments)
        self.current_segment_spin.setValue(1)
        self.current_segment_spin.setEnabled(True)
        self.prev_segment_btn.setEnabled(True)
        self.next_segment_btn.setEnabled(True)
        
        # 加载第一段数据（不跳转标签页）
        self.current_segment = 1
        # 直接加载数据到当前活动的标签页
        self.load_segment_data(0)  # 0-based index
        
        # 更新状态栏
        self.status_bar.showMessage(f"Data segmented into {num_segments} segments")
        
        # 同步所有分段控件
        self._sync_segment_controls()
    
    def _on_inline_segment_changed(self, value, sender_spin):
        """处理内联控件的段选择变化（防止循环调用）"""
        # 只在用户实际更改值时触发，而不是同步时
        if not hasattr(self, '_syncing_controls') or not self._syncing_controls:
            # 更新主spinbox
            self.current_segment_spin.blockSignals(True)
            self.current_segment_spin.setValue(value)
            self.current_segment_spin.blockSignals(False)
            # 触发段切换
            self.on_segment_changed(value)
    
    def on_segment_changed(self, segment_1based):
        """处理段选择变化（1-based索引）"""
        if not self.segmentation_enabled or self.segment_manager is None:
            return
        
        # 保存当前段的结果
        self.save_current_segment_results()
        
        # 加载新段的数据
        segment_0based = segment_1based - 1
        self.current_segment = segment_1based
        self.load_segment_data(segment_0based)
    
    def go_to_prev_segment(self):
        """跳转到上一段"""
        if self.current_segment > 1:
            self.current_segment_spin.setValue(self.current_segment - 1)
            # 同步所有分段控件
            self._sync_segment_controls()
    
    def go_to_next_segment(self):
        """跳转到下一段"""
        if self.current_segment < self.num_segments:
            self.current_segment_spin.setValue(self.current_segment + 1)
            # 同步所有分段控件
            self._sync_segment_controls()
    
    def load_segment_data(self, segment_index):
        """加载指定段的数据"""
        if self.segment_manager is None:
            return
        
        # 获取段数据
        segment_data = self.segment_manager.get_segment_data(segment_index)
        if segment_data is None:
            self.status_bar.showMessage(f"Error loading segment {segment_index + 1}")
            return
        
        # 获取段信息
        segment_info = self.segment_manager.get_segment_info(segment_index)
        time_offset = self.segment_manager.get_global_time_offset(segment_index)
        
        # 更新段信息显示
        info_text = (f"Segment {segment_index + 1}/{self.num_segments}: "
                    f"{segment_info['start_sample']}-{segment_info['end_sample']} samples "
                    f"({segment_info['start_time']:.2f}-{segment_info['end_time']:.2f}s)")
        self.segment_info_label.setText(info_text)
        self.segment_info_label.setStyleSheet("color: black; font-style: normal;")
        
        # 加载数据到画布
        current_tab = self.main_tabs.currentIndex()
        
        if current_tab == 1:  # Auto Detection tab
            self.auto_canvas.current_channel_data = segment_data
            self.auto_canvas.plot_data(segment_data, self.sampling_rate, time_offset=time_offset)
            
            # 设置时间偏移
            if hasattr(self.auto_detector, 'set_time_offset'):
                self.auto_detector.set_time_offset(time_offset)
            
            # 恢复之前的检测结果（如果有）
            auto_results, _ = self.segment_manager.get_segment_results(segment_index)
            if auto_results and hasattr(self.auto_detector, 'load_detection_results'):
                self.auto_detector.load_detection_results(auto_results)
        
        elif current_tab == 2:  # Manual Selection tab
            self.manual_canvas.current_channel_data = segment_data
            self.manual_canvas.plot_data(segment_data, self.sampling_rate, time_offset=time_offset)
            
            # 设置时间偏移
            if hasattr(self.manual_selector, 'set_time_offset'):
                self.manual_selector.set_time_offset(time_offset)
            
            # 恢复之前的手动标记（如果有）
            _, manual_results = self.segment_manager.get_segment_results(segment_index)
            if manual_results and hasattr(self.manual_selector, 'load_manual_results'):
                self.manual_selector.load_manual_results(manual_results)
            
            # 重要！调用 update_manual_plot 来刷新 manual selector 的显示
            if hasattr(self.manual_selector, 'update_manual_plot'):
                self.manual_selector.update_manual_plot()
        
        # 同步所有分段控件
        self._sync_segment_controls()
        
        self.status_bar.showMessage(f"Loaded segment {segment_index + 1}/{self.num_segments}")
    
    def save_current_segment_results(self):
        """保存当前段的处理结果"""
        if not self.segmentation_enabled or self.segment_manager is None:
            return
        
        segment_index = self.current_segment - 1  # Convert to 0-based
        
        # 获取自动检测结果
        auto_results = None
        if hasattr(self.auto_detector, 'get_detection_results'):
            auto_results = self.auto_detector.get_detection_results()
        
        # 获取手动标记结果
        manual_results = None
        if hasattr(self.manual_selector, 'get_manual_results'):
            manual_results = self.manual_selector.get_manual_results()
        
        # 保存到分段管理器
        self.segment_manager.save_segment_results(segment_index, auto_results, manual_results)
    
    def _get_current_channel_data(self):
        """获取当前选择通道的数据"""
        if self.data is None or self.selected_channel is None:
            return None
        
        if isinstance(self.data, dict):
            return self.data.get(self.selected_channel, None)
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim == 1:
                return self.data
            elif self.data.ndim == 2:
                try:
                    channel_parts = self.selected_channel.split()
                    if len(channel_parts) > 1 and channel_parts[-1].isdigit():
                        channel_index = int(channel_parts[-1]) - 1
                    else:
                        channel_index = int(self.selected_channel) - 1
                    
                    if 0 <= channel_index < self.data.shape[1]:
                        return self.data[:, channel_index]
                except:
                    pass
        
        return None


    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            # 询问用户是否要清除数据
            should_clear = False
            if hasattr(self, 'manual_selector') and self.manual_selector is not None:
                if hasattr(self.manual_selector, 'manual_spikes') and len(self.manual_selector.manual_spikes) > 0:
                    from PyQt6.QtWidgets import QMessageBox
                    reply = QMessageBox.question(
                        self,
                        "Clear Data on Close?",
                        f"You have {len(self.manual_selector.manual_spikes)} manually marked spikes.\n\nDo you want to clear them when closing this window?\n(Click 'No' to keep them for next time)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No  # 默认不清除
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        should_clear = True
            
            # 关闭所有子窗口
            if hasattr(self, 'manual_selector') and self.manual_selector is not None:
                # 关闭 List 窗口
                if hasattr(self.manual_selector, 'spikes_list_window') and self.manual_selector.spikes_list_window is not None:
                    self.manual_selector.spikes_list_window.close()
                    self.manual_selector.spikes_list_window = None
                
                # 关闭所有 Statistics 窗口
                if hasattr(self.manual_selector, 'statistics_windows'):
                    for window in list(self.manual_selector.statistics_windows.values()):
                        if window is not None:
                            window.close()
                    self.manual_selector.statistics_windows.clear()
                
                # 关闭 Group Manager 窗口
                if hasattr(self.manual_selector, 'group_manager_dialog') and self.manual_selector.group_manager_dialog is not None:
                    self.manual_selector.group_manager_dialog.close()
                    self.manual_selector.group_manager_dialog = None
                
                # 如果用户选择清除数据
                if should_clear:
                    self.manual_selector.manual_spikes.clear()
                    self.manual_selector.manual_spike_count = 0
                    if hasattr(self.manual_selector, 'peak_count_label'):
                        self.manual_selector.peak_count_label.setText("No manual peaks")
            
            # 确保自动检测器中的线程被终止
            if hasattr(self, 'auto_detector'):
                # 终止检测线程
                if hasattr(self.auto_detector, 'detection_thread') and self.auto_detector.detection_thread:
                    if self.auto_detector.detection_thread.isRunning():
                        print("Terminating detection thread...")
                        if hasattr(self.auto_detector, 'detection_worker') and self.auto_detector.detection_worker:
                            self.auto_detector.detection_worker.abort()
                        self.auto_detector.detection_thread.quit()
                        self.auto_detector.detection_thread.wait(1000)  # 等待最多1秒
                        if self.auto_detector.detection_thread.isRunning():
                            print("Force terminating detection thread")
                            self.auto_detector.detection_thread.terminate()
                            self.auto_detector.detection_thread.wait()
                
                # 终止持续时间计算线程
                if hasattr(self.auto_detector, 'duration_thread') and self.auto_detector.duration_thread:
                    if self.auto_detector.duration_thread.isRunning():
                        print("Terminating duration thread...")
                        if hasattr(self.auto_detector, 'duration_worker') and self.auto_detector.duration_worker:
                            self.auto_detector.duration_worker.abort()
                        self.auto_detector.duration_thread.quit()
                        self.auto_detector.duration_thread.wait(1000)
                        if self.auto_detector.duration_thread.isRunning():
                            print("Force terminating duration thread")
                            self.auto_detector.duration_thread.terminate()
                            self.auto_detector.duration_thread.wait()
            
            print("All threads terminated")
            # 继续正常关闭处理
            super().closeEvent(event)
            
        except Exception as e:
            print(f"Error in closeEvent: {e}")
            import traceback
            traceback.print_exc()
            # 确保即使出错也能关闭窗口
            event.accept()