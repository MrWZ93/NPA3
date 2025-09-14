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
# from .popup_cursor_manager import PopupCursorManager  # 不再需要，功能已集成到cursor_info_panel
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
        
        # 初始化弹窗cursor管理器 - 不再需要，功能已集成到cursor_info_panel
        # self.popup_cursor_manager = PopupCursorManager(self)
        # self.popup_cursor_manager.hide()
        
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
        
        # 初始化cursor manager与plot canvas的关联 - 不再需要
        # self.popup_cursor_manager.set_plot_widget(self.plot_canvas)
        
        # 连接cursor可见性切换信号
        if hasattr(self, 'cursor_info_panel'):
            self.cursor_info_panel.toggle_cursors_visibility_requested.connect(self.on_toggle_cursors_visibility)
        
        # 关键新增：连接cursor位置更新信号到本对话框的处理方法
        if hasattr(self, 'plot_canvas') and hasattr(self.plot_canvas, 'cursor_position_updated'):
            self.plot_canvas.cursor_position_updated.connect(self.on_cursor_position_updated)
        if hasattr(self, 'subplot3_canvas') and hasattr(self.subplot3_canvas, 'cursor_position_updated'):
            self.subplot3_canvas.cursor_position_updated.connect(self.on_cursor_position_updated)
    
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
        self._update_subplot3_histogram(restore_fits=False)
    
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
        """标签页切换处理 - 优化版，支持拟合恢复"""
        if self._changing_tab:
            return
            
        try:
            self._changing_tab = True
            
            if index == 1:  # 直方图标签页
                # 切换到直方图时，如果有拟合数据则恢复
                self._update_subplot3_histogram(restore_fits=True)
                self._sync_cursor_manager_to_canvas(self.subplot3_canvas)
                
                # 同步cursor可见性状态到subplot3_canvas
                if hasattr(self.plot_canvas, 'get_cursors_visible') and hasattr(self.subplot3_canvas, 'set_cursors_visible'):
                    visibility = self.plot_canvas.get_cursors_visible()
                    self.subplot3_canvas.set_cursors_visible(visibility)
                    # 更新按钮文本
                    if hasattr(self, 'cursor_info_panel'):
                        self.cursor_info_panel.update_visibility_button_text(visibility)
                    # if hasattr(self.popup_cursor_manager, 'toggle_visibility_btn'):
                    #     self.popup_cursor_manager.toggle_visibility_btn.setText("Hide" if visibility else "Show")
                
                self.status_bar.showMessage(DialogConfig.STATUS_MESSAGES['histogram_view'])
                
                # 在切换到histogram tab后，立即更新cursor info panel
                if hasattr(self, 'cursor_info_panel'):
                    # 调试输出：检查cursor数据是否正确传递
                    current_canvas = self.get_current_canvas()
                    if hasattr(current_canvas, 'cursors'):
                        print(f"[DEBUG] Switching to histogram tab, found {len(current_canvas.cursors)} cursors")
                    
                    # 在histogram tab中禁用Position Control（因为cursor不可见）
                    self.cursor_info_panel.update_position_label_for_tab(is_histogram_tab=True)
                    
                    self.update_cursor_info_panel()
                
            elif index == 0:  # 主视图标签页
                self._sync_cursor_manager_to_canvas(self.plot_canvas)
                
                # 在切换回主视图时，更新subplot3中的拟合显示
                if (hasattr(self, 'plot_canvas') and 
                    hasattr(self.plot_canvas, '_update_ax3_fit_display')):
                    print("Updating Main View subplot3 fit display on tab switch")
                    self.plot_canvas._update_ax3_fit_display()
                    self.plot_canvas.draw()
                
                self.status_bar.showMessage(DialogConfig.STATUS_MESSAGES['main_view'])
                
                # 在切换到主视图后，也更新cursor info panel
                if hasattr(self, 'cursor_info_panel'):
                    # 恢复Position Control的正常功能
                    self.cursor_info_panel.update_position_label_for_tab(is_histogram_tab=False)
                    
                    self.update_cursor_info_panel()
                
            # 不在tab切换时更新cursor info panel，避免不必要的刷新
            # self.update_cursor_info_panel()
                
        except Exception as e:
            print(f"Error in tab change: {e}")
        finally:
            self._changing_tab = False
    
    def on_clear_fits_requested(self):
        """清除拟合请求处理 - 增强版"""
        print("[Dialog] Starting comprehensive fit clearing from clear button...")
        
        # 调用控制器的清除方法
        self.controller.on_clear_fits_requested()
        
        # 直接清除共享拟合数据和UI显示
        if self.shared_fit_data:
            self.shared_fit_data.clear_fits()
            
        # 强制清除Fit Results面板
        try:
            if hasattr(self, 'fit_info_panel') and self.fit_info_panel is not None:
                print("[Dialog] Force clearing fit_info_panel from clear button")
                # 直接清空列表
                self.fit_info_panel.fit_list.clear()
                # 调用正式的清除方法
                self.fit_info_panel.clear_all_fits()
                print("[Dialog] Successfully force cleared fit info panel from clear button")
        except Exception as e:
            print(f"[Dialog] Error force clearing fit_info_panel from clear button: {e}")
            
        # 调用综合清除方法
        self._clear_shared_fits_on_data_change()
        
        print("[Dialog] Comprehensive fit clearing from clear button completed")
    
    def on_region_selected(self, x_min, x_max):
        """区域选择处理"""
        try:
            # 清除拟合数据（因为用户重新选择了高亮区域）
            self._clear_shared_fits_on_data_change()
            
            if hasattr(self.plot_canvas, 'update_highlighted_plots'):
                # 区域选择后更新显示，但不再重复清除拟合
                self.plot_canvas.update_highlighted_plots(clear_fits=False)
            
            self._update_subplot3_histogram(restore_fits=False)
            
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
        """更新cursor信息面板 - 优化版，支持高频更新"""
        try:
            canvas = self.get_current_canvas()
            if canvas and hasattr(canvas, 'get_cursor_info'):
                cursor_info = canvas.get_cursor_info()
                # 在tab切换时强制更新，忽略跳过标志
                force_update = True
                # 使用强制更新模式实现实时更新
                self.cursor_info_panel.refresh_cursor_list(cursor_info, force_update)
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
        """处理Cursor位置变化 - 统一显示Y坐标"""
        # 统一显示Y坐标，因为histogram中不显示cursor
        self.status_bar.showMessage(f"Cursor {cursor_id} moved to Y = {new_position:.4f}")
        self.update_cursor_info_panel()
    
    def on_cursor_position_updated(self, cursor_id, new_position):
        """处理cursor位置实时更新 - 节流优化版"""
        # 节流更新：不要立即更新GUI，等待一段时间再更新
        # 这样可以减少GUI更新的频率，提高拖拽性能
        
        # 直接调用控制器的节流更新方法
        if hasattr(self, 'controller'):
            self.controller.on_cursor_position_updated(cursor_id, new_position)
        else:
            # 如果控制器不可用，直接更新（但这种情况不应该发生）
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
            
            # if self.popup_cursor_manager.isVisible():
            #     self.popup_cursor_manager.update_from_plot()
            
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
    
    def _update_subplot3_histogram(self, restore_fits=True):
        """更新subplot3直方图 - 支持拟合曲线恢复"""
        if self._updating_subplot3 or not hasattr(self.plot_canvas, 'data') or self.plot_canvas.data is None:
            return
        
        try:
            self._updating_subplot3 = True
            
            print(f"Updating subplot3 histogram, restore_fits={restore_fits}")
            
            # 更新直方图
            self.controller._update_subplot3_histogram()
            
            # 设置subplot3_canvas的parent_dialog
            self.subplot3_canvas.parent_dialog = self
            
            # 根据参数决定是否恢复拟合数据
            if restore_fits and hasattr(self, 'shared_fit_data') and self.shared_fit_data and self.shared_fit_data.has_fits():
                print(f"Restoring {len(self.shared_fit_data.gaussian_fits)} fits to subplot3")
                # 延迟恢复拟合，确保直方图已经绘制完成
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, self._restore_fits_to_subplot3)
            
            # 在Histogram标签页时更新cursor manager关联
            if self.tab_widget.currentIndex() == 1:
                self._sync_cursor_manager_to_canvas(self.subplot3_canvas)
                # 同步cursor可见性状态
                if hasattr(self.plot_canvas, 'get_cursors_visible') and hasattr(self.subplot3_canvas, 'set_cursors_visible'):
                    visibility = self.plot_canvas.get_cursors_visible()
                    self.subplot3_canvas.set_cursors_visible(visibility)
                    # 更新按钮文本
                    if hasattr(self, 'cursor_info_panel'):
                        self.cursor_info_panel.update_visibility_button_text(visibility)
                    if hasattr(self.popup_cursor_manager, 'toggle_visibility_btn'):
                        self.popup_cursor_manager.toggle_visibility_btn.setText("Hide" if visibility else "Show")
                
        except Exception as e:
            print(f"Error updating subplot3 histogram: {e}")
        finally:
            self._updating_subplot3 = False
    
    def _clear_shared_fits_on_data_change(self):
        """数据变化时清除共享拟合数据 - 增强版"""
        print("[Fix] Starting comprehensive fit data clearing...")
        
        # 第1步：清除共享拟合数据
        if hasattr(self, 'shared_fit_data') and self.shared_fit_data:
            if self.shared_fit_data.has_fits():
                print(f"[Fix] Clearing shared fit data: {len(self.shared_fit_data.gaussian_fits)} fits")
                self.shared_fit_data.clear_fits()
            else:
                print("[Fix] No fits in shared data to clear")
        else:
            print("[Fix] No shared_fit_data found")
            
        # 第2步：清除subplot3_canvas中的拟合显示
        if hasattr(self, 'subplot3_canvas'):
            try:
                if hasattr(self.subplot3_canvas, 'clear_fits'):
                    self.subplot3_canvas.clear_fits()
                    print("[Fix] Cleared fits from subplot3_canvas")
                    
                # 清除subplot3_canvas自身的拟合数据
                if hasattr(self.subplot3_canvas, 'fitting_manager') and self.subplot3_canvas.fitting_manager:
                    if hasattr(self.subplot3_canvas.fitting_manager, 'gaussian_fits'):
                        self.subplot3_canvas.fitting_manager.gaussian_fits.clear()
                        print("[Fix] Cleared subplot3_canvas fitting_manager gaussian_fits")
                        
            except Exception as e:
                print(f"[Fix] Error clearing subplot3_canvas: {e}")
                
        # 第3步：清除主视图subplot3中的拟合线条
        if hasattr(self, 'plot_canvas'):
            try:
                if hasattr(self.plot_canvas, '_ax3_fit_lines') and self.plot_canvas._ax3_fit_lines:
                    for line in self.plot_canvas._ax3_fit_lines[:]:
                        try:
                            if line and line in self.plot_canvas.ax3.lines:
                                line.remove()
                        except:
                            pass
                    self.plot_canvas._ax3_fit_lines.clear()
                    print("[Fix] Cleared fits from main view subplot3")
                    
                # 清除plot_canvas自身的拟合数据
                if hasattr(self.plot_canvas, 'fitting_manager') and self.plot_canvas.fitting_manager:
                    if hasattr(self.plot_canvas.fitting_manager, 'gaussian_fits'):
                        self.plot_canvas.fitting_manager.gaussian_fits.clear()
                        print("[Fix] Cleared plot_canvas fitting_manager gaussian_fits")
                        
            except Exception as e:
                print(f"[Fix] Error clearing plot_canvas: {e}")
                
        # 第4步：强制清除拟合信息面板
        try:
            if hasattr(self, 'fit_info_panel') and self.fit_info_panel is not None:
                print("[Fix] Force clearing fit_info_panel")
                # 直接清空列表
                self.fit_info_panel.fit_list.clear()
                # 调用正式的清除方法
                self.fit_info_panel.clear_all_fits()
                # 显示提示信息
                self.fit_info_panel.info_label.show()
                self.fit_info_panel.stats_label.setText("Select a fit to view its details")
                print("[Fix] Successfully force cleared fit info panel")
            else:
                print("[Fix] fit_info_panel not found or is None")
        except Exception as e:
            print(f"[Fix] Error force clearing fit_info_panel: {e}")
            import traceback
            traceback.print_exc()
                
        # 第5步：重绘所有相关的画布
        try:
            if hasattr(self, 'subplot3_canvas'):
                self.subplot3_canvas.draw()
            if hasattr(self, 'plot_canvas'):
                self.plot_canvas.draw()
        except Exception as e:
            print(f"[Fix] Error redrawing canvases: {e}")
                
        print("[Fix] Comprehensive fit data clearing completed")
    
    def _restore_fits_to_subplot3(self):
        """恢复拟合曲线到subplot3"""
        try:
            if not hasattr(self, 'subplot3_canvas') or not hasattr(self, 'shared_fit_data'):
                return
                
            if not self.shared_fit_data or not self.shared_fit_data.has_fits():
                print("No shared fit data to restore to subplot3")
                return
                
            print(f"Restoring {len(self.shared_fit_data.gaussian_fits)} fits to subplot3")
            
            # 调用subplot3_canvas的恢复方法
            if hasattr(self.subplot3_canvas, 'restore_fits_from_shared_data'):
                success = self.subplot3_canvas.restore_fits_from_shared_data()
                if success:
                    print("Successfully restored fits to subplot3")
                    # 更新绘图
                    self.subplot3_canvas.draw()
                else:
                    print("Failed to restore fits to subplot3")
            else:
                print("subplot3_canvas does not support restore_fits_from_shared_data")
                
        except Exception as e:
            print(f"Error restoring fits to subplot3: {e}")
            import traceback
            traceback.print_exc()
    
    def _sync_cursor_manager_to_canvas(self, canvas):
        """同步cursor manager到指定画布 - 修复重复创建问题"""
        # 确保两个画布之间的cursor数据同步，但histogram不显示cursor
        try:
            if canvas == self.subplot3_canvas:
                # 切换到histogram tab时，将主视图的cursor数据同步到subplot3
                if hasattr(self.plot_canvas, 'cursor_manager') and hasattr(self.subplot3_canvas, 'cursor_manager'):
                    # 只同步基本数据，不复制线条引用
                    source_cursors = self.plot_canvas.cursor_manager.cursors
                    target_cursors = []
                    
                    for cursor in source_cursors:
                        # 只复制基本数据，不复制线条引用
                        cursor_copy = {
                            'id': cursor['id'],
                            'y_position': cursor['y_position'],
                            'color': cursor['color'],
                            'selected': cursor.get('selected', False),
                            'line_ax2': None,  # 不复制线条引用
                            'line_ax3': None,  # 不复制线条引用
                            'histogram_line': None  # histogram模式下不创建
                        }
                        target_cursors.append(cursor_copy)
                    
                    self.subplot3_canvas.cursor_manager.cursors = target_cursors
                    
                    # 同步cursor计数器
                    self.subplot3_canvas.cursor_manager.cursor_counter = self.plot_canvas.cursor_manager.cursor_counter
                    
                    # 同步选中状态
                    if hasattr(self.plot_canvas.cursor_manager, 'selected_cursor') and self.plot_canvas.cursor_manager.selected_cursor:
                        selected_id = self.plot_canvas.cursor_manager.selected_cursor.get('id')
                        for cursor in self.subplot3_canvas.cursor_manager.cursors:
                            if cursor.get('id') == selected_id:
                                self.subplot3_canvas.cursor_manager.selected_cursor = cursor
                                break
                    else:
                        self.subplot3_canvas.cursor_manager.selected_cursor = None
                    
                    # 同步可见性状态
                    self.subplot3_canvas.cursor_manager.cursors_visible = self.plot_canvas.cursor_manager.cursors_visible
                    
                    # 同步兼容性属性
                    self._sync_compatibility_attributes(self.subplot3_canvas)
                    
                    print(f"Synced {len(self.subplot3_canvas.cursor_manager.cursors)} cursors to histogram view (data only, no display)")
                    
            elif canvas == self.plot_canvas:
                # 切换到主视图时，将subplot3的cursor数据同步到主视图
                if hasattr(self.subplot3_canvas, 'cursor_manager') and hasattr(self.plot_canvas, 'cursor_manager'):
                    # 只同步基本数据，不复制线条引用
                    source_cursors = self.subplot3_canvas.cursor_manager.cursors
                    target_cursors = []
                    
                    for cursor in source_cursors:
                        # 只复制基本数据，不复制线条引用
                        cursor_copy = {
                            'id': cursor['id'],
                            'y_position': cursor['y_position'],
                            'color': cursor['color'],
                            'selected': cursor.get('selected', False),
                            'line_ax2': None,  # 稍后重新创建
                            'line_ax3': None,  # 稍后重新创建
                            'histogram_line': None
                        }
                        target_cursors.append(cursor_copy)
                    
                    self.plot_canvas.cursor_manager.cursors = target_cursors
                    
                    # 同步cursor计数器
                    self.plot_canvas.cursor_manager.cursor_counter = self.subplot3_canvas.cursor_manager.cursor_counter
                    
                    # 同步选中状态
                    if hasattr(self.subplot3_canvas.cursor_manager, 'selected_cursor') and self.subplot3_canvas.cursor_manager.selected_cursor:
                        selected_id = self.subplot3_canvas.cursor_manager.selected_cursor.get('id')
                        for cursor in self.plot_canvas.cursor_manager.cursors:
                            if cursor.get('id') == selected_id:
                                self.plot_canvas.cursor_manager.selected_cursor = cursor
                                break
                    else:
                        self.plot_canvas.cursor_manager.selected_cursor = None
                    
                    # 同步可见性状态
                    self.plot_canvas.cursor_manager.cursors_visible = self.subplot3_canvas.cursor_manager.cursors_visible
                    
                    # 同步兼容性属性
                    self._sync_compatibility_attributes(self.plot_canvas)
                    
                    # 在主视图中正常显示cursor，使用强制清理重新创建线条
                    if hasattr(self.plot_canvas, 'cursor_manager'):
                        # 直接调用刷新方法，其中包含了强制清理
                        if hasattr(self.plot_canvas, 'refresh_cursors_after_plot_update'):
                            self.plot_canvas.refresh_cursors_after_plot_update()
                    
                    print(f"Synced {len(self.plot_canvas.cursor_manager.cursors)} cursors to main view (with display)")
                    
        except Exception as e:
            print(f"Error syncing cursor data: {e}")
            import traceback
            traceback.print_exc()
    
    def _sync_compatibility_attributes(self, canvas):
        """同步兼容性属性，确保旧代码正常工作"""
        try:
            if hasattr(canvas, 'cursor_manager'):
                # 通过设置兼容性属性来触发同步
                if hasattr(canvas, 'cursors'):
                    canvas.cursors = canvas.cursor_manager.cursors
                if hasattr(canvas, 'cursor_counter'):
                    canvas.cursor_counter = canvas.cursor_manager.cursor_counter
                if hasattr(canvas, 'selected_cursor'):
                    canvas.selected_cursor = canvas.cursor_manager.selected_cursor
        except Exception as e:
            print(f"Error syncing compatibility attributes: {e}")
    
    def toggle_cursor_manager(self):
        """切换cursor manager显示 - 不再需要，cursor管理功能已集成到cursor_info_panel"""
        # if self.popup_cursor_manager.isVisible():
        #     self.popup_cursor_manager.hide()
        # else:
        #     canvas = self.get_current_canvas()
        #     self.popup_cursor_manager.set_plot_widget(canvas)
        #     self.popup_cursor_manager.show_popup()
        #     
        #     # 强制激活
        #     self.popup_cursor_manager.raise_()
        #     self.popup_cursor_manager.activateWindow()
        #     self.popup_cursor_manager.setFocus()
        pass
    
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
    
    def on_toggle_cursors_visibility(self):
        """处理cursor可见性切换请求"""
        try:
            # 获取当前活动的画布
            current_canvas = self.get_current_canvas()
            
            if hasattr(current_canvas, 'toggle_cursors_visibility'):
                new_visibility = current_canvas.toggle_cursors_visibility()
                
                # 同步到两个画布
                if current_canvas == self.plot_canvas:
                    if hasattr(self.subplot3_canvas, 'set_cursors_visible'):
                        self.subplot3_canvas.set_cursors_visible(new_visibility)
                elif current_canvas == self.subplot3_canvas:
                    if hasattr(self.plot_canvas, 'set_cursors_visible'):
                        self.plot_canvas.set_cursors_visible(new_visibility)
                
                # 更新cursor信息面板按钮文本
                if hasattr(self, 'cursor_info_panel'):
                    self.cursor_info_panel.update_visibility_button_text(new_visibility)
                
                # 更新popup cursor manager按钮文本 - 不再需要
                # if hasattr(self.popup_cursor_manager, 'toggle_visibility_btn'):
                #     if new_visibility:
                #         self.popup_cursor_manager.toggle_visibility_btn.setText("Hide")
                #     else:
                #         self.popup_cursor_manager.toggle_visibility_btn.setText("Show")
                
                status = "visible" if new_visibility else "hidden"
                self.status_bar.showMessage(f"Cursors are now {status}")
            else:
                self.status_bar.showMessage("Current canvas does not support cursor visibility toggle")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error toggling cursor visibility: {str(e)}")
            print(f"Error in on_toggle_cursors_visibility: {e}")
            import traceback
            traceback.print_exc()
