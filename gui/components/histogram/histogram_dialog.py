#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Dialog - 直方图分析对话框
用于分析和可视化数据的直方图
"""

import os
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTabWidget, QFileDialog, QMessageBox, QGroupBox, 
                            QStatusBar, QWidget, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

# 导入自定义模块
from .histogram_plot import HistogramPlot
from .data_manager import HistogramDataManager
from .controls import HistogramControlPanel, FileChannelControl


class HistogramDialog(QDialog):
    """直方图分析对话框"""
    
    def __init__(self, parent=None):
        super(HistogramDialog, self).__init__(parent)
        self.setWindowTitle("Histogram Analysis")
        self.resize(1000, 800)  # 设置初始大小
        
        # 初始化数据管理器
        self.data_manager = HistogramDataManager(self)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        
        # 设置界面
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置用户界面"""
        # ================ 顶部区域：控制面板 ================
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        
        # 创建文件和通道控制面板
        self.file_channel_control = FileChannelControl(self)
        
        # 创建直方图控制面板
        self.histogram_control = HistogramControlPanel(self)
        
        # 添加到顶部布局
        top_layout.addWidget(self.file_channel_control)
        top_layout.addWidget(self.histogram_control)
        
        # ================ 中间区域：绘图区 ================
        # 创建绘图区
        self.plot_canvas = HistogramPlot(self, width=8, height=6, dpi=100)
        self.plot_toolbar = NavigationToolbar(self.plot_canvas, self)
        
        # 将绘图区添加到布局
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(5, 0, 5, 0)  # 减小左右边距
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
        self.file_channel_control.load_file_btn.clicked.connect(self.load_file)
        
        # 通道选择
        self.file_channel_control.channel_changed.connect(self.on_channel_changed)
        
        # 采样率变化
        self.file_channel_control.sampling_rate_changed.connect(self.on_sampling_rate_changed)
        
        # 直方图控制信号
        self.histogram_control.bins_changed.connect(self.on_bins_changed)
        self.histogram_control.highlight_size_changed.connect(self.on_highlight_size_changed)
        self.histogram_control.highlight_position_changed.connect(self.on_highlight_position_changed)
        self.histogram_control.log_x_changed.connect(self.on_log_x_changed)
        self.histogram_control.log_y_changed.connect(self.on_log_y_changed)
        self.histogram_control.kde_changed.connect(self.on_kde_changed)
        self.histogram_control.invert_data_changed.connect(self.on_invert_data_changed)
    
    def load_file(self):
        """加载文件"""
        try:
            # 显示加载中消息
            self.status_bar.showMessage("Loading file...")
            
            # 使用数据管理器加载文件
            success, data, info = self.data_manager.load_file()
            
            if not success:
                error_msg = info if isinstance(info, str) else "Failed to load file"
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load file: {error_msg}"
                )
                self.status_bar.showMessage(f"Error: {error_msg}")
                return
            
            # 更新文件标签
            self.file_channel_control.update_file_info(self.data_manager.file_path)
            
            # 更新采样率
            self.file_channel_control.set_sampling_rate(self.data_manager.sampling_rate)
            
            # 更新通道列表
            channels = self.data_manager.get_channels()
            self.file_channel_control.update_channels(channels)
            
            # 选择第一个通道
            if channels:
                self.data_manager.selected_channel = channels[0]
                self.file_channel_control.set_selected_channel(channels[0])
                
                # 获取通道数据并绘制
                channel_data = self.data_manager.get_channel_data()
                if channel_data is not None:
                    # 获取文件名作为标题
                    file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
                    
                    self.plot_canvas.plot_data(
                        channel_data, 
                        self.data_manager.sampling_rate,
                        self.histogram_control.get_bins(),
                        log_x=False,  # 默认不启用X轴对数
                        log_y=False,  # 默认不启用Y轴对数
                        show_kde=True,   # 默认启用KDE
                        invert_data=False,  # 默认不取反数据
                        file_name=file_name
                    )
            
            # 文件信息摘要
            if isinstance(info, dict):
                summary = ", ".join([f"{k}: {v}" for k, v in info.items() 
                                if k not in ['File Path', 'Modified Time']])
                self.status_bar.showMessage(f"Loaded file: {os.path.basename(self.data_manager.file_path)} - {summary}")
            else:
                self.status_bar.showMessage(f"Loaded file: {os.path.basename(self.data_manager.file_path)}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error loading file: {str(e)}"
            )
            self.status_bar.showMessage(f"Error loading file: {str(e)}")
            print(f"Error in load_file: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def set_data(self, data, sampling_rate=None):
        """设置数据（外部调用）"""
        # 使用数据管理器设置数据
        self.data_manager.set_data(data, sampling_rate)
        
        # 更新采样率控制
        self.file_channel_control.set_sampling_rate(self.data_manager.sampling_rate)
        
        # 更新通道列表
        channels = self.data_manager.get_channels()
        self.file_channel_control.update_channels(channels)
        
        # 选择第一个通道并绘制
        if channels:
            channel_data = self.data_manager.get_channel_data(channels[0])
            if channel_data is not None:
                # 获取文件名作为标题
                file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
                
                self.plot_canvas.plot_data(
                    channel_data, 
                    self.data_manager.sampling_rate,
                    self.histogram_control.get_bins(),
                    log_x=False,  # 默认不启用X轴对数
                    log_y=False,  # 默认不启用Y轴对数
                    show_kde=True,   # 默认启用KDE
                    invert_data=False,  # 默认不取反数据
                    file_name=file_name
                )
        
        self.status_bar.showMessage("Data loaded")
    
    def on_channel_changed(self, channel_name):
        """处理通道选择变化"""
        if not channel_name or channel_name == "Select a channel":
            return
            
        try:
            # 获取通道数据
            channel_data = self.data_manager.get_channel_data(channel_name)
            
            if channel_data is None:
                self.status_bar.showMessage(f"Error: No data for channel {channel_name}")
                return
            
            # 获取文件名作为标题
            file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
            
            # 绘制数据
            self.plot_canvas.plot_data(
                channel_data, 
                self.data_manager.sampling_rate,
                self.histogram_control.get_bins(),
                log_x=self.histogram_control.log_x_check.isChecked(),
                log_y=self.histogram_control.log_y_check.isChecked(),
                show_kde=self.histogram_control.kde_check.isChecked(),
                invert_data=self.histogram_control.invert_data_check.isChecked(),
                file_name=file_name
            )
            
            self.status_bar.showMessage(f"Selected channel: {channel_name}")
            
        except Exception as e:
            self.status_bar.showMessage(f"Error during channel change: {str(e)}")
            print(f"Error in on_channel_changed: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变化"""
        self.data_manager.sampling_rate = value
        
        # 获取文件名作为标题
        file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
        
        # 如果有当前数据，重新绘制
        channel_data = self.data_manager.get_channel_data()
        if channel_data is not None:
            self.plot_canvas.plot_data(
                channel_data, 
                value,
                self.histogram_control.get_bins(),
                log_x=self.histogram_control.log_x_check.isChecked(),
                log_y=self.histogram_control.log_y_check.isChecked(),
                show_kde=self.histogram_control.kde_check.isChecked(),
                invert_data=self.histogram_control.invert_data_check.isChecked(),
                file_name=file_name
            )
    
    def on_bins_changed(self, bins):
        """处理直方图箱数变化"""
        self.plot_canvas.update_bins(bins)
    
    def on_highlight_size_changed(self, size_percent):
        """处理高亮区域大小变化"""
        self.plot_canvas.update_highlight_size(size_percent)
    
    def on_highlight_position_changed(self, position_percent):
        """处理高亮区域位置变化"""
        self.plot_canvas.move_highlight(position_percent)
    
    def on_log_x_changed(self, enabled):
        """处理X轴对数显示变化"""
        self.plot_canvas.set_log_x(enabled)
        self.status_bar.showMessage(f"X-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_log_y_changed(self, enabled):
        """处理Y轴对数显示变化"""
        self.plot_canvas.set_log_y(enabled)
        self.status_bar.showMessage(f"Y-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_kde_changed(self, enabled):
        """处理KDE曲线显示变化"""
        self.plot_canvas.set_kde(enabled)
        self.status_bar.showMessage(f"Kernel Density Estimation: {'enabled' if enabled else 'disabled'}")
    
    def on_invert_data_changed(self, enabled):
        """处理数据取反变化"""
        self.plot_canvas.set_invert_data(enabled)
        self.status_bar.showMessage(f"Data inversion: {'enabled' if enabled else 'disabled'}")
