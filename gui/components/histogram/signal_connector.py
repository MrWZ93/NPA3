#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Connector - 信号连接器
专门负责信号和槽的连接管理
"""

from PyQt6.QtWidgets import QMessageBox


class HistogramSignalConnector:
    """直方图信号连接器"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self._connecting = False
    
    def connect_all_signals(self):
        """连接所有信号"""
        if self._connecting:
            return
        
        try:
            self._connecting = True
            
            # 文件和数据信号
            self._connect_file_signals()
            
            # 直方图控制信号
            self._connect_histogram_control_signals()
            
            # 标签页切换信号
            self._connect_tab_signals()
            
            # 导出工具信号
            self._connect_export_signals()
            
            # 拟合相关信号
            self._connect_fit_signals()
            
            # Cursor相关信号
            self._connect_cursor_signals()
            
            # Plot canvas信号
            self._connect_plot_signals()
            
        except Exception as e:
            print(f"Error connecting signals: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._connecting = False
    
    def _connect_file_signals(self):
        """连接文件相关信号"""
        # 文件加载
        self.dialog.file_channel_control.load_file_btn.clicked.connect(
            self.dialog.load_file
        )
        
        # 通道选择变化
        self.dialog.file_channel_control.channel_changed.connect(
            self.dialog.on_channel_changed
        )
        
        # 采样率变化
        self.dialog.file_channel_control.sampling_rate_changed.connect(
            self.dialog.on_sampling_rate_changed
        )
    
    def _connect_histogram_control_signals(self):
        """连接直方图控制信号"""
        # 基础控制信号
        self.dialog.histogram_control.bins_changed.connect(
            self.dialog.on_bins_changed
        )
        self.dialog.histogram_control.highlight_size_changed.connect(
            self.dialog.on_highlight_size_changed
        )
        self.dialog.histogram_control.highlight_position_changed.connect(
            self.dialog.on_highlight_position_changed
        )
        
        # 显示选项信号
        self.dialog.histogram_control.log_x_changed.connect(
            self.dialog.on_log_x_changed
        )
        self.dialog.histogram_control.log_y_changed.connect(
            self.dialog.on_log_y_changed
        )
        self.dialog.histogram_control.kde_changed.connect(
            self.dialog.on_kde_changed
        )
        self.dialog.histogram_control.invert_data_changed.connect(
            self.dialog.on_invert_data_changed
        )
        
        # 清除拟合信号
        if hasattr(self.dialog.histogram_control, 'clear_fits_requested'):
            self.dialog.histogram_control.clear_fits_requested.connect(
                self.dialog.on_clear_fits_requested
            )
    
    def _connect_tab_signals(self):
        """连接标签页信号"""
        self.dialog.tab_widget.currentChanged.connect(
            self.dialog.on_tab_changed
        )
    
    def _connect_export_signals(self):
        """连接导出工具信号"""
        # 综合导出
        self.dialog.export_tools.export_comprehensive_requested.connect(
            self.dialog.on_export_comprehensive
        )
        
        # 图像复制
        self.dialog.export_tools.copy_image_requested.connect(
            self.dialog.on_copy_images
        )
    
    def _connect_fit_signals(self):
        """连接拟合相关信号"""
        # Clear All按钮
        self.dialog.clear_all_btn.clicked.connect(
            self.dialog.on_clear_fits_requested
        )
        
        # 拟合信息面板信号
        self.dialog.fit_info_panel.fit_deleted.connect(
            self.dialog.on_fit_deleted
        )
        self.dialog.fit_info_panel.fits_deleted.connect(
            self.dialog.on_fits_deleted
        )
        self.dialog.fit_info_panel.fit_edited.connect(
            self.dialog.on_fit_edited
        )
        self.dialog.fit_info_panel.fit_selected.connect(
            self.dialog.on_fit_selected
        )
        self.dialog.fit_info_panel.copy_all_fits.connect(
            self.dialog.on_copy_fit_info
        )
        self.dialog.fit_info_panel.toggle_fit_labels.connect(
            self.dialog.on_toggle_fit_labels
        )
    
    def _connect_cursor_signals(self):
        """连接Cursor相关信号"""
        # Cursor信息面板信号
        self.dialog.cursor_info_panel.add_cursor_requested.connect(
            self.dialog.add_cursor
        )
        self.dialog.cursor_info_panel.clear_cursors_requested.connect(
            self.dialog.clear_cursors
        )
        self.dialog.cursor_info_panel.cursor_selected.connect(
            self.dialog.select_cursor
        )
        self.dialog.cursor_info_panel.cursor_deleted.connect(
            self.dialog.delete_cursor
        )
        self.dialog.cursor_info_panel.cursors_deleted.connect(
            self.dialog.delete_cursors
        )
        self.dialog.cursor_info_panel.cursor_position_changed.connect(
            self.dialog.update_cursor_position
        )
        
        # Popup Cursor管理器信号（如果使用的话）
        if hasattr(self.dialog, 'popup_cursor_manager'):
            self.dialog.popup_cursor_manager.cursor_position_changed.connect(
                self.dialog.on_cursor_position_changed
            )
            self.dialog.popup_cursor_manager.cursor_selection_changed.connect(
                self.dialog.on_cursor_selection_changed
            )
    
    def _connect_plot_signals(self):
        """连接绘图相关信号"""
        # 主视图canvas信号
        if hasattr(self.dialog.plot_canvas, 'cursor_selected'):
            try:
                self.dialog.plot_canvas.cursor_selected.disconnect()
            except:
                pass
            self.dialog.plot_canvas.cursor_selected.connect(
                self.dialog.on_plot_cursor_selected
            )
        
        if hasattr(self.dialog.plot_canvas, 'region_selected'):
            try:
                self.dialog.plot_canvas.region_selected.disconnect()
            except:
                pass
            self.dialog.plot_canvas.region_selected.connect(
                self.dialog.on_region_selected
            )
        
        # subplot3 canvas信号
        if hasattr(self.dialog.subplot3_canvas, 'cursor_selected'):
            try:
                self.dialog.subplot3_canvas.cursor_selected.disconnect()
            except:
                pass
            self.dialog.subplot3_canvas.cursor_selected.connect(
                self.dialog.on_plot_cursor_selected
            )
    
    def disconnect_all_signals(self):
        """断开所有信号连接"""
        try:
            # 这里可以添加信号断开逻辑，如果需要的话
            pass
        except Exception as e:
            print(f"Error disconnecting signals: {e}")


class DialogEventHandler:
    """对话框事件处理器"""
    
    def __init__(self, dialog):
        self.dialog = dialog
    
    def show_error_message(self, title, message):
        """显示错误消息"""
        QMessageBox.critical(self.dialog, title, message)
    
    def show_info_message(self, title, message):
        """显示信息消息"""
        QMessageBox.information(self.dialog, title, message)
    
    def show_warning_message(self, title, message):
        """显示警告消息"""
        QMessageBox.warning(self.dialog, title, message)
    
    def ask_confirmation(self, title, message):
        """询问确认"""
        reply = QMessageBox.question(
            self.dialog, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def update_status(self, message):
        """更新状态栏"""
        if hasattr(self.dialog, 'status_bar'):
            self.dialog.status_bar.showMessage(message)
