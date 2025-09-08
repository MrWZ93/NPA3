#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Controller - 直方图控制器
负责协调模型（数据管理器）和视图（对话框）之间的交互
"""

import os
import numpy as np
from .error_handler import ErrorHandler

class HistogramController:
    """直方图控制器，负责协调模型和视图"""
    
    def __init__(self, data_manager, view):
        """初始化控制器
        
        Args:
            data_manager: 数据管理器实例
            view: 视图实例
        """
        self.data_manager = data_manager
        self.view = view
        
        # 连接视图的信号到控制器的方法
        self._connect_signals()
    
    def _connect_signals(self):
        """连接视图的信号"""
        # 文件加载
        self.view.file_channel_control.load_file_btn.clicked.connect(self.load_file)
        
        # 通道选择
        self.view.file_channel_control.channel_changed.connect(self.on_channel_changed)
        
        # 采样率变化
        self.view.file_channel_control.sampling_rate_changed.connect(self.on_sampling_rate_changed)
        
        # 直方图控制信号
        self.view.histogram_control.bins_changed.connect(self.on_bins_changed)
        self.view.histogram_control.highlight_size_changed.connect(self.on_highlight_size_changed)
        self.view.histogram_control.highlight_position_changed.connect(self.on_highlight_position_changed)
        self.view.histogram_control.log_x_changed.connect(self.on_log_x_changed)
        self.view.histogram_control.log_y_changed.connect(self.on_log_y_changed)
        self.view.histogram_control.kde_changed.connect(self.on_kde_changed)
        self.view.histogram_control.invert_data_changed.connect(self.on_invert_data_changed)
        self.view.histogram_control.clear_fits_requested.connect(self.on_clear_fits_requested)
        
        # 连接拟合信息面板的信号
        if hasattr(self.view, 'fit_info_panel'):
            # 注意：这些信号已经在signal_connector.py中连接了，所以这里不再重复连接
            # 避免重复连接导致信号被触发多次
            pass
        
        # 暗色模式和导出功能
        if hasattr(self.view.histogram_control, 'dark_mode_changed'):
            self.view.histogram_control.dark_mode_changed.connect(self.on_dark_mode_changed)
        
        if hasattr(self.view.histogram_control, 'export_image_requested'):
            self.view.histogram_control.export_image_requested.connect(self.export_image)
    
    def load_file(self):
        """加载文件"""
        try:
            # 显示加载中消息
            self.view.status_bar.showMessage("Loading file...")
            
            # 使用数据管理器加载文件
            success, data, info = self.data_manager.load_file()
            
            if not success:
                error_msg = info if isinstance(info, str) else "Failed to load file"
                ErrorHandler.handle_error(
                    self.view,
                    error_msg,
                    "File Loading Error",
                    status_bar=self.view.status_bar
                )
                return
            
            # 更新文件标签
            self.view.file_channel_control.update_file_info(self.data_manager.file_path)
            
            # 更新采样率
            self.view.file_channel_control.set_sampling_rate(self.data_manager.sampling_rate)
            
            # 更新通道列表
            channels = self.data_manager.get_channels()
            self.view.file_channel_control.update_channels(channels)
            
            # 选择第一个通道
            if channels:
                self.data_manager.selected_channel = channels[0]
                self.view.file_channel_control.set_selected_channel(channels[0])
                
                # 获取通道数据并绘制
                self._update_plot(channels[0])
            
            # 文件信息摘要
            if isinstance(info, dict):
                summary = ", ".join([f"{k}: {v}" for k, v in info.items() 
                                if k not in ['File Path', 'Modified Time']])
                self.view.status_bar.showMessage(f"Loaded file: {os.path.basename(self.data_manager.file_path)} - {summary}")
            else:
                self.view.status_bar.showMessage(f"Loaded file: {os.path.basename(self.data_manager.file_path)}")
            
        except Exception as e:
            ErrorHandler.handle_error(
                self.view,
                e,
                "File Loading Error",
                status_bar=self.view.status_bar
            )
    
    def _update_plot(self, channel_name=None):
        """更新绘图，使用当前设置"""
        try:
            # 获取通道数据
            channel_data = self.data_manager.get_channel_data(channel_name)
            
            if channel_data is None:
                self.view.status_bar.showMessage(f"Error: No data for channel {channel_name}")
                return
            
            # 获取文件名作为标题
            file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
            
            # 获取当前显示设置
            bins = self.view.histogram_control.get_bins()
            log_x = self.view.histogram_control.log_x_check.isChecked()
            log_y = self.view.histogram_control.log_y_check.isChecked()
            show_kde = self.view.histogram_control.kde_check.isChecked()
            invert_data = self.view.histogram_control.invert_data_check.isChecked()
            
            # 绘制数据
            self.view.plot_canvas.plot_data(
                channel_data, 
                self.data_manager.sampling_rate,
                bins,
                log_x=log_x,
                log_y=log_y,
                show_kde=show_kde,
                invert_data=invert_data,
                file_name=file_name
            )
            
            # 更新统计信息
            self._update_statistics(channel_data)
            
            if channel_name:
                self.view.status_bar.showMessage(f"Selected channel: {channel_name}")
                
        except Exception as e:
            ErrorHandler.handle_error(
                self.view,
                e,
                "Plot Update Error",
                status_bar=self.view.status_bar
            )
    
    def _update_statistics(self, data):
        """更新数据统计信息"""
        if data is None or len(data) == 0:
            return
            
        # 计算基本统计量
        try:
            stats_info = {
                "Count": len(data),
                "Min": np.min(data),
                "Max": np.max(data),
                "Mean": np.mean(data),
                "Median": np.median(data),
                "Std Dev": np.std(data)
            }
            
            # 更新统计信息显示
            if hasattr(self.view, 'update_statistics_display'):
                self.view.update_statistics_display(stats_info)
            
        except Exception as e:
            print(f"Error calculating statistics: {e}")
    
    def _update_highlighted_statistics(self):
        """更新高亮区域的统计信息"""
        if not hasattr(self.view.plot_canvas, 'data') or self.view.plot_canvas.data is None:
            return
            
        # 获取高亮区域数据
        highlight_min = self.view.plot_canvas.highlight_min
        highlight_max = self.view.plot_canvas.highlight_max
        data = self.view.plot_canvas.data
        
        # 应用数据取反设置
        highlighted_data = -data[highlight_min:highlight_max] if self.view.plot_canvas.invert_data else data[highlight_min:highlight_max]
        
        # 更新统计信息
        self._update_statistics(highlighted_data)
    
    def on_channel_changed(self, channel_name):
        """处理通道选择变化"""
        if not channel_name or channel_name == "Select a channel":
            return
            
        self._update_plot(channel_name)
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变化"""
        self.data_manager.sampling_rate = value
        self._update_plot()
    
    def on_bins_changed(self, bins):
        """处理直方图箱数变化"""
        self.view.plot_canvas.update_bins(bins)
        
        # 如果当前有数据，更新统计信息
        channel_data = self.data_manager.get_channel_data()
        if channel_data is not None:
            self._update_statistics(channel_data)
    
    def on_highlight_size_changed(self, size_percent):
        """处理高亮区域大小变化"""
        self.view.plot_canvas.update_highlight_size(size_percent)
        
        # 更新高亮区域的统计信息
        self._update_highlighted_statistics()
        
        # 清除拟合数据（因为高亮区域变化了）
        self.view._clear_shared_fits_on_data_change()
        
        # 更新subplot3直方图
        self._update_subplot3_histogram(restore_fits=False)
    
    def on_highlight_position_changed(self, position_percent):
        """处理高亮区域位置变化"""
        if hasattr(self.view.plot_canvas, 'move_highlight'):
            self.view.plot_canvas.move_highlight(position_percent)
        else:
            # 如果move_highlight方法不存在，使用update_highlight_position
            if hasattr(self.view.plot_canvas, 'update_highlight_position'):
                self.view.plot_canvas.update_highlight_position(position_percent)
        
        # 更新高亮区域的统计信息
        self._update_highlighted_statistics()
        
        # 清除拟合数据（因为高亮区域变化了）
        self.view._clear_shared_fits_on_data_change()
        
        # 更新subplot3直方图
        self._update_subplot3_histogram(restore_fits=False)
    
    def on_log_x_changed(self, enabled):
        """处理X轴对数显示变化"""
        self.view.plot_canvas.set_log_x(enabled)
        # 更新subplot3直方图
        self._update_subplot3_histogram(restore_fits=False)
        self.view.status_bar.showMessage(f"X-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_log_y_changed(self, enabled):
        """处理Y轴对数显示变化"""
        self.view.plot_canvas.set_log_y(enabled)
        # 更新subplot3直方图
        self._update_subplot3_histogram(restore_fits=False)
        self.view.status_bar.showMessage(f"Y-axis logarithmic scale: {'enabled' if enabled else 'disabled'}")
    
    def on_kde_changed(self, enabled):
        """处理KDE曲线显示变化"""
        self.view.plot_canvas.set_kde(enabled)
        # 更新subplot3直方图
        self._update_subplot3_histogram(restore_fits=False)
        self.view.status_bar.showMessage(f"Kernel Density Estimation: {'enabled' if enabled else 'disabled'}")
    
    def on_invert_data_changed(self, enabled):
        """处理数据取反变化"""
        self.view.plot_canvas.set_invert_data(enabled)
        # 注意：set_invert_data会完全重绘，所以不需要单独更新subplot3
        self.view.status_bar.showMessage(f"Data inversion: {'enabled' if enabled else 'disabled'}")
    
    def on_dark_mode_changed(self, enabled):
        """处理暗色模式变化"""
        if hasattr(self.view.plot_canvas, 'set_dark_mode'):
            self.view.plot_canvas.set_dark_mode(enabled)
            self.view.status_bar.showMessage(f"Dark mode: {'enabled' if enabled else 'disabled'}")
    
    def export_image(self):
        """导出当前图像"""
        from PyQt6.QtWidgets import QFileDialog
        
        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Export Image",
            "",
            "PNG Files (*.png);;JPEG Files (*.jpg);;PDF Files (*.pdf);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 保存图像
            if hasattr(self.view.plot_canvas, 'save_figure'):
                success = self.view.plot_canvas.save_figure(file_path)
                
                if success:
                    self.view.status_bar.showMessage(f"Image exported to {file_path}")
                else:
                    self.view.status_bar.showMessage("Failed to export image")
            else:
                self.view.status_bar.showMessage("Image export not supported")
                
        except Exception as e:
            ErrorHandler.handle_error(
                self.view,
                e,
                "Export Error",
                status_bar=self.view.status_bar
            )
    
    def _update_subplot3_histogram(self, restore_fits=False):
        """更新subplot3直方图视图"""
        if not hasattr(self.view, 'subplot3_canvas') or self.view.subplot3_canvas is None:
            return
            
        if not hasattr(self.view.plot_canvas, 'data') or self.view.plot_canvas.data is None:
            return
        
        try:
            # 获取当前的高亮数据（从subplot3）
            highlight_min = self.view.plot_canvas.highlight_min
            highlight_max = self.view.plot_canvas.highlight_max
            data = self.view.plot_canvas.data
            
            # 应用数据取反设置
            highlighted_data = -data[highlight_min:highlight_max] if self.view.plot_canvas.invert_data else data[highlight_min:highlight_max]
            
            if len(highlighted_data) == 0:
                return
            
            # 获取当前显示设置
            bins = self.view.histogram_control.get_bins()
            log_x = self.view.histogram_control.log_x_check.isChecked()
            log_y = self.view.histogram_control.log_y_check.isChecked()
            show_kde = self.view.histogram_control.kde_check.isChecked()
            
            # 获取文件名作为标题
            file_name = os.path.basename(self.data_manager.file_path) if self.data_manager.file_path else ""
            
            # 在subplot3_canvas中创建直方图视图
            self.view.subplot3_canvas.plot_subplot3_histogram(
                highlighted_data,
                bins=bins,
                log_x=log_x,
                log_y=log_y,
                show_kde=show_kde,
                file_name=file_name
            )
            
        except Exception as e:
            ErrorHandler.handle_error(
                self.view,
                e,
                "Subplot3 Histogram Update Error",
                status_bar=self.view.status_bar
            )
    
    def on_tab_changed(self, index):
        """处理标签页切换"""
        if index == 1:  # 切换到直方图标签页
            # 确保subplot3直方图是最新的，并且恢复拟合曲线
            self._update_subplot3_histogram(restore_fits=True)
            # 显示提示信息
            self.view.status_bar.showMessage("Histogram view: Click and drag to select regions for Gaussian fitting")
    
    def on_clear_fits_requested(self):
        """处理清除高斯拟合请求 - 增强版"""
        print("[Controller] Starting comprehensive fit clearing...")
        
        # 清除subplot3_canvas中的拟合
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'clear_fits'):
            self.view.subplot3_canvas.clear_fits()
            
        # 清除共享拟合数据
        if hasattr(self.view, 'shared_fit_data') and self.view.shared_fit_data:
            self.view.shared_fit_data.clear_fits()
            
        # 强制清除Fit Results面板
        try:
            if hasattr(self.view, 'fit_info_panel') and self.view.fit_info_panel is not None:
                print("[Controller] Force clearing fit_info_panel")
                # 直接清空列表
                self.view.fit_info_panel.fit_list.clear()
                # 调用正式的清除方法
                self.view.fit_info_panel.clear_all_fits()
                print("[Controller] Successfully force cleared fit info panel")
        except Exception as e:
            print(f"[Controller] Error force clearing fit_info_panel: {e}")
            
        # 调用视图的综合清除方法
        if hasattr(self.view, '_clear_shared_fits_on_data_change'):
            self.view._clear_shared_fits_on_data_change()
            
        self.view.status_bar.showMessage("Cleared all Gaussian fits")
        print("[Controller] Comprehensive fit clearing completed")
            
    def on_fit_selected(self, fit_index):
        """处理拟合项被选中"""
        # 在当前活动的画布中高亮显示拟合曲线
        current_canvas = self.view.get_current_canvas()
        if hasattr(current_canvas, 'highlight_fit'):
            current_canvas.highlight_fit(fit_index)
            
        # 也在subplot3_canvas中高亮显示（如果存在）
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'highlight_fit'):
            self.view.subplot3_canvas.highlight_fit(fit_index)
            
        if fit_index > 0:
            self.view.status_bar.showMessage(f"Selected fit {fit_index}")
        else:
            self.view.status_bar.showMessage("No fit selected")
            
    def on_fit_deleted(self, fit_index):
        """处理单个拟合项被删除"""
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'delete_specific_fit'):
            success = self.view.subplot3_canvas.delete_specific_fit(fit_index)
            if success:
                self.view.status_bar.showMessage(f"Deleted fit {fit_index}")
            
    def on_fits_deleted(self, fit_indices):
        """处理多个拟合项被删除"""
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'delete_specific_fit'):
            # 从大到小排序索引，以避免删除早期项时影响后续项的索引
            for fit_index in sorted(fit_indices, reverse=True):
                self.view.subplot3_canvas.delete_specific_fit(fit_index)
            
            self.view.status_bar.showMessage(f"Deleted {len(fit_indices)} fits")
            
    def on_fit_edited(self, fit_index, new_params):
        """处理拟合项被编辑"""
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'update_specific_fit'):
            success = self.view.subplot3_canvas.update_specific_fit(fit_index, new_params)
            if success:
                self.view.status_bar.showMessage(f"Updated fit {fit_index}")
                
    def on_toggle_fit_labels(self, visible):
        """切换拟合标签的可见性"""
        if hasattr(self.view, 'subplot3_canvas') and hasattr(self.view.subplot3_canvas, 'toggle_fit_labels'):
            self.view.subplot3_canvas.toggle_fit_labels(visible)
            status = "visible" if visible else "hidden"
            self.view.status_bar.showMessage(f"Fit labels are now {status}")
