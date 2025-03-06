#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
功率谱密度分析器对话框模块
"""

import os
import numpy as np
import json
import traceback
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QLabel, QTextEdit, QPushButton, QFileDialog, 
                            QComboBox, QDoubleSpinBox, QGroupBox, QFormLayout, QCheckBox,
                            QMessageBox, QProgressDialog, QSplitter, QSlider,
                            QSpinBox, QRadioButton, QButtonGroup, QToolButton, QListWidget,
                            QListWidgetItem)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QFont, QIcon, QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.cm as cm

from .data_loader import DataLoader
from .psd_visualizer import PSDVisualizer
from .psd_worker import PSDWorker, export_psd_to_csv, export_psd_to_json, export_psd_to_npy


class PSDAnalyzerDialog(QDialog):
    """功率谱密度分析器对话框"""
    def __init__(self, parent=None, data=None, sampling_rate=None, title=None):
        super(PSDAnalyzerDialog, self).__init__(parent)
        
        # 设置窗口标题和大小
        self.setWindowTitle(title or "PSD Analyzer")
        self.resize(1200, 800)
        
        # 创建文件加载器
        self.file_loader = DataLoader()
        
        # 存储直接传入的数据
        self.direct_data = data
        self.direct_sampling_rate = sampling_rate
        
        # 创建PSD计算线程
        self.psd_worker = None
        
        # 创建界面元素
        self._init_ui()
        
        # 应用样式
        self.apply_style()
        
        # 如果有直接传入的数据，初始化
        if self.direct_data is not None:
            self.initialize_with_direct_data()
    
    def _init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        
        # 创建顶部工具栏区域
        self._init_toolbar()
        
        # 创建主分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建左侧面板
        self._init_left_panel()
        
        # 创建右侧面板
        self._init_right_panel()
        
        # 添加面板到分割器
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        
        # 设置分割器的初始大小比例
        self.splitter.setSizes([300, 900])
        
        # 添加分割器到主布局
        self.main_layout.addWidget(self.splitter)
        
        # 添加底部按钮栏
        self._init_bottom_bar()
        
        # 连接信号槽
        self._connect_signals()
    
    def _init_toolbar(self):
        """初始化顶部工具栏"""
        self.toolbar_layout = QHBoxLayout()
        
        # 文件选择按钮
        self.open_button = QPushButton("Open Data File")
        self.open_button.setIcon(QIcon.fromTheme("document-open"))
        
        # 文件路径显示
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("color: #666; font-style: italic;")
        
        # 内存使用情况显示
        self.memory_label = QLabel("Memory: 0 MB")
        self.memory_label.setStyleSheet("color: #666;")
        
        self.toolbar_layout.addWidget(self.open_button)
        self.toolbar_layout.addWidget(self.file_path_label, 1)  # 1表示拉伸因子
        self.toolbar_layout.addWidget(self.memory_label)
        
        # 添加工具栏到主布局
        self.main_layout.addLayout(self.toolbar_layout)
    
    def _init_left_panel(self):
        """初始化左侧面板"""
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        
        # 文件信息区域
        self.info_group = QGroupBox("File Information")
        self.info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        
        self.info_layout.addWidget(self.info_text)
        self.info_group.setLayout(self.info_layout)
        
        # 通道选择区域
        self.channel_group = QGroupBox("Channel Selection")
        self.channel_layout = QVBoxLayout()
        
        self.channel_combo = QComboBox()
        
        self.channel_layout.addWidget(self.channel_combo)
        self.channel_group.setLayout(self.channel_layout)
        
        # 采样率设置
        self.sampling_group = QGroupBox("Sampling Rate")
        self.sampling_layout = QVBoxLayout()
        
        self.sampling_layout_inner = QHBoxLayout()
        self.sampling_label = QLabel("Rate (Hz):")
        self.sampling_input = QDoubleSpinBox()
        self.sampling_input.setRange(0.1, 1000000.0)
        self.sampling_input.setValue(1000.0)
        self.sampling_input.setDecimals(1)
        self.sampling_input.setSingleStep(100.0)
        
        self.sampling_layout_inner.addWidget(self.sampling_label)
        self.sampling_layout_inner.addWidget(self.sampling_input)
        
        self.sampling_layout.addLayout(self.sampling_layout_inner)
        self.sampling_group.setLayout(self.sampling_layout)
        
        # 添加到左侧布局
        self.left_layout.addWidget(self.info_group)
        self.left_layout.addWidget(self.channel_group)
        self.left_layout.addWidget(self.sampling_group)
        self.left_layout.addStretch(1)  # 添加弹性空间
    
    def _init_right_panel(self):
        """初始化右侧面板"""
        self.right_panel = QTabWidget()
        
        # 创建数据可视化选项卡
        self._init_visualize_tab()
        
        # 创建PSD分析选项卡
        self._init_analysis_tab()
        
        # 创建比较选项卡
        self._init_compare_tab()
        
        # 添加选项卡到右侧面板
        self.right_panel.addTab(self.visualize_tab, "Data Visualization")
        self.right_panel.addTab(self.analysis_tab, "PSD Analysis")
        self.right_panel.addTab(self.compare_tab, "Compare PSDs")
    
    def _init_visualize_tab(self):
        """初始化数据可视化选项卡"""
        self.visualize_tab = QWidget()
        self.visualize_layout = QVBoxLayout(self.visualize_tab)
        
        # 创建可视化组件
        self.visualizer = FigureCanvas(Figure(figsize=(8, 6)))
        self.axes = self.visualizer.figure.add_subplot(111)
        
        # 创建导航工具栏
        self.toolbar = NavigationToolbar(self.visualizer, self.visualize_tab)
        
        # 添加到可视化选项卡
        self.visualize_layout.addWidget(self.toolbar)
        self.visualize_layout.addWidget(self.visualizer)
    
    def _init_analysis_tab(self):
        """初始化数据分析选项卡"""
        self.analysis_tab = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_tab)
        
        # 创建PSD分析布局
        # 使用水平分割器分隔控件区和可视化区
        self.analysis_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 创建PSD控制面板
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建PSD分析组件
        self.psd_group = QGroupBox("Power Spectral Density Analysis")
        self.psd_layout = QVBoxLayout()
        self.psd_group.setLayout(self.psd_layout)
        
        # PSD参数设置 - 使用更紧凑的布局
        params_container = QWidget()
        params_layout = QHBoxLayout(params_container)
        params_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧参数
        left_params = QWidget()
        left_layout = QFormLayout(left_params)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setVerticalSpacing(5)

        # 参数控件...
        # [这里保留原来的参数控件代码]
        
        # 添加窗口类型选择
        self.psd_window_combo = QComboBox()
        self.psd_window_combo.addItems(["Hamming", "Blackman", "Hann", "Bartlett", "Flattop", "Rectangular"])
        self.psd_window_combo.setCurrentText("Hann")  # 将Hann设为默认窗口
        
        # 添加FFT长度选择
        self.psd_nfft_combo = QComboBox()
        self.psd_nfft_combo.addItem("Auto (based on data)")
        nfft_options = [str(2**n) for n in range(8, 24)]  # 256到65536小遨1600万点
        self.psd_nfft_combo.addItems(nfft_options)
        self.psd_nfft_combo.setCurrentText("4096")  # 默认值
        self.psd_nfft_combo.setToolTip(
            "频率分辨率 = 采样率/NFFT\n"
            "小值: 提供更快的计算速度\n"
            "大值: 提供更精细的频率分辨率\n\n"
            "Auto: 自动选择接近数据长度的值\n"
            "建议: 短信号(<1000点)用小值，长信号(>10000点)用大值"
        )
        
        # 添加段长选择
        self.psd_nperseg_combo = QComboBox()
        self.psd_nperseg_combo.addItems(["Same as NFFT", "NFFT/2", "NFFT/4", "NFFT/8"])
        self.psd_nperseg_combo.setCurrentText("Same as NFFT")
        
        # 添加重叠率选择
        self.psd_noverlap_combo = QComboBox()
        self.psd_noverlap_combo.addItems(["None", "25%", "50%", "75%"])
        self.psd_noverlap_combo.setCurrentText("50%")
        
        # 添加去趋势选择
        self.psd_detrend_combo = QComboBox()
        self.psd_detrend_combo.addItems(["Constant", "Linear", "None"])
        
        # 添加缩放选择
        self.psd_scaling_combo = QComboBox()
        self.psd_scaling_combo.addItems(["Density", "Spectrum"])
        self.psd_scaling_combo.setToolTip("Density: V²/Hz, Spectrum: V² (scaled by frequency resolution)")
        
        # 添加显示格式选择
        self.psd_display_combo = QComboBox()
        self.psd_display_combo.addItems(["dB Scale", "Raw Power"])
        
        left_layout.addRow("Window:", self.psd_window_combo)
        left_layout.addRow("FFT Length:", self.psd_nfft_combo)
        left_layout.addRow("Segment Length:", self.psd_nperseg_combo)
        left_layout.addRow("Overlap:", self.psd_noverlap_combo)
        left_layout.addRow("Detrend:", self.psd_detrend_combo)
        left_layout.addRow("Scaling:", self.psd_scaling_combo)
        left_layout.addRow("Display:", self.psd_display_combo)
        
        # 右侧参数
        right_params = QWidget()
        right_layout = QFormLayout(right_params)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setVerticalSpacing(5)
        
        # 添加截止频率设置
        freq_cutoff = QWidget()
        cutoff_layout = QHBoxLayout(freq_cutoff)
        cutoff_layout.setContentsMargins(0, 0, 0, 0)
        cutoff_layout.setSpacing(5)
        
        self.cutoff_freq_low = QDoubleSpinBox()
        self.cutoff_freq_low.setRange(0, 100000)
        self.cutoff_freq_low.setValue(0)  # 默认不设置低频截止
        self.cutoff_freq_low.setSingleStep(10)
        
        self.cutoff_freq_high = QDoubleSpinBox()
        self.cutoff_freq_high.setRange(0, 100000)
        self.cutoff_freq_high.setValue(0)  # 默认不设置高频截止
        self.cutoff_freq_high.setSingleStep(100)
        
        cutoff_layout.addWidget(QLabel("Low(Hz):"))
        cutoff_layout.addWidget(self.cutoff_freq_low)
        cutoff_layout.addWidget(QLabel("High(Hz):"))
        cutoff_layout.addWidget(self.cutoff_freq_high)
        
        # 添加峰值检测设置
        self.peak_detection = QGroupBox("Peak Detection")
        self.peak_detection.setCheckable(True)
        self.peak_detection.setChecked(False)
        peak_layout = QVBoxLayout(self.peak_detection)
        
        # 添加峰值高度设置
        height_widget = QWidget()
        height_layout = QHBoxLayout(height_widget)
        height_layout.setContentsMargins(0, 0, 0, 0)
        
        self.peak_height_label = QLabel("Height(%)")
        self.peak_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.peak_height_slider.setRange(1, 99)
        self.peak_height_slider.setValue(20)  # 默认值
        self.peak_height_value = QLabel("20%")
        
        height_layout.addWidget(self.peak_height_label)
        height_layout.addWidget(self.peak_height_slider, 1)
        height_layout.addWidget(self.peak_height_value)
        
        # 添加峰值间距设置
        distance_widget = QWidget()
        distance_layout = QHBoxLayout(distance_widget)
        distance_layout.setContentsMargins(0, 0, 0, 0)
        
        self.peak_distance_label = QLabel("Min Dist(Hz):")
        self.peak_distance_spin = QDoubleSpinBox()
        self.peak_distance_spin.setRange(0, 1000)
        self.peak_distance_spin.setValue(5)  # 默认值
        self.peak_distance_spin.setSingleStep(1)
        
        distance_layout.addWidget(self.peak_distance_label)
        distance_layout.addWidget(self.peak_distance_spin)
        
        # 添加峰值阈值设置
        threshold_widget = QWidget()
        threshold_layout = QHBoxLayout(threshold_widget)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        
        self.peak_threshold_label = QLabel("Prominence(%):")
        self.peak_threshold_spin = QSpinBox()
        self.peak_threshold_spin.setRange(0, 100)
        self.peak_threshold_spin.setValue(5)  # 默认值5%
        
        threshold_layout.addWidget(self.peak_threshold_label)
        threshold_layout.addWidget(self.peak_threshold_spin)
        
        # 将峰值检测控件添加到峰值检测布局
        peak_layout.addWidget(height_widget)
        peak_layout.addWidget(distance_widget)
        peak_layout.addWidget(threshold_widget)
        
        # 添加复选框设置
        option_widget = QWidget()
        option_layout = QHBoxLayout(option_widget)
        option_layout.setContentsMargins(0, 0, 0, 0)
        
        self.psd_normalize_check = QCheckBox("Normalize")
        self.psd_normalize_check.setChecked(True)
        
        self.psd_log_x_check = QCheckBox("Log X")
        self.psd_log_x_check.setChecked(True)
        
        self.psd_log_y_check = QCheckBox("Log Y")
        self.psd_log_y_check.setChecked(True)
        
        self.psd_exclude_dc_check = QCheckBox("Exclude DC")
        self.psd_exclude_dc_check.setChecked(True)
        
        option_layout.addWidget(self.psd_normalize_check)
        option_layout.addWidget(self.psd_log_x_check)
        option_layout.addWidget(self.psd_log_y_check)
        option_layout.addWidget(self.psd_exclude_dc_check)
        
        # 添加频带分析选择器切换
        band_selector_widget = QWidget()
        band_selector_layout = QHBoxLayout(band_selector_widget)
        band_selector_layout.setContentsMargins(0, 0, 0, 0)
        
        self.band_selector_check = QCheckBox("Enable Band Selector")
        self.band_selector_check.setChecked(False)
        
        band_selector_layout.addWidget(self.band_selector_check)
        
        # 添加到右侧布局
        right_layout.addRow("Cutoffs:", freq_cutoff)
        right_layout.addRow("", self.peak_detection)
        right_layout.addRow("Options:", option_widget)
        right_layout.addRow("", band_selector_widget)
        
        # 按钮布局
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.compute_psd_button = QPushButton("Compute PSD")
        
        self.export_psd_button = QPushButton("Export PSD")
        self.export_psd_button.setEnabled(False)  # 默认禁用
        
        # 新增添加到比较标签页的按钮
        self.add_to_compare_button = QPushButton("Add to Compare")
        self.add_to_compare_button.setEnabled(False)  # 默认禁用
        
        self.save_preset_button = QPushButton("Save Preset")
        
        self.load_preset_button = QPushButton("Load Preset")
        
        button_layout.addWidget(self.compute_psd_button)
        button_layout.addWidget(self.export_psd_button)
        button_layout.addWidget(self.add_to_compare_button)
        button_layout.addWidget(self.save_preset_button)
        button_layout.addWidget(self.load_preset_button)
        button_layout.addStretch(1)
        
        # 将左右两侧参数添加到参数容器
        params_layout.addWidget(left_params)
        params_layout.addWidget(right_params)
        
        # 添加到PSD布局
        self.psd_layout.addWidget(params_container)
        self.psd_layout.addWidget(button_widget)
        
        # 添加PSD面板到控制区域
        controls_layout.addWidget(self.psd_group)
        
        # 创建PSD可视化区域
        viz_panel = QWidget()
        viz_layout = QVBoxLayout(viz_panel)
        viz_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建PSD可视化组件
        self.psd_visualizer = PSDVisualizer(viz_panel)
        
        # 添加导航工具栏
        self.psd_toolbar = NavigationToolbar(self.psd_visualizer, viz_panel)
        
        # 将工具栏和可视化器添加到布局
        viz_layout.addWidget(self.psd_toolbar)
        viz_layout.addWidget(self.psd_visualizer)
        
        # 添加控制面板和可视化区域到分割器
        self.analysis_splitter.addWidget(controls_panel)
        self.analysis_splitter.addWidget(viz_panel)
        
        # 设置初始分割大小，让可视化区域比控制区域大
        self.analysis_splitter.setSizes([300, 600])
        
        # 添加分割器到分析选项卡
        self.analysis_layout.addWidget(self.analysis_splitter)
    
    def _init_compare_tab(self):
        """初始化PSD比较选项卡"""
        self.compare_tab = QWidget()
        self.compare_layout = QVBoxLayout(self.compare_tab)
        self.compare_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        self.compare_layout.setSpacing(4)  # 减小间距
        
        # 创建比较功能区域的工具栏
        tools_widget = QWidget()
        tools_layout = QHBoxLayout(tools_widget)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        
        # 设置工具栏的最小/最大高度
        tools_widget.setMinimumHeight(40)
        tools_widget.setMaximumHeight(40)  # 固定高度，避免过大
        
        # 清除按钮
        self.clear_compare_button = QPushButton("Clear All")
        self.clear_compare_button.setEnabled(False)  # 初始禁用
        
        # 删除选定项目按钮
        self.remove_selected_button = QPushButton("Remove Selected")
        self.remove_selected_button.setEnabled(False)  # 初始禁用
        
        # 一些显示选项的复选框
        self.normalize_compare_check = QCheckBox("Normalize")
        self.normalize_compare_check.setChecked(True)
        
        self.log_x_compare_check = QCheckBox("Log X")
        self.log_x_compare_check.setChecked(True)
        
        self.log_y_compare_check = QCheckBox("Log Y")
        self.log_y_compare_check.setChecked(True)
        
        self.show_legend_check = QCheckBox("Show Legend")
        self.show_legend_check.setChecked(True)
        self.show_legend_check.setToolTip("Toggle legend visibility")
        
        # 添加到工具栏布局
        tools_layout.addWidget(self.clear_compare_button)
        tools_layout.addWidget(self.remove_selected_button)
        tools_layout.addWidget(QLabel(" | "))  # 分隔符
        tools_layout.addWidget(self.normalize_compare_check)
        tools_layout.addWidget(self.log_x_compare_check)
        tools_layout.addWidget(self.log_y_compare_check)
        tools_layout.addWidget(self.show_legend_check)
        tools_layout.addStretch(1)
        
        # 创建列表显示已添加的PSD
        list_group = QGroupBox("Added PSD Curves")
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(2, 5, 2, 2)  # 缩小边距
        list_layout.setSpacing(2)  # 缩小间距
        
        self.psd_list_widget = QListWidget()
        self.psd_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.psd_list_widget.itemSelectionChanged.connect(self.on_compare_selection_changed)
        
        list_layout.addWidget(self.psd_list_widget)
        
        # 创建比较图表
        self.compare_figure = Figure(figsize=(8, 6))
        self.compare_canvas = FigureCanvas(self.compare_figure)
        self.compare_axes = self.compare_figure.add_subplot(111)
        
        # 创建导航工具栏
        self.compare_toolbar = NavigationToolbar(self.compare_canvas, self.compare_tab)
        
        # 将所有组件添加到比较页面布局
        self.compare_layout.addWidget(tools_widget)
        
        # 创建一个分割器，左边是列表，右边是图表
        compare_splitter = QSplitter(Qt.Orientation.Horizontal)
        compare_splitter.addWidget(list_group)
        
        # 创建图表容器
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)  # 直接消除工具栏和图表间的间距
        chart_layout.addWidget(self.compare_toolbar)
        chart_layout.addWidget(self.compare_canvas)
        
        compare_splitter.addWidget(chart_container)
        
        # 设置初始分割比例 - 列表窄一些，图表宽一些
        # 在最大化时完全利用新空间
        compare_splitter.setSizes([150, 1000])
        
        self.compare_layout.addWidget(compare_splitter)
        
        # 初始化存储比较数据的列表
        self.compare_data = []
    
    def _init_bottom_bar(self):
        """初始化底部状态栏"""
        self.button_layout = QHBoxLayout()
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        
        self.close_button = QPushButton("Close")
        
        self.button_layout.addWidget(self.status_label, 1)
        self.button_layout.addWidget(self.close_button)
        
        self.main_layout.addLayout(self.button_layout)
    
    def _connect_signals(self):
        """连接信号槽"""
        # 主界面按钮
        self.open_button.clicked.connect(self.open_data_file)
        self.close_button.clicked.connect(self.reject)
        
        # 通道选择改变
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        
        # 采样率改变
        self.sampling_input.valueChanged.connect(self.on_sampling_rate_changed)
        
        # PSD计算
        self.compute_psd_button.clicked.connect(self.compute_psd)
        self.export_psd_button.clicked.connect(self.export_psd)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.load_preset_button.clicked.connect(self.load_preset)
        
        # 峰值高度滑块的值变化
        self.peak_height_slider.valueChanged.connect(self.update_peak_height_label)
        
        # 峰值检测复选框
        self.peak_detection.toggled.connect(self.toggle_peak_detection_options)
        
        # 频带选择器
        self.band_selector_check.stateChanged.connect(self.toggle_band_selector)
        
        # 初始禁用峰值检测选项
        self.toggle_peak_detection_options(False)
        
        # 比较相关功能
        self.add_to_compare_button.clicked.connect(self.add_to_compare)
        self.clear_compare_button.clicked.connect(self.clear_all_compare)
        self.remove_selected_button.clicked.connect(self.remove_selected_compare)
        
        # 比较选项变化
        self.normalize_compare_check.stateChanged.connect(self.update_compare_plot)
        self.log_x_compare_check.stateChanged.connect(self.update_compare_plot)
        self.log_y_compare_check.stateChanged.connect(self.update_compare_plot)
        self.show_legend_check.stateChanged.connect(self.update_compare_plot)
    
    def apply_style(self):
        """应用NPA风格"""
        # 应用全局样式
        if hasattr(self.parent(), 'styleSheet') and self.parent().styleSheet():
            self.setStyleSheet(self.parent().styleSheet())
            
        # 设置各组件的字体和颜色
        title_font = QFont("Arial", 11, QFont.Weight.Bold)
        self.info_group.setFont(title_font)
        self.channel_group.setFont(title_font)
        self.sampling_group.setFont(title_font)
        self.psd_group.setFont(title_font)
        
        # 应用按钮样式
        for button in [self.open_button, self.compute_psd_button, self.export_psd_button, 
                       self.save_preset_button, self.load_preset_button, self.close_button]:
            button.setMinimumHeight(30)
            
        # 设置文本框和下拉框样式
        self.info_text.setStyleSheet("background-color: #f8f8f8; border: 1px solid #ddd; padding: 5px;")
        
        # 设置图表元素集合
        for canvas in [self.visualizer, self.psd_visualizer]:
            canvas.figure.patch.set_facecolor('#f8f8f8')
            canvas.figure.set_dpi(100)
    
    def update_peak_height_label(self, value):
        """更新峰值高度标签"""
        self.peak_height_value.setText(f"{value}%")
        
    def toggle_peak_detection_options(self, enabled):
        """切换峰值检测选项的启用状态"""
        for widget in [self.peak_height_slider, self.peak_height_label, self.peak_height_value,
                      self.peak_distance_spin, self.peak_distance_label,
                      self.peak_threshold_spin, self.peak_threshold_label]:
            widget.setEnabled(enabled)
    
    def toggle_band_selector(self, state):
        """切换频带选择器"""
        enabled = state == Qt.CheckState.Checked.value
        self.psd_visualizer.toggle_region_selector(enabled)
    
    def initialize_with_direct_data(self):
        """使用直接传入的数据初始化对话框"""
        if self.direct_data is None:
            return False
            
        # 更新文件路径显示
        self.file_path_label.setText("Current Visualization Data")
        self.file_path_label.setStyleSheet("color: #000; font-weight: bold;")
        
        # 创建信息字典
        info = {
            "Data Source": "Current Visualization",
            "Sampling Rate": f"{self.direct_sampling_rate} Hz" if self.direct_sampling_rate else "Unknown"
        }
        
        # 根据数据类型添加更多信息
        if isinstance(self.direct_data, dict):
            info["Data Type"] = "Multi-channel Data (Dictionary)"
            info["Channels"] = str(len(self.direct_data))
            channel_sizes = [len(data) for data in self.direct_data.values()]
            info["Data Points"] = ", ".join([str(size) for size in channel_sizes])
        elif isinstance(self.direct_data, np.ndarray):
            if self.direct_data.ndim == 1:
                info["Data Type"] = "Single-channel Data (Array)"
                info["Data Points"] = str(len(self.direct_data))
            elif self.direct_data.ndim == 2:
                info["Data Type"] = "Multi-channel Data (2D Array)"
                info["Channels"] = str(self.direct_data.shape[1])
                info["Data Points"] = str(self.direct_data.shape[0])
        
        # 更新文件信息
        self.update_file_info(info)
        
        # 设置采样率
        if self.direct_sampling_rate:
            self.sampling_input.setValue(self.direct_sampling_rate)
            self.file_loader.sampling_rate = self.direct_sampling_rate
        
        # 将数据设置到file_loader中
        # 同时保存到current_data和original_data，确保PSD计算使用原始数据
        if isinstance(self.direct_data, dict):
            self.file_loader.current_data = self.direct_data
            self.file_loader.original_data = dict(self.direct_data)  # 复制一份作为原始数据
        elif isinstance(self.direct_data, np.ndarray):
            if self.direct_data.ndim == 1:
                # 单通道数据
                self.file_loader.current_data = {"Channel 1": self.direct_data}
                self.file_loader.original_data = {"Channel 1": np.copy(self.direct_data)}
            elif self.direct_data.ndim == 2:
                # 多通道数据，转换为字典
                self.file_loader.current_data = {}
                self.file_loader.original_data = {}
                for i in range(self.direct_data.shape[1]):
                    self.file_loader.current_data[f"Channel {i+1}"] = self.direct_data[:, i]
                    self.file_loader.original_data[f"Channel {i+1}"] = np.copy(self.direct_data[:, i])
        
        # 更新通道列表
        self.update_channel_list()
        
        # 更新内存使用信息
        self.update_memory_usage()
        
        # 选择第一个通道
        channels = self.file_loader.get_channel_names()
        if channels:
            self.plot_channel(channels[0])
            
        return True
    
    def update_memory_usage(self):
        """更新内存使用信息"""
        memory_mb = self.file_loader.get_memory_usage()
        self.memory_label.setText(f"Memory: {memory_mb:.1f} MB")
        
        # 如果内存使用超过1GB，显示警告
        if memory_mb > 1000:
            self.memory_label.setStyleSheet("color: #f00; font-weight: bold;")
        else:
            self.memory_label.setStyleSheet("color: #666;")
    
    def open_data_file(self):
        """打开数据文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Data File", "", 
            "All Supported Files (*.h5 *.hdf5);;HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        
        if file_path:
            self.load_file(file_path)
    
    def load_file(self, file_path):
        """加载文件"""
        # 加载文件，传入当前窗口作为进度对话框的父窗口
        success, data, info = self.file_loader.load_file(file_path, self)
        
        if success:
            # 更新文件路径显示
            self.file_path_label.setText(os.path.basename(file_path))
            self.file_path_label.setStyleSheet("color: #000; font-weight: bold;")
            
            # 更新文件信息
            self.update_file_info(info)
            
            # 更新通道列表
            self.update_channel_list()
            
            # 更新内存使用信息
            self.update_memory_usage()
            
            # 获取采样率
            sampling_rate = self.file_loader.sampling_rate
            
            # 更新采样率设置
            self.sampling_input.setValue(sampling_rate)
            
            # 如果有通道数据，默认显示第一个通道
            channels = self.file_loader.get_channel_names()
            if channels:
                self.plot_channel(channels[0])
        else:
            QMessageBox.warning(self, "Error", f"Error loading file: {info.get('Error', 'Unknown error')}")
    
    def update_file_info(self, info_dict):
        """更新文件信息显示"""
        info_html = ""
        for key, value in info_dict.items():
            info_html += f"<b>{key}:</b> {value}<br>"
        
        self.info_text.setHtml(info_html)
    
    def update_channel_list(self):
        """更新通道列表"""
        channels = self.file_loader.get_channel_names()
        
        self.channel_combo.clear()
        if channels:
            self.channel_combo.addItems(channels)
    
    def on_channel_changed(self, index):
        """通道选择变更处理"""
        if index >= 0 and self.channel_combo.count() > index:
            channel_name = self.channel_combo.itemText(index)
            self.plot_channel(channel_name)
            
            # 自动推荐NFFT值
            self.recommend_nfft_value(channel_name)
    
    def on_sampling_rate_changed(self, value):
        """采样率变更处理"""
        # 更新文件加载器的采样率
        self.file_loader.sampling_rate = value
        
        # 重新绘制当前选择的通道
        if self.channel_combo.currentIndex() >= 0:
            channel_name = self.channel_combo.currentText()
            self.plot_channel(channel_name)
    
    def plot_channel(self, channel_name):
        """绘制指定通道的数据"""
        if not self.file_loader.current_data:
            return
        
        channel_data = self.file_loader.get_channel_data(channel_name)
        if channel_data is None:
            return
        
        # 清空当前图表
        self.axes.clear()
        
        # 获取采样率
        sampling_rate = self.sampling_input.value()
        
        # 创建时间轴
        time_axis = np.arange(len(channel_data)) / sampling_rate
        
        # 智能缩减数据点，避免绘制过多点导致卡顿
        max_display_points = 10000  # 最大显示点数
        if len(channel_data) > max_display_points:
            downsample_factor = len(channel_data) // max_display_points
            downsampled_data = channel_data[::downsample_factor]
            downsampled_time = time_axis[::downsample_factor]
            self.axes.plot(downsampled_time, downsampled_data)
            self.status_label.setText(f"Showing downsampled data (1:{downsample_factor})")
        else:
            self.axes.plot(time_axis, channel_data)
            self.status_label.setText("")
        
        # 设置图表标题和标签
        self.axes.set_title(f"Channel: {channel_name}")
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("Amplitude")
        self.axes.grid(True)
        
        # 重绘图表
        self.visualizer.figure.tight_layout()
        self.visualizer.draw()
    
    def compute_psd(self):
        """计算功率谱密度"""
        if not self.file_loader.current_data:
            QMessageBox.warning(self, "Error", "No data loaded")
            return
        
        # 获取当前选择的通道
        if self.channel_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Error", "No channel selected")
            return
        
        channel_name = self.channel_combo.currentText()
        # 注意：这里使用原始数据计算PSD
        channel_data = self.file_loader.get_channel_data(channel_name, use_original=True)
        
        if channel_data is None:
            QMessageBox.warning(self, "Error", f"Cannot get data for channel: {channel_name}")
            return
        
        # 获取PSD参数
        window = self.psd_window_combo.currentText().lower()
        
        # 处理NFFT设置
        nfft_text = self.psd_nfft_combo.currentText()
        if nfft_text == "Auto (based on data)":
            # 自动选择NFFT：使用比数据长度大的下一个2的幂次
            data_length = len(channel_data)
            nfft = 1
            while nfft < data_length:
                nfft *= 2
            
            # 对于过长的数据，限制为16777216（2^24）
            nfft = min(nfft, 16777216)
            
            # 通知用户自动选择的值
            QMessageBox.information(self, "Auto NFFT", 
                                f"Data length: {data_length} points\n"
                                f"Selected NFFT: {nfft}")
        else:
            # 直接使用指定的NFFT值
            nfft = int(nfft_text)
        
        # 获取段长设置
        nperseg_text = self.psd_nperseg_combo.currentText()
        if nperseg_text == "Same as NFFT":
            nperseg = nfft
        elif nperseg_text == "NFFT/2":
            nperseg = nfft // 2
        elif nperseg_text == "NFFT/4":
            nperseg = nfft // 4
        elif nperseg_text == "NFFT/8":
            nperseg = nfft // 8
        else:
            nperseg = nfft
        
        # 获取重叠设置
        noverlap_text = self.psd_noverlap_combo.currentText()
        if noverlap_text == "None":
            noverlap = 0
        elif noverlap_text == "25%":
            noverlap = int(nperseg * 0.25)
        elif noverlap_text == "50%":
            noverlap = int(nperseg * 0.5)
        elif noverlap_text == "75%":
            noverlap = int(nperseg * 0.75)
        else:
            noverlap = int(nperseg * 0.5)
            
        # 获取去趋势设置
        detrend = self.psd_detrend_combo.currentText().lower()
        if detrend == "none":
            detrend = False
            
        # 获取缩放设置
        scaling = self.psd_scaling_combo.currentText().lower()
            
        # 获取其他显示设置
        normalize = self.psd_normalize_check.isChecked()
        log_x = self.psd_log_x_check.isChecked()
        log_y = self.psd_log_y_check.isChecked()
        exclude_dc = self.psd_exclude_dc_check.isChecked()
        is_db_scale = self.psd_display_combo.currentText() == "dB Scale"
        low_cutoff = self.cutoff_freq_low.value()
        high_cutoff = self.cutoff_freq_high.value()
        
        # 获取峰值检测设置
        find_peaks_enabled = self.peak_detection.isChecked()
        peak_height = self.peak_height_slider.value()
        peak_distance = self.peak_distance_spin.value()
        peak_threshold = self.peak_threshold_spin.value()
        
        # 检查数据长度
        data_length = len(channel_data)
        if data_length < nperseg:
            QMessageBox.warning(self, "Warning", 
                             f"Data length ({data_length}) is less than segment length ({nperseg}). "+
                             "Using data length as segment length.")
            nperseg = data_length
            
        # 基于数据长度的智能调整
        if data_length < 64:  # 通常welch方法需要一定数量的数据点
            QMessageBox.warning(self, "Warning", 
                             f"Data length ({data_length}) is too short for reliable PSD estimation. "+
                             "Results may not be meaningful.")
            
        # 禁用计算按钮，避免重复点击
        self.compute_psd_button.setEnabled(False)
        self.compute_psd_button.setText("Computing...")
        self.status_label.setText("Computing PSD...")
        
        # 创建进度对话框
        progress = QProgressDialog("Computing PSD...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Computing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        progress.setValue(0)
        
        # 如果使用原始数据，显示信息
        data_length = len(channel_data)
        if data_length > 1000000:
            self.status_label.setText(f"使用原始数据计算PSD: {data_length} 个数据点")
            progress.setLabelText(f"Computing PSD using {data_length} original data points...")
        
        # 创建并启动工作线程
        self.psd_worker = PSDWorker(
            channel_data, 
            self.file_loader.sampling_rate,
            window,
            nperseg,
            noverlap,
            nfft,
            detrend,
            scaling
        )
        
        # 连接信号
        self.psd_worker.progress.connect(progress.setValue)
        self.psd_worker.finished.connect(lambda result: self.on_psd_computed(
            result, channel_name, window, nfft, normalize, log_x, log_y, exclude_dc, 
            is_db_scale, low_cutoff, high_cutoff, find_peaks_enabled, 
            peak_height, peak_distance, peak_threshold
        ))
        self.psd_worker.error.connect(self.on_psd_error)
        
        # 连接取消按钮
        progress.canceled.connect(self.psd_worker.terminate)
        
        # 启动线程
        self.psd_worker.start()
    
    def on_psd_computed(self, result, channel_name, window_type, nfft, normalize, log_x, log_y, 
                        exclude_dc, is_db_scale, low_cutoff, high_cutoff, find_peaks_enabled, 
                        peak_height, peak_distance, peak_threshold):
        """PSD计算完成回调"""
        # 重新启用计算按钮
        self.compute_psd_button.setEnabled(True)
        self.compute_psd_button.setText("Compute PSD")
        self.status_label.setText("PSD computation completed")
        
        if result is None:
            return
            
        frequencies, psd = result
        
        # 绘制PSD
        plot_type = "dB" if is_db_scale else "raw"
        
        self.psd_visualizer.plot_psd(
            frequencies,
            psd,
            title=f"PSD of {channel_name}",
            normalized=normalize,
            log_x=log_x,
            log_y=log_y,
            exclude_bins=1 if exclude_dc else 0,
            plot_type=plot_type,
            find_peaks_enabled=find_peaks_enabled,
            peak_height=peak_height,
            peak_distance=peak_distance,
            peak_threshold=peak_threshold,
            window_type=window_type,
            nfft=nfft,
            sampling_rate=self.file_loader.sampling_rate,
            low_cutoff=low_cutoff if low_cutoff > 0 else None,
            high_cutoff=high_cutoff if high_cutoff > 0 else None
        )
        
        # 启用导出按钮和添加到比较按钮
        self.export_psd_button.setEnabled(True)
        self.add_to_compare_button.setEnabled(True)
        
        # 切换到分析选项卡
        self.right_panel.setCurrentWidget(self.analysis_tab)
    
    def on_psd_error(self, error_msg):
        """PSD计算错误回调"""
        # 重新启用计算按钮
        self.compute_psd_button.setEnabled(True)
        self.compute_psd_button.setText("Compute PSD")
        self.status_label.setText("PSD computation failed")
        
        QMessageBox.warning(self, "Error", f"Error computing PSD: {error_msg}")
    
    def export_psd(self):
        """导出PSD数据"""
        # 检查是否有PSD数据
        frequencies, psd, normalized, plot_params = self.psd_visualizer.get_current_data()
        if frequencies is None or psd is None:
            QMessageBox.warning(self, "Error", "No PSD data to export")
            return
        
        # 获取当前选择的通道
        channel_name = self.channel_combo.currentText()
        
        # 获取当前设置
        is_db_scale = self.psd_display_combo.currentText() == "dB Scale"
        low_cutoff = self.cutoff_freq_low.value()
        high_cutoff = self.cutoff_freq_high.value()
        
        cutoff_text = ""
        if low_cutoff > 0:
            cutoff_text += f"_low{int(low_cutoff)}"
        if high_cutoff > 0:
            cutoff_text += f"_high{int(high_cutoff)}"
        
        # 获取保存格式选择
        formats = ["CSV (*.csv)", "JSON (*.json)", "NPY Binary (*.npy)"]
        format_buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        msg_box = QMessageBox(QMessageBox.Icon.Question, "Export Format", "Select export format:", format_buttons, self)
        
        # 设置按钮文本
        msg_box.button(QMessageBox.StandardButton.Yes).setText(formats[0])
        msg_box.button(QMessageBox.StandardButton.No).setText(formats[1])
        msg_box.button(QMessageBox.StandardButton.Discard).setText(formats[2])
        
        # 显示对话框
        selected_format = msg_box.exec()
        
        # 检查结果
        ok = selected_format != QMessageBox.StandardButton.Cancel
        
        if not ok:
            return
        
        # 确定选择的格式索引
        if selected_format == QMessageBox.StandardButton.Yes:
            format_idx = 0  # CSV
        elif selected_format == QMessageBox.StandardButton.No:
            format_idx = 1  # JSON
        elif selected_format == QMessageBox.StandardButton.Discard:
            format_idx = 2  # NPY
        else:
            return  # 其他情况，如关闭对话框
        
        # 获取保存路径
        default_name = f"psd_data{cutoff_text}"
        if self.file_loader.file_path:
            base_name = os.path.splitext(os.path.basename(self.file_loader.file_path))[0]
            default_name = f"{base_name}_{channel_name}_psd{cutoff_text}"
        
        if format_idx == 0:  # CSV
            default_name += ".csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export PSD Data", default_name, "CSV Files (*.csv)"
            )
            if not file_path:
                return
            export_psd_to_csv(file_path, frequencies, psd, is_db_scale, normalized, plot_params, self)
        
        elif format_idx == 1:  # JSON
            default_name += ".json"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export PSD Data", default_name, "JSON Files (*.json)"
            )
            if not file_path:
                return
            peak_indices = self.psd_visualizer.current_peak_indices
            export_psd_to_json(file_path, frequencies, psd, is_db_scale, normalized, plot_params, peak_indices, self)
        
        elif format_idx == 2:  # NPY
            default_name += ".npy"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export PSD Data", default_name, "NPY Files (*.npy)"
            )
            if not file_path:
                return
            export_psd_to_npy(file_path, frequencies, psd, plot_params, self)
    
    def save_preset(self):
        """保存PSD参数预设"""
        # 构建预设数据
        preset = {
            "window": self.psd_window_combo.currentText(),
            "nfft": self.psd_nfft_combo.currentText(),
            "nperseg": self.psd_nperseg_combo.currentText(),
            "noverlap": self.psd_noverlap_combo.currentText(),
            "detrend": self.psd_detrend_combo.currentText(),
            "scaling": self.psd_scaling_combo.currentText(),
            "display": self.psd_display_combo.currentText(),
            "low_cutoff": self.cutoff_freq_low.value(),
            "high_cutoff": self.cutoff_freq_high.value(),
            "normalize": self.psd_normalize_check.isChecked(),
            "log_x": self.psd_log_x_check.isChecked(),
            "log_y": self.psd_log_y_check.isChecked(),
            "exclude_dc": self.psd_exclude_dc_check.isChecked(),
            "peak_detection": self.peak_detection.isChecked(),
            "peak_height": self.peak_height_slider.value(),
            "peak_distance": self.peak_distance_spin.value(),
            "peak_threshold": self.peak_threshold_spin.value(),
            "band_selector": self.band_selector_check.isChecked()
        }
        
        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PSD Preset", "psd_preset.json", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
            
        # 保存到文件
        try:
            with open(file_path, 'w') as f:
                json.dump(preset, f, indent=4)
            QMessageBox.information(self, "Success", f"Preset saved to {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error saving preset: {str(e)}")
    
    def load_preset(self):
        """加载PSD参数预设"""
        # 获取加载路径
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load PSD Preset", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
            
        # 从文件加载
        try:
            with open(file_path, 'r') as f:
                preset = json.load(f)
                
            # 应用预设
            if "window" in preset:
                index = self.psd_window_combo.findText(preset["window"])
                if index >= 0:
                    self.psd_window_combo.setCurrentIndex(index)
                    
            if "nfft" in preset:
                index = self.psd_nfft_combo.findText(preset["nfft"])
                if index >= 0:
                    self.psd_nfft_combo.setCurrentIndex(index)
                    
            if "nperseg" in preset:
                index = self.psd_nperseg_combo.findText(preset["nperseg"])
                if index >= 0:
                    self.psd_nperseg_combo.setCurrentIndex(index)
                    
            if "noverlap" in preset:
                index = self.psd_noverlap_combo.findText(preset["noverlap"])
                if index >= 0:
                    self.psd_noverlap_combo.setCurrentIndex(index)
                    
            if "detrend" in preset:
                index = self.psd_detrend_combo.findText(preset["detrend"])
                if index >= 0:
                    self.psd_detrend_combo.setCurrentIndex(index)
                    
            if "scaling" in preset:
                index = self.psd_scaling_combo.findText(preset["scaling"])
                if index >= 0:
                    self.psd_scaling_combo.setCurrentIndex(index)
                    
            if "display" in preset:
                index = self.psd_display_combo.findText(preset["display"])
                if index >= 0:
                    self.psd_display_combo.setCurrentIndex(index)
                    
            if "low_cutoff" in preset:
                self.cutoff_freq_low.setValue(preset["low_cutoff"])
                
            if "high_cutoff" in preset:
                self.cutoff_freq_high.setValue(preset["high_cutoff"])
                
            if "normalize" in preset:
                self.psd_normalize_check.setChecked(preset["normalize"])
                
            if "log_x" in preset:
                self.psd_log_x_check.setChecked(preset["log_x"])
                
            if "log_y" in preset:
                self.psd_log_y_check.setChecked(preset["log_y"])
                
            if "exclude_dc" in preset:
                self.psd_exclude_dc_check.setChecked(preset["exclude_dc"])
                
            # 设置峰值检测
            if "peak_detection" in preset:
                self.peak_detection.setChecked(preset["peak_detection"])
                        
            if "peak_height" in preset:
                self.peak_height_slider.setValue(preset["peak_height"])
                
            if "peak_distance" in preset:
                self.peak_distance_spin.setValue(preset["peak_distance"])
                
            if "peak_threshold" in preset:
                self.peak_threshold_spin.setValue(preset["peak_threshold"])
                
            if "band_selector" in preset:
                self.band_selector_check.setChecked(preset["band_selector"])
                
            QMessageBox.information(self, "Success", f"Preset loaded from {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading preset: {str(e)}")
            traceback.print_exc()

    def recommend_nfft_value(self, channel_name):
        """根据数据长度自动推荐NFFT值"""
        if not self.file_loader.current_data:
            return
        
        channel_data = self.file_loader.get_channel_data(channel_name)
        if channel_data is None:
            return
        
        data_length = len(channel_data)
        recommended_nfft = "4096"  # 默认中等大小
        
        # 根据数据长度选择合适的NFFT
        if data_length < 1000:
            recommended_nfft = "1024"  # 短数据使用小的NFFT
        elif data_length < 10000:
            recommended_nfft = "4096"  # 中等长度数据
        elif data_length < 100000:
            recommended_nfft = "8192"  # 长数据
        else:
            recommended_nfft = "16384"  # 非常长的数据
        
        # 应用推荐值
        current_nfft = self.psd_nfft_combo.currentText()
        if current_nfft != recommended_nfft:
            self.psd_nfft_combo.setCurrentText(recommended_nfft)
            self.status_label.setText(f"自动推荐NFFT: {recommended_nfft} (基于数据长度 {data_length} 点)")
        
        return recommended_nfft
    
    # -------------------- 比较功能相关方法 --------------------
    def add_to_compare(self):
        """将当前PSD添加到比较选项卡"""
        # 获取当前PSD数据
        frequencies, psd, normalized, plot_params = self.psd_visualizer.get_current_data()
        if frequencies is None or psd is None:
            QMessageBox.warning(self, "Error", "No PSD data to add")
            return
        
        # 获取当前选择的通道
        channel_name = self.channel_combo.currentText()
        
        # 获取当前文件路径或名称
        if self.file_loader.file_path:
            file_name = os.path.basename(self.file_loader.file_path)
        else:
            file_name = "Current Data"
        
        # 创建PSD项目的标识信息
        psd_info = {
            "file": file_name,
            "channel": channel_name,
            "nfft": plot_params.get('nfft', "Unknown"),
            "window": plot_params.get('window_type', "Unknown"),
            "sampling_rate": self.file_loader.sampling_rate,
            "frequencies": frequencies,
            "psd": psd,
            "normalized_psd": psd / np.max(psd) if np.max(psd) > 0 else psd  # 预计算归一化值
        }
        
        # 生成唯一ID和显示名称
        psd_id = f"{len(self.compare_data) + 1}"
        psd_name = f"{psd_id}. {file_name} - {channel_name}"
        
        # 为项目分配颜色 (使用循环色系)
        color_idx = len(self.compare_data) % 10  # 循环使用10种颜色
        color = cm.tab10(color_idx)
        psd_info["color"] = color
        
        # 将数据添加到比较数据列表
        self.compare_data.append(psd_info)
        
        # 将项目添加到列表控件
        item = QListWidgetItem(psd_name)
        item.setData(Qt.ItemDataRole.UserRole, psd_id)  # 存储ID以便后续查找
        
        # 设置项目颜色
        item.setForeground(QColor(int(color[0]*255), int(color[1]*255), int(color[2]*255)))
        
        self.psd_list_widget.addItem(item)
        
        # 启用比较控件
        self.clear_compare_button.setEnabled(True)
        
        # 更新比较图表
        self.update_compare_plot()
        
        # 切换到比较选项卡
        self.right_panel.setCurrentWidget(self.compare_tab)
        
        # 显示状态信息
        self.status_label.setText(f"Added PSD of {channel_name} to comparison")
    
    def on_compare_selection_changed(self):
        """处理比较列表选择变化"""
        # 获取选中的项目
        selected_items = self.psd_list_widget.selectedItems()
        
        # 启用/禁用删除选定项目按钮
        self.remove_selected_button.setEnabled(len(selected_items) > 0)
        
        # 更新比较图表，突出显示选中的项目
        self.update_compare_plot()
    
    def clear_all_compare(self):
        """清除所有比较数据"""
        # 清空列表和数据
        self.psd_list_widget.clear()
        self.compare_data = []
        
        # 禁用相关按钮
        self.clear_compare_button.setEnabled(False)
        self.remove_selected_button.setEnabled(False)
        
        # 清空比较图表
        self.update_compare_plot()
        
        # 显示状态信息
        self.status_label.setText("Cleared all comparison data")
    
    def remove_selected_compare(self):
        """删除选中的比较项目"""
        # 获取选中的项目
        selected_items = self.psd_list_widget.selectedItems()
        if not selected_items:
            return
        
        # 获取选中项目的ID
        selected_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # 从列表中删除选中的项目
        for item in selected_items:
            self.psd_list_widget.takeItem(self.psd_list_widget.row(item))
        
        # 从数据中删除相应的PSD
        self.compare_data = [data for data in self.compare_data 
                            if str(data.get("id", "")) not in selected_ids]
        
        # 如果没有剩余数据，禁用清除按钮
        if len(self.compare_data) == 0:
            self.clear_compare_button.setEnabled(False)
        
        # 禁用删除选定项目按钮
        self.remove_selected_button.setEnabled(False)
        
        # 更新比较图表
        self.update_compare_plot()
        
        # 显示状态信息
        self.status_label.setText(f"Removed {len(selected_ids)} item(s) from comparison")
    
    def update_compare_plot(self):
        """更新比较图表"""
        # 清空当前图表
        self.compare_axes.clear()
        
        # 如果没有数据，直接返回
        if not self.compare_data:
            self.compare_canvas.draw()
            return
        
        # 获取显示选项
        normalize = self.normalize_compare_check.isChecked()
        log_x = self.log_x_compare_check.isChecked()
        log_y = self.log_y_compare_check.isChecked()
        
        # 获取选中的项目ID
        selected_items = self.psd_list_widget.selectedItems()
        selected_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # 分组准备数据 - 先绘制未选中的，再绘制选中的（让选中的显示在上层）
        unselected_data = []
        selected_data = []
        
        for i, data in enumerate(self.compare_data):
            psd_id = str(i + 1)  # 构造ID
            
            if psd_id in selected_ids:
                selected_data.append((psd_id, data))
            else:
                unselected_data.append((psd_id, data))
        
        # 先绘制未选中的曲线（低层）
        for psd_id, data in unselected_data:
            frequencies = data["frequencies"]
            
            # 选择要绘制的PSD数据
            if normalize:
                psd = data["normalized_psd"]
            else:
                psd = data["psd"]
            
            # 如果有选中项，未选中的降低不透明度
            alpha = 0.4 if selected_ids else 1.0
            
            # 绘制曲线
            self.compare_axes.plot(
                frequencies, psd,
                color=data["color"],
                linewidth=1.0,
                alpha=alpha,
                label=f"{psd_id}. {data['channel']} ({data['file']})"
            )
        
        # 然后绘制选中的曲线（高层）
        for psd_id, data in selected_data:
            frequencies = data["frequencies"]
            
            # 选择要绘制的PSD数据
            if normalize:
                psd = data["normalized_psd"]
            else:
                psd = data["psd"]
            
            # 绘制选中的曲线，加粗且完全不透明
            self.compare_axes.plot(
                frequencies, psd,
                color=data["color"],
                linewidth=2.5,  # 更粗的线条
                alpha=1.0,      # 完全不透明
                label=f"{psd_id}. {data['channel']} ({data['file']})"
            )
        
        # 设置坐标轴类型
        if log_x:
            self.compare_axes.set_xscale('log')
        else:
            self.compare_axes.set_xscale('linear')
            
        if log_y:
            self.compare_axes.set_yscale('log')
        else:
            self.compare_axes.set_yscale('linear')
        
        # 设置标签和标题
        self.compare_axes.set_xlabel("Frequency (Hz)")
        y_label = "Normalized Power" if normalize else "Power (V²/Hz)"
        self.compare_axes.set_ylabel(y_label)
        self.compare_axes.set_title("PSD Comparison")
        self.compare_axes.grid(True, which="both", ls="-", alpha=0.6)
        
        # 根据复选框状态决定是否显示图例
        if self.show_legend_check.isChecked():
            legend = self.compare_axes.legend(loc='upper right')
            # 设置图例可拖动
            legend.set_draggable(True)
        else:
            # 不显示图例
            if self.compare_axes.get_legend() is not None:
                self.compare_axes.get_legend().remove()
        
        # 使用更紧凑的布局
        self.compare_figure.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.1)
        
        # 重绘图表
        self.compare_canvas.draw()


# 兼容性别名类
H5ViewerDialog = PSDAnalyzerDialog