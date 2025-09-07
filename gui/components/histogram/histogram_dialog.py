#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Dialog - 重构版直方图分析对话框
采用模块化设计，简化UI布局，提升用户体验
"""

import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# 导入模块化组件
from .data_manager import HistogramDataManager
from .histogram_plot import FitDataManager
from .ui_builder import HistogramUIBuilder
from .signal_connector import HistogramSignalConnector, DialogEventHandler
from .histogram_controller import HistogramController
from .export_tools import IntegratedDataExporter, ImageClipboardManager, HistogramExporter
from .popup_cursor_manager import PopupCursorManager
from .dialog_config import DialogConfig, UITexts


class HistogramDialog(QDialog):
    """重构版直方图分析对话框 - 简洁高效的模块化设计"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_dialog()
        self._initialize_components()
        self._build_interface()
        self._connect_signals()
        
    def _setup_dialog(self):
        """初始化对话框基本设置"""
        self.setWindowTitle(DialogConfig.WINDOW_TITLE)
        self.setWindowIcon(QIcon(DialogConfig.WINDOW_ICON))  # 可以替换为实际图标路径
        self.resize(*DialogConfig.INITIAL_SIZE)
        self.setMinimumSize(*DialogConfig.MINIMUM_SIZE)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(*DialogConfig.MAIN_MARGINS)
        self.main_layout.setSpacing(DialogConfig.MAIN_SPACING)
        
    def _initialize_components(self):
        """初始化核心组件"""
        # 数据管理
        self.data_manager = HistogramDataManager(self)
        self.shared_fit_data = FitDataManager()
        
        # 导出器
        self.exporter = HistogramExporter(self)
        self.integrated_exporter = IntegratedDataExporter(self)
        
        # 事件处理器
        self.event_handler = DialogEventHandler(self)
        
        # 状态标志
        self.fit_curves_visible = True
        self._updating_subplot3 = False
        self._changing_tab = False
        self._handling_cursor_selection = False
        
    def _build_interface(self):
        """构建用户界面"""
        # 使用UI构建器创建界面
        self.ui_builder = HistogramUIBuilder(self)
        self.main_splitter = self.ui_builder.build_main_layout()
        
        # 初始化弹窗cursor管理器
        self.popup_cursor_manager = PopupCursorManager(self)
        self.popup_cursor_manager.hide()
        
        # 设置画布的共享拟合数据
        self.plot_canvas.set_shared_fit_data(self.shared_fit_data)
        self.subplot3_canvas.set_shared_fit_data(self.shared_fit_data)
        
    def _connect_signals(self):
        """连接信号和槽"""
        # 创建控制器（会自动连接大部分信号）
        self.controller = HistogramController(self.data_manager, self)
        
        # 使用信号连接器连接剩余信号
        self.signal_connector = HistogramSignalConnector(self)
        self.signal_connector.connect_all_signals()
        
        # 连接标签页切换信号到控制器
        self.tab_widget.currentChanged.connect(self.controller.on_tab_changed)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # 初始化cursor manager与plot canvas的关联
        self.popup_cursor_manager.set_plot_widget(self.plot_canvas)
    
    # ================ 核心业务方法 ================
    
    def load_file(self):
        """文件加载（委托给控制器）"""
        self.controller.load_file()
        
    def set_data(self, data, sampling_rate=None):
        """设置数据（外部调用接口）"""
        self.data_manager.set_data(data, sampling_rate)
        self.file_channel_control.set_sampling_rate(self.data_manager.sampling_rate)
        
        channels = self.data_manager.get_channels()
        self.file_channel_control.update_channels(channels)
        
        if channels:
            self.controller._update_plot(channels[0])
        
        self.status_bar.showMessage("Data loaded successfully")
    
    def get_current_canvas(self):
        """获取当前活动的画布"""
        return self.subplot3_canvas if self.tab_widget.currentIndex() == 1 else self.plot_canvas
    
    # ================ 事件处理方法 ================
    
    def on_channel_changed(self, channel_name):
        """通道变化处理（委托给控制器）"""
        self.controller.on_channel_changed(channel_name)
    
    def on_sampling_rate_changed(self, value):
        """采样率变化处理（委托给控制器）"""
        self.controller.on_sampling_rate_changed(value)
    
    def on_bins_changed(self, bins):
        """直方图箱数变化处理"""
        self.controller.on_bins_changed(bins)
        self._update_subplot3_histogram()
    
    def on_highlight_size_changed(self, size_percent):
        """高亮区域大小变化处理"""
        self.controller.on_highlight_size_changed(size_percent)
        self._clear_shared_fits_on_data_change()
    
    def on_highlight_position_changed(self, position_percent):
        """高亮区域位置变化处理"""
        self.controller.on_highlight_position_changed(position_percent)
        self._clear_shared_fits_on_data_change()
    
    def on_log_x_changed(self, enabled):
        """X轴对数变化处理"""
        self.controller.on_log_x_changed(enabled)
    
    def on_log_y_changed(self, enabled):
        """Y轴对数变化处理"""
        self.controller.on_log_y_changed(enabled)
        # 检查是否被禁用
        if enabled and not self.plot_canvas.log_y:
            self.histogram_control.log_y_check.setChecked(False)
            self.status_bar.showMessage("Y-axis log scale disabled: histogram contains zero counts")
    
    def on_kde_changed(self, enabled):
        """KDE变化处理"""
        self.controller.on_kde_changed(enabled)
    
    def on_invert_data_changed(self, enabled):
        """数据取反变化处理"""
        self.controller.on_invert_data_changed(enabled)
    
    def on_tab_changed(self, index):
        """标签页切换处理 - 优化版"""
        if self._changing_tab:
            return
            
        try:
            self._changing_tab = True
            
            if index == 1:  # 直方图标签页
                self._update_subplot3_histogram()
                self._sync_cursor_manager_to_canvas(self.subplot3_canvas)
                self.status_bar.showMessage(DialogConfig.STATUS_MESSAGES['histogram_view'])
                
            elif index == 0:  # 主视图标签页
                self._sync_cursor_manager_to_canvas(self.plot_canvas)
                self.status_bar.showMessage(DialogConfig.STATUS_MESSAGES['main_view'])
                
            self.update_cursor_info_panel()
                
        except Exception as e:
            print(f"Error in tab change: {e}")
        finally:
            self._changing_tab = False
    
    def on_clear_fits_requested(self):
        """清除拟合请求处理"""
        self.controller.on_clear_fits_requested()
        self.shared_fit_data.clear_fits()
    
    def on_region_selected(self, x_min, x_max):
        """区域选择处理"""
        try:
            if hasattr(self.plot_canvas, 'update_highlighted_plots'):
                self.plot_canvas.update_highlighted_plots()
            
            self._clear_shared_fits_on_data_change()
            self._update_subplot3_histogram()
            
            self.status_bar.showMessage(f"Region selected: {x_min:.3f} to {x_max:.3f}")
            
        except Exception as e:
            print(f"Error handling region selection: {e}")
    
    # ================ 拟合相关方法 ================
    
    def on_fit_deleted(self, fit_index):
        """单个拟合删除处理"""
        self.controller.on_fit_deleted(fit_index)
    
    def on_fits_deleted(self, fit_indices):
        """批量拟合删除处理"""
        self.controller.on_fits_deleted(fit_indices)
    
    def on_fit_edited(self, fit_index, new_params):
        """拟合编辑处理"""
        self.controller.on_fit_edited(fit_index, new_params)
    
    def on_fit_selected(self, fit_index):
        """拟合选择处理"""
        self.controller.on_fit_selected(fit_index)
    
    def on_copy_fit_info(self):
        """复制拟合信息处理"""
        try:
            if self.tab_widget.currentIndex() == 1 and hasattr(self.subplot3_canvas, 'fit_info_str'):
                success, message = self.exporter.copy_fit_info_to_clipboard(
                    self.subplot3_canvas.fit_info_str
                )
                self.status_bar.showMessage(message if success else f"Copy failed: {message}")
            else:
                self.status_bar.showMessage("No fit information available")
        except Exception as e:
            self.event_handler.show_error_message("Copy Error", f"Error copying fit information: {str(e)}")
    
    def on_toggle_fit_labels(self, visible):
        """切换拟合标签可见性"""
        self.controller.on_toggle_fit_labels(visible)
    
    # ================ Cursor相关方法 ================
    
    def add_cursor(self):
        """添加cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'add_cursor'):
                cursor_id = canvas.add_cursor()
                if cursor_id is not None:
                    self.status_bar.showMessage(f"Added cursor {cursor_id}")
                    self.update_cursor_info_panel()
                else:
                    self.status_bar.showMessage("Failed to add cursor")
        except Exception as e:
            self.status_bar.showMessage(f"Error adding cursor: {str(e)}")
    
    def clear_cursors(self):
        """清除所有cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'clear_all_cursors'):
                success = canvas.clear_all_cursors()
                if success:
                    self.status_bar.showMessage("Cleared all cursors")
                    self.cursor_info_panel.clear_all_cursors()
        except Exception as e:
            self.status_bar.showMessage(f"Error clearing cursors: {str(e)}")
    
    def update_cursor_info_panel(self):
        """更新cursor信息面板"""
        try:
            canvas = self.get_current_canvas()
            if canvas and hasattr(canvas, 'get_cursor_info'):
                cursor_info = canvas.get_cursor_info()
                self.cursor_info_panel.refresh_cursor_list(cursor_info)
        except Exception as e:
            print(f"Error updating cursor info panel: {e}")
    
    def delete_cursor(self, cursor_id):
        """删除指定cursor"""
        canvas = self.get_current_canvas()
        if hasattr(canvas, 'remove_cursor') and canvas.remove_cursor(cursor_id):
            self.status_bar.showMessage(f"Deleted cursor {cursor_id}")
            self.update_cursor_info_panel()
    
    def delete_cursors(self, cursor_ids):
        """删除多个cursor"""
        canvas = self.get_current_canvas()
        if hasattr(canvas, 'remove_cursor'):
            success_count = sum(1 for cursor_id in cursor_ids if canvas.remove_cursor(cursor_id))
            self.status_bar.showMessage(f"Deleted {success_count} cursors")
            self.update_cursor_info_panel()
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新cursor位置"""
        canvas = self.get_current_canvas()
        if hasattr(canvas, 'update_cursor_position') and canvas.update_cursor_position(cursor_id, new_position):
            canvas.draw()
            self.update_cursor_info_panel()
    
    def select_cursor(self, cursor_id):
        """选择cursor"""
        canvas = self.get_current_canvas()
        if hasattr(canvas, 'select_cursor'):
            canvas.select_cursor(cursor_id if cursor_id >= 0 else None)
            self.update_cursor_info_panel()
    
    def on_cursor_position_changed(self, cursor_id, new_position):
        """Cursor位置变化处理"""
        self.status_bar.showMessage(f"Cursor {cursor_id} moved to Y = {new_position:.4f}")
        self.update_cursor_info_panel()
        
    def on_cursor_selection_changed(self, cursor_id):
        """Cursor选择变化处理"""
        status = f"Selected cursor {cursor_id}" if cursor_id >= 0 else "No cursor selected"
        self.status_bar.showMessage(status)
        self.update_cursor_info_panel()
    
    def on_plot_cursor_selected(self, cursor_id):
        """绘图区cursor选择处理"""
        if self._handling_cursor_selection:
            return
            
        try:
            self._handling_cursor_selection = True
            
            if self.popup_cursor_manager.isVisible():
                self.popup_cursor_manager.update_from_plot()
            
            self.update_cursor_info_panel()
            
            status = f"Selected cursor {cursor_id} from plot" if cursor_id is not None and cursor_id >= 0 else "Cursor selection cleared from plot"
            self.status_bar.showMessage(status)
                
        except Exception as e:
            print(f"Error handling plot cursor selection: {e}")
        finally:
            self._handling_cursor_selection = False
    
    # ================ 导出相关方法 ================
    
    def on_export_comprehensive(self):
        """综合导出处理"""
        try:
            success, message = self.integrated_exporter.export_comprehensive_data()
            
            if success:
                self.status_bar.showMessage("Export completed successfully")
                self.event_handler.show_info_message("Export Complete", message)
            else:
                self.status_bar.showMessage(f"Export failed: {message}")
                if "cancelled" not in message.lower():
                    self.event_handler.show_warning_message("Export Failed", message)
                    
        except Exception as e:
            error_msg = f"Error during comprehensive export: {str(e)}"
            self.status_bar.showMessage(error_msg)
            self.event_handler.show_error_message("Export Error", error_msg)
    
    def on_copy_images(self):
        """图像复制处理"""
        try:
            if not hasattr(self, 'plot_canvas') or not hasattr(self, 'subplot3_canvas'):
                self.status_bar.showMessage("No images available to copy")
                return
            
            success, message = ImageClipboardManager.copy_combined_images_to_clipboard(
                self.plot_canvas, self.subplot3_canvas
            )
            
            if success:
                self.status_bar.showMessage("Images copied to clipboard successfully")
            else:
                self.status_bar.showMessage(f"Failed to copy images: {message}")
                self.event_handler.show_warning_message("Copy Failed", f"Failed to copy images to clipboard:\n{message}")
                
        except Exception as e:
            error_msg = f"Error copying images: {str(e)}"
            self.status_bar.showMessage(error_msg)
            self.event_handler.show_error_message("Copy Error", error_msg)
    
    # ================ 工具方法 ================
    
    def _update_subplot3_histogram(self):
        """更新subplot3直方图 - 简化版"""
        if self._updating_subplot3 or not hasattr(self.plot_canvas, 'data') or self.plot_canvas.data is None:
            return
        
        try:
            self._updating_subplot3 = True
            self.controller._update_subplot3_histogram()
            
            # 设置subplot3_canvas的parent_dialog
            self.subplot3_canvas.parent_dialog = self
            
            # 在Histogram标签页时更新cursor manager关联
            if self.tab_widget.currentIndex() == 1:
                self._sync_cursor_manager_to_canvas(self.subplot3_canvas)
                
        except Exception as e:
            print(f"Error updating subplot3 histogram: {e}")
        finally:
            self._updating_subplot3 = False
    
    def _clear_shared_fits_on_data_change(self):
        """数据变化时清除共享拟合数据"""
        if self.shared_fit_data.has_fits():
            print("Clearing shared fit data due to data region change")
            self.shared_fit_data.clear_fits()
    
    def _sync_cursor_manager_to_canvas(self, canvas):
        """同步cursor manager到指定画布"""
        if self.popup_cursor_manager.isVisible():
            self.popup_cursor_manager.set_plot_widget(canvas)
    
    def toggle_cursor_manager(self):
        """切换cursor manager显示"""
        if self.popup_cursor_manager.isVisible():
            self.popup_cursor_manager.hide()
        else:
            canvas = self.get_current_canvas()
            self.popup_cursor_manager.set_plot_widget(canvas)
            self.popup_cursor_manager.show_popup()
            
            # 强制激活
            self.popup_cursor_manager.raise_()
            self.popup_cursor_manager.activateWindow()
            self.popup_cursor_manager.setFocus()
    
    def toggle_fit_display(self):
        """切换拟合曲线显示"""
        try:
            self.fit_curves_visible = not self.fit_curves_visible
            
            if hasattr(self.plot_canvas, '_ax3_fit_lines') and self.plot_canvas._ax3_fit_lines:
                for line in self.plot_canvas._ax3_fit_lines:
                    if line and hasattr(line, 'set_visible'):
                        line.set_visible(self.fit_curves_visible)
                
                self.plot_canvas.draw()
                status = "visible" if self.fit_curves_visible else "hidden"
                self.status_bar.showMessage(f"Fit curves in main view are now {status}")
            else:
                self.status_bar.showMessage("No fit curves to toggle in main view")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error toggling fit display: {str(e)}")
