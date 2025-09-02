#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Controls - 直方图控制面板
提供直方图分析的控制界面元素
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QSpinBox, QSlider, QFormLayout, QGroupBox,
                           QPushButton, QDoubleSpinBox, QComboBox, QCheckBox,
                           QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class HistogramControlPanel(QWidget):
    """直方图控制面板"""
    
    # 定义信号
    bins_changed = pyqtSignal(int)
    highlight_size_changed = pyqtSignal(int)
    highlight_position_changed = pyqtSignal(int)
    log_x_changed = pyqtSignal(bool)
    log_y_changed = pyqtSignal(bool)
    kde_changed = pyqtSignal(bool)
    invert_data_changed = pyqtSignal(bool)
    clear_fits_requested = pyqtSignal()  # 清除高斯拟合信号
    
    def __init__(self, parent=None):
        super(HistogramControlPanel, self).__init__(parent)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距使布局更紧凑
        
        # 初始化延时定时器，用于滑块优化
        self.size_timer = QTimer(self)
        self.size_timer.setSingleShot(True)
        self.size_timer.setInterval(50)  # 50ms的延迟
        
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.setInterval(50)  # 50ms的延迟
        
        # 保存当前值
        self.current_size = 10
        self.current_position = 5
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI组件"""
        # 直方图设置组
        hist_group = QGroupBox("Histogram Settings")
        hist_layout = QVBoxLayout(hist_group)
        hist_layout.setContentsMargins(5, 5, 5, 5)  # 减小内边距
        
        # 上部区域：箱数和复选框并排
        top_layout = QHBoxLayout()
        
        # 箱数控制
        bins_layout = QHBoxLayout()
        bins_layout.addWidget(QLabel("Bins:"))
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(5, 500)
        self.bins_spin.setValue(200)
        self.bins_spin.setSingleStep(5)
        bins_layout.addWidget(self.bins_spin)
        
        # 添加显示选项 - 水平排列
        options_layout = QHBoxLayout()
        
        # X轴对数显示
        self.log_x_check = QCheckBox("Log X")
        self.log_x_check.setToolTip("Display the histogram X-axis using logarithmic scale")
        self.log_x_check.setChecked(False)  # 默认不勾选
        
        # Y轴对数显示
        self.log_y_check = QCheckBox("Log Y")
        self.log_y_check.setToolTip("Display the histogram Y-axis using logarithmic scale")
        self.log_y_check.setChecked(False)  # 默认不勾选
        
        # KDE显示
        self.kde_check = QCheckBox("KDE")
        self.kde_check.setToolTip("Overlay a kernel density estimation curve on the histogram")
        self.kde_check.setChecked(False)  # 默认不勾选
        
        # 数据取反
        self.invert_data_check = QCheckBox("Invert")
        self.invert_data_check.setToolTip("Invert the data values (multiply by -1)")
        self.invert_data_check.setChecked(False)  # 默认不勾选
        
        # 清除高斯拟合按钮
        self.clear_fits_btn = QPushButton("Clear Fits")
        self.clear_fits_btn.setToolTip("Clear all Gaussian fits")
        self.clear_fits_btn.setFixedWidth(80)
        
        # 添加所有选项到布局
        top_layout.addLayout(bins_layout)
        top_layout.addStretch(1)  # 添加弹性空间使复选框靠右
        top_layout.addWidget(self.log_x_check)
        top_layout.addWidget(self.log_y_check)
        top_layout.addWidget(self.kde_check)
        top_layout.addWidget(self.invert_data_check)
        top_layout.addWidget(self.clear_fits_btn)
        
        hist_layout.addLayout(top_layout)
        
        # 高亮区域设置
        highlight_layout = QVBoxLayout()
        
        # 高亮区域大小设置
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.highlight_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_size_slider.setRange(1, 100)  # 1-100% 范围
        self.highlight_size_slider.setValue(10)  # 默认10%
        self.highlight_size_slider.setTracking(True)  # 实时跟踪滑块位置
        self.highlight_size_label = QLabel("10%")
        size_layout.addWidget(self.highlight_size_slider)
        size_layout.addWidget(self.highlight_size_label)
        
        # 高亮区域位置设置
        position_layout = QHBoxLayout()
        position_layout.addWidget(QLabel("Position:"))
        self.highlight_position_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_position_slider.setRange(0, 100)  # 0-100% 范围
        self.highlight_position_slider.setValue(5)  # 默认位于数据开始附近
        self.highlight_position_slider.setTracking(True)  # 实时跟踪滑块位置
        self.highlight_position_label = QLabel("5%")
        position_layout.addWidget(self.highlight_position_slider)
        position_layout.addWidget(self.highlight_position_label)
        
        # 将控件添加到高亮区域布局
        highlight_layout.addLayout(size_layout)
        highlight_layout.addLayout(position_layout)
        
        # 添加高亮区域布局到直方图设置组
        hist_layout.addLayout(highlight_layout)
        
        # 添加直方图设置组到主布局
        self.main_layout.addWidget(hist_group)
        self.main_layout.addStretch(1)  # 添加弹性空间，让控件靠上排列
    
    def connect_signals(self):
        """连接信号与槽"""
        # 直方图箱数变化
        self.bins_spin.valueChanged.connect(self.bins_changed)
        
        # 高亮区域大小变化 - 使用延时优化
        self.highlight_size_slider.valueChanged.connect(self.on_size_slider_moved)
        self.size_timer.timeout.connect(self.emit_size_changed)
        
        # 高亮区域位置变化 - 使用延时优化
        self.highlight_position_slider.valueChanged.connect(self.on_position_slider_moved)
        self.position_timer.timeout.connect(self.emit_position_changed)
        
        # 对数轴和KDE选项
        self.log_x_check.stateChanged.connect(self.on_log_x_changed)
        self.log_y_check.stateChanged.connect(self.on_log_y_changed)
        self.kde_check.stateChanged.connect(self.on_kde_changed)
        
        # 数据取反选项
        self.invert_data_check.stateChanged.connect(self.on_invert_data_changed)
        
        # 清除高斯拟合按钮
        self.clear_fits_btn.clicked.connect(self.on_clear_fits_clicked)
    
    def on_size_slider_moved(self, value):
        """处理滑块移动事件并使用延时优化"""
        self.highlight_size_label.setText(f"{value}%")
        self.current_size = value
        # 重新启动定时器，让用户停止移动滑块后才发送信号
        self.size_timer.start()
    
    def emit_size_changed(self):
        """定时器超时后发送信号"""
        self.highlight_size_changed.emit(self.current_size)
    
    def on_position_slider_moved(self, value):
        """处理滑块移动事件并使用延时优化"""
        self.highlight_position_label.setText(f"{value}%")
        self.current_position = value
        # 重新启动定时器，让用户停止移动滑块后才发送信号
        self.position_timer.start()
    
    def emit_position_changed(self):
        """定时器超时后发送信号"""
        self.highlight_position_changed.emit(self.current_position)
    
    def on_log_x_changed(self, state):
        """处理X轴对数显示变化"""
        self.log_x_changed.emit(state == Qt.CheckState.Checked.value)
    
    def on_log_y_changed(self, state):
        """处理Y轴对数显示变化"""
        self.log_y_changed.emit(state == Qt.CheckState.Checked.value)
    
    def on_kde_changed(self, state):
        """处理KDE显示变化"""
        self.kde_changed.emit(state == Qt.CheckState.Checked.value)
    
    def on_invert_data_changed(self, state):
        """处理数据取反变化"""
        self.invert_data_changed.emit(state == Qt.CheckState.Checked.value)
    
    def get_bins(self):
        """获取直方图箱数"""
        return self.bins_spin.value()
    
    def get_highlight_size(self):
        """获取高亮区域大小百分比"""
        return self.highlight_size_slider.value()
    
    def get_highlight_position(self):
        """获取高亮区域位置百分比"""
        return self.highlight_position_slider.value()
    
    def set_bins(self, value):
        """设置直方图箱数"""
        self.bins_spin.setValue(value)
    
    def set_highlight_size(self, value):
        """设置高亮区域大小百分比"""
        self.highlight_size_slider.setValue(value)
    
    def set_highlight_position(self, value):
        """设置高亮区域位置百分比"""
        self.highlight_position_slider.setValue(value)
        
    def on_clear_fits_clicked(self):
        """处理清除高斯拟合按钮点击"""
        self.clear_fits_requested.emit()


class FileChannelControl(QWidget):
    """文件和通道控制面板"""
    
    # 定义信号
    file_loaded = pyqtSignal(str, dict)  # 文件路径, 文件信息
    channel_changed = pyqtSignal(str)    # 通道名称
    sampling_rate_changed = pyqtSignal(float)  # 采样率
    
    def __init__(self, parent=None):
        super(FileChannelControl, self).__init__(parent)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距使布局更紧凑
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI组件"""
        # 文件选择组
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(5, 5, 5, 5)  # 减小内边距
        
        # 文件选择按钮和标签
        file_select_layout = QHBoxLayout()
        self.load_file_btn = QPushButton("Load File")
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: gray; font-style: italic;")
        file_select_layout.addWidget(self.load_file_btn)
        file_select_layout.addWidget(self.file_label, 1)
        
        # 通道和采样率水平布局
        channel_rate_layout = QHBoxLayout()
        
        # 通道选择
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("Select a channel")
        self.channel_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        channel_layout.addWidget(self.channel_combo)
        
        # 采样率设置
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Rate (Hz):"))
        self.sampling_rate_spin = QDoubleSpinBox()
        self.sampling_rate_spin.setRange(1, 1000000)
        self.sampling_rate_spin.setValue(1000.0)
        self.sampling_rate_spin.setDecimals(1)
        self.sampling_rate_spin.setSingleStep(100)
        self.sampling_rate_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rate_layout.addWidget(self.sampling_rate_spin)
        
        # 添加通道和采样率到水平布局
        channel_rate_layout.addLayout(channel_layout)
        channel_rate_layout.addLayout(rate_layout)
        
        # 将所有布局添加到文件组
        file_layout.addLayout(file_select_layout)
        file_layout.addLayout(channel_rate_layout)
        
        # 添加到主布局
        self.main_layout.addWidget(file_group)
        self.main_layout.addStretch(1)  # 添加弹性空间，让控件靠上排列
    
    def connect_signals(self):
        """连接信号与槽"""
        # 文件加载按钮
        self.load_file_btn.clicked.connect(self.on_load_file_clicked)
        
        # 通道选择变化
        self.channel_combo.currentTextChanged.connect(self.on_channel_changed)
        
        # 采样率变化
        self.sampling_rate_spin.valueChanged.connect(self.on_sampling_rate_changed)
    
    def on_load_file_clicked(self):
        """处理文件加载按钮点击"""
        # 这个方法实际上是作为一个接口暴露出去的
        # 具体的文件加载逻辑将在主对话框中实现
        # 当按钮被点击时，主对话框会通过连接此信号来处理
        # 在此只发出一个假的信号用于测试
        self.file_loaded.emit("", {})
    
    def on_channel_changed(self, channel_name):
        """处理通道变更"""
        if channel_name and channel_name != "Select a channel":
            self.channel_changed.emit(channel_name)
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变更"""
        self.sampling_rate_changed.emit(value)
    
    def update_file_info(self, file_path, show_name=True):
        """更新文件信息显示"""
        if show_name and file_path:
            import os
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setStyleSheet("color: black; font-style: normal;")
            self.file_label.setToolTip(file_path)
        else:
            self.file_label.setText("No file selected")
            self.file_label.setStyleSheet("color: gray; font-style: italic;")
            self.file_label.setToolTip("")
    
    def update_channels(self, channels):
        """更新通道列表"""
        self.channel_combo.clear()
        
        if not channels:
            self.channel_combo.addItem("Select a channel")
            return
        
        for channel in channels:
            self.channel_combo.addItem(str(channel))
    
    def set_sampling_rate(self, rate):
        """设置采样率"""
        if rate > 0:
            self.sampling_rate_spin.setValue(rate)
    
    def get_sampling_rate(self):
        """获取采样率"""
        return self.sampling_rate_spin.value()
    
    def get_selected_channel(self):
        """获取选择的通道名称"""
        return self.channel_combo.currentText()
    
    def set_selected_channel(self, channel_name):
        """设置选择的通道"""
        index = self.channel_combo.findText(channel_name)
        if index >= 0:
            self.channel_combo.setCurrentIndex(index)
