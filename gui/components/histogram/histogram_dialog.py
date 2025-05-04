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
from .export_tools import ExportToolsPanel, HistogramExporter
from .fit_info_panel import FitInfoPanel


class HistogramDialog(QDialog):
    """直方图分析对话框"""
    
    def __init__(self, parent=None):
        super(HistogramDialog, self).__init__(parent)
        self.setWindowTitle("Histogram Analysis")
        self.resize(1000, 800)  # 设置初始大小
        
        # 初始化数据管理器
        self.data_manager = HistogramDataManager(self)
        
        # 初始化导出器
        self.exporter = HistogramExporter(self)
        
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
        
        # 创建导出工具面板
        self.export_tools = ExportToolsPanel(self)
        
        # 添加到顶部布局
        top_layout.addWidget(self.file_channel_control)
        top_layout.addWidget(self.histogram_control)
        top_layout.addWidget(self.export_tools)
        
        # ================ 中间区域：绘图区 ================
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 主视图标签页
        self.main_tab = QWidget()
        main_tab_layout = QVBoxLayout(self.main_tab)
        main_tab_layout.setContentsMargins(5, 0, 5, 0)  # 减小左右边距
        
        # 创建主视图绘图区
        self.plot_canvas = HistogramPlot(self, width=8, height=6, dpi=100)
        self.plot_toolbar = NavigationToolbar(self.plot_canvas, self)
        
        # 将绘图区添加到主视图标签页
        main_tab_layout.addWidget(self.plot_toolbar)
        main_tab_layout.addWidget(self.plot_canvas)
        
        # Subplot3直方图标签页
        self.subplot3_tab = QWidget()
        subplot3_tab_layout = QHBoxLayout(self.subplot3_tab)  # 使用水平布局来并排直方图和信息面板
        subplot3_tab_layout.setContentsMargins(5, 0, 5, 0)  # 减小左右边距
        
        # 创建一个拆分器来管理直方图和信息面板的布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 直方图区域
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)  # 减小内边距
        
        # 创建 subplot3 直方图绘图区
        self.subplot3_canvas = HistogramPlot(self, width=8, height=6, dpi=100)
        self.subplot3_toolbar = NavigationToolbar(self.subplot3_canvas, self)
        
        # 将绘图区添加到直方图容器
        plot_layout.addWidget(self.subplot3_toolbar)
        plot_layout.addWidget(self.subplot3_canvas)
        
        # 信息面板区域
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(5, 0, 0, 0)  # 减小内边距
        
        # 创建拟合信息面板
        self.fit_info_panel = FitInfoPanel(self)
        info_layout.addWidget(self.fit_info_panel)
        
        # 调试信息
        print("Fit info panel created")
        
        # 添加到拆分器
        splitter.addWidget(plot_container)
        splitter.addWidget(info_container)
        
        # 设置拆分器初始比例 (70% 直方图, 30% 信息面板)
        splitter.setSizes([700, 300])
        
        # 将拆分器添加到标签页布局
        subplot3_tab_layout.addWidget(splitter)
        
        # 添加标签页到标签页控件
        self.tab_widget.addTab(self.main_tab, "Main View")
        self.tab_widget.addTab(self.subplot3_tab, "Histogram")
        
        # ================ 状态栏 ================
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        
        # ================ 将各部分添加到主布局 ================
        self.main_layout.addWidget(top_widget)
        self.main_layout.addWidget(self.tab_widget, 1)  # 标签页控件占大部分空间
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
        self.histogram_control.clear_fits_requested.connect(self.on_clear_fits_requested)
        
        # 标签页切换
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # 导出工具信号
        self.export_tools.export_histogram_requested.connect(self.on_export_histogram)
        self.export_tools.copy_fit_info_requested.connect(self.on_copy_fit_info)
        
        # 拟合信息面板信号
        self.fit_info_panel.fit_deleted.connect(self.on_fit_deleted)
        self.fit_info_panel.fits_deleted.connect(self.on_fits_deleted)
        self.fit_info_panel.fit_edited.connect(self.on_fit_edited)
        self.fit_info_panel.fit_selected.connect(self.on_fit_selected)
        self.fit_info_panel.export_all_fits.connect(self.on_export_histogram)
        self.fit_info_panel.copy_all_fits.connect(self.on_copy_fit_info)
        self.fit_info_panel.toggle_fit_labels.connect(self.on_toggle_fit_labels)
    
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
                    
                    # 绘制主视图
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
                    
                    # 绘制subplot3直方图
                    self.update_subplot3_histogram()
            
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
    
    def update_subplot3_histogram(self):
        """更新subplot3直方图"""
        if not hasattr(self.plot_canvas, 'data') or self.plot_canvas.data is None:
            return
        
        # 获取当前的高亮数据（从subplot3）
        highlight_min = self.plot_canvas.highlight_min
        highlight_max = self.plot_canvas.highlight_max
        data = self.plot_canvas.data
        
        # 应用数据取反设置
        highlighted_data = -data[highlight_min:highlight_max] if self.plot_canvas.invert_data else data[highlight_min:highlight_max]
        
        if len(highlighted_data) == 0:
            return
        
        # 在subplot3_canvas中创建直方图视图
        self.subplot3_canvas.plot_subplot3_histogram(
            highlighted_data,
            bins=self.histogram_control.get_bins(),
            log_x=self.histogram_control.log_x_check.isChecked(),
            log_y=self.histogram_control.log_y_check.isChecked(),
            show_kde=self.histogram_control.kde_check.isChecked(),
            file_name=os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
        )
        
        # 清除拟合信息面板
        self.fit_info_panel.clear_all_fits()
        
        # 设置subplot3_canvas的parent_dialog父组件为自己，这样可以访问fit_info_panel
        self.subplot3_canvas.parent_dialog = self
        print(f"Setting parent_dialog for subplot3_canvas: {self}")
    
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
                
                # 绘制主视图
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
                
                # 绘制subplot3直方图
                self.update_subplot3_histogram()
        
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
            
            # 更新subplot3直方图
            self.update_subplot3_histogram()
            
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
            
            # 更新subplot3直方图
            self.update_subplot3_histogram()
    
    def on_bins_changed(self, bins):
        """处理直方图箱数变化"""
        self.plot_canvas.update_bins(bins)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
    
    def on_highlight_size_changed(self, size_percent):
        """处理高亮区域大小变化"""
        self.plot_canvas.update_highlight_size(size_percent)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
    
    def on_highlight_position_changed(self, position_percent):
        """处理高亮区域位置变化"""
        self.plot_canvas.move_highlight(position_percent)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
    
    def on_log_x_changed(self, enabled):
        """处理X轴对数显示变化"""
        self.plot_canvas.set_log_x(enabled)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
        self.status_bar.showMessage(f"X-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_log_y_changed(self, enabled):
        """处理Y轴对数显示变化"""
        self.plot_canvas.set_log_y(enabled)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
        self.status_bar.showMessage(f"Y-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_kde_changed(self, enabled):
        """处理KDE曲线显示变化"""
        self.plot_canvas.set_kde(enabled)
        # 更新subplot3直方图
        self.update_subplot3_histogram()
        self.status_bar.showMessage(f"Kernel Density Estimation: {'enabled' if enabled else 'disabled'}")
    
    def on_invert_data_changed(self, enabled):
        """处理数据取反变化"""
        self.plot_canvas.set_invert_data(enabled)
        # 更新subplot3直方图（需要在set_invert_data完成后调用）
        # 注意：set_invert_data会完全重绘，所以不需要单独更新subplot3
        self.status_bar.showMessage(f"Data inversion: {'enabled' if enabled else 'disabled'}")
    
    def on_tab_changed(self, index):
        """处理标签页切换"""
        if index == 1:  # 切换到直方图标签页
            # 确保subplot3直方图是最新的
            self.update_subplot3_histogram()
            # 显示提示信息
            self.status_bar.showMessage("Histogram view: Click and drag to select regions for Gaussian fitting")
    
    def on_clear_fits_requested(self):
        """处理清除高斯拟合请求"""
        if hasattr(self.subplot3_canvas, 'clear_fits'):
            self.subplot3_canvas.clear_fits()
            self.status_bar.showMessage("Cleared all Gaussian fits")
    
    def on_export_histogram(self):
        """处理导出直方图数据请求"""
        try:
            # 检查是否在直方图标签页
            is_histogram_tab = self.tab_widget.currentIndex() == 1
            
            if is_histogram_tab and hasattr(self.subplot3_canvas, 'histogram_data'):
                # 获取当前直方图数据
                data = self.subplot3_canvas.histogram_data
                bins = self.subplot3_canvas.histogram_bins
                counts = self.subplot3_canvas.hist_counts
                bin_edges = self.subplot3_canvas.hist_bin_edges
                
                # 导出数据
                success, message = self.exporter.export_histogram_data(
                    data, bins, counts, bin_edges, self.data_manager.file_path
                )
                
                if success:
                    self.status_bar.showMessage(f"Histogram data exported to: {message}")
                else:
                    self.status_bar.showMessage(f"Export failed: {message}")
                    
            elif hasattr(self.plot_canvas, 'data'):
                # 使用主视图的高亮区域数据
                data = self.plot_canvas.data[self.plot_canvas.highlight_min:self.plot_canvas.highlight_max]
                if self.plot_canvas.invert_data:
                    data = -data
                    
                # 创建临时直方图数据
                hist_result = np.histogram(data, bins=self.histogram_control.get_bins())
                counts = hist_result[0]
                bin_edges = hist_result[1]
                
                # 导出数据
                success, message = self.exporter.export_histogram_data(
                    data, self.histogram_control.get_bins(), counts, bin_edges, self.data_manager.file_path
                )
                
                if success:
                    self.status_bar.showMessage(f"Histogram data exported to: {message}")
                else:
                    self.status_bar.showMessage(f"Export failed: {message}")
            else:
                self.status_bar.showMessage("No data to export")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error exporting data: {str(e)}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Error exporting histogram data: {str(e)}"
            )
    
    def on_copy_fit_info(self):
        """处理复制拟合信息请求"""
        try:
            if self.tab_widget.currentIndex() == 1 and hasattr(self.subplot3_canvas, 'fit_info_str'):
                # 复制拟合信息到剪贴板
                success, message = self.exporter.copy_fit_info_to_clipboard(
                    self.subplot3_canvas.fit_info_str
                )
                
                if success:
                    self.status_bar.showMessage(message)
                else:
                    self.status_bar.showMessage(f"Copy failed: {message}")
            else:
                self.status_bar.showMessage("No fit information available. Please select regions for Gaussian fitting first.")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error copying data: {str(e)}")
            QMessageBox.critical(
                self,
                "Copy Error",
                f"Error copying fit information: {str(e)}"
            )
    
    def on_fit_deleted(self, fit_index):
        """处理删除拟合项目请求"""
        try:
            if hasattr(self.subplot3_canvas, 'delete_specific_fit'):
                # 先从拟合信息面板删除
                self.fit_info_panel.remove_fit(fit_index)
                # 再从图中删除
                self.subplot3_canvas.delete_specific_fit(fit_index)
                self.status_bar.showMessage(f"Deleted fit {fit_index}")
        except Exception as e:
            self.status_bar.showMessage(f"Error deleting fit: {str(e)}")
    
    def on_fit_edited(self, fit_index, new_params):
        """处理编辑拟合参数请求"""
        try:
            if hasattr(self.subplot3_canvas, 'update_specific_fit'):
                self.subplot3_canvas.update_specific_fit(fit_index, new_params)
                self.status_bar.showMessage(f"Updated fit {fit_index}")
        except Exception as e:
            self.status_bar.showMessage(f"Error updating fit: {str(e)}")
    
    def on_fit_selected(self, fit_index):
        """处理选中拟合项目请求"""
        try:
            if hasattr(self.subplot3_canvas, 'highlight_specific_fit'):
                self.subplot3_canvas.highlight_specific_fit(fit_index)
                self.status_bar.showMessage(f"Selected fit {fit_index}")
        except Exception as e:
            self.status_bar.showMessage(f"Error selecting fit: {str(e)}")
    
    def on_fits_deleted(self, fit_indices):
        """处理删除多个拟合项请求"""
        try:
            if hasattr(self.subplot3_canvas, 'delete_specific_fit'):
                # 从大到小排序索引，以避免删除早期项时影响后续项的索引
                for fit_index in sorted(fit_indices, reverse=True):
                    # 先从技师信息面板删除
                    self.fit_info_panel.remove_fit(fit_index)
                    # 再从图中删除
                    self.subplot3_canvas.delete_specific_fit(fit_index)
                
                self.status_bar.showMessage(f"Deleted {len(fit_indices)} fits")
        except Exception as e:
            self.status_bar.showMessage(f"Error deleting fits: {str(e)}")
    
    def on_toggle_fit_labels(self, visible):
        """处理切换拟合标签可见性请求"""
        try:
            if hasattr(self.subplot3_canvas, 'toggle_fit_labels'):
                self.subplot3_canvas.toggle_fit_labels(visible)
                status = "visible" if visible else "hidden"
                self.status_bar.showMessage(f"Fit labels are now {status}")
        except Exception as e:
            self.status_bar.showMessage(f"Error toggling fit labels: {str(e)}")
