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
                            QStatusBar, QWidget, QSplitter, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

# 导入自定义模块
from .histogram_plot import HistogramPlot, FitDataManager
from .data_manager import HistogramDataManager
from .controls import HistogramControlPanel, FileChannelControl
from .export_tools import ExportToolsPanel, IntegratedDataExporter, ImageClipboardManager, HistogramExporter
from .fit_info_panel import FitInfoPanel
from .popup_cursor_manager import PopupCursorManager
from .cursor_info_panel import CursorInfoPanel


class HistogramDialog(QDialog):
    """直方图分析对话框"""
    
    def __init__(self, parent=None):
        super(HistogramDialog, self).__init__(parent)
        self.setWindowTitle("Histogram Analysis")
        self.resize(1000, 800)  # 设置初始大小
        
        # 初始化数据管理器
        self.data_manager = HistogramDataManager(self)
        
        # 【新增】初始化共享的拟合数据管理器
        self.shared_fit_data = FitDataManager()
        
        # 拟合曲线显示状态
        self.fit_curves_visible = True
        
        # 初始化导出器
        self.exporter = HistogramExporter(self)
        self.integrated_exporter = IntegratedDataExporter(self)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        
        # 设置界面
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主布局：水平分割为三个面板
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ================ 左侧面板：Histogram Settings ================
        self.setup_left_panel()
        main_splitter.addWidget(self.left_panel)
        
        # ================ 中央区域：图表显示 ================
        self.setup_central_area()
        main_splitter.addWidget(self.central_area)
        
        # ================ 右侧面板：Fit Results & Cursors ================
        self.setup_right_panel()
        main_splitter.addWidget(self.right_panel)
        
        # 设置分割器比例 (左:中:右 = 280:800:280)
        main_splitter.setSizes([280, 800, 280])
        main_splitter.setStretchFactor(0, 0)  # 左侧固定
        main_splitter.setStretchFactor(1, 1)  # 中央可伸缩
        main_splitter.setStretchFactor(2, 0)  # 右侧固定
        
        # 将分割器添加到主布局
        self.main_layout.addWidget(main_splitter)
        
        # ================ 状态栏 ================
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        self.main_layout.addWidget(self.status_bar)
        
        # ================ 初始化弹窗式cursor manager ================
        self.popup_cursor_manager = PopupCursorManager(self)
        self.popup_cursor_manager.hide()  # 初始状态为隐藏
    
    def setup_left_panel(self):
        """设置左侧控制面板"""
        self.left_panel = QGroupBox()
        self.left_panel.setFixedWidth(280)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Histogram Settings组
        settings_group = QGroupBox("Histogram Settings")
        settings_layout = QVBoxLayout()
        
        # 创建直方图控制面板
        self.histogram_control = HistogramControlPanel(self)
        settings_layout.addWidget(self.histogram_control)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # File Control组
        file_group = QGroupBox("File Control")
        file_layout = QVBoxLayout()
        
        # 创建文件和通道控制面板
        self.file_channel_control = FileChannelControl(self)
        file_layout.addWidget(self.file_channel_control)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Export Tools组
        export_group = QGroupBox("Export Tools")
        export_layout = QVBoxLayout()
        
        # 创建导出工具面板
        self.export_tools = ExportToolsPanel(self)
        export_layout.addWidget(self.export_tools)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # 添加伸缩空间
        layout.addStretch()
        
        self.left_panel.setLayout(layout)
    
    def setup_central_area(self):
        """设置中央图表显示区域"""
        self.central_area = QWidget()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 主视图标签页
        self.main_tab = QWidget()
        main_tab_layout = QVBoxLayout(self.main_tab)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建主视图绘图区
        self.plot_canvas = HistogramPlot(self, width=10, height=8, dpi=100)
        # 设置共享拟合数据
        self.plot_canvas.set_shared_fit_data(self.shared_fit_data)
        
        self.plot_toolbar = NavigationToolbar(self.plot_canvas, self)
        
        # 将绘图区添加到主视图标签页
        main_tab_layout.addWidget(self.plot_toolbar)
        main_tab_layout.addWidget(self.plot_canvas)
        
        # Histogram标签页
        self.subplot3_tab = QWidget()
        subplot3_tab_layout = QVBoxLayout(self.subplot3_tab)
        subplot3_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建 subplot3 直方图绘图区
        self.subplot3_canvas = HistogramPlot(self, width=10, height=8, dpi=100)
        # 设置共享拟合数据
        self.subplot3_canvas.set_shared_fit_data(self.shared_fit_data)
        
        self.subplot3_toolbar = NavigationToolbar(self.subplot3_canvas, self)
        
        # 将绘图区添加到Histogram标签页
        subplot3_tab_layout.addWidget(self.subplot3_toolbar)
        subplot3_tab_layout.addWidget(self.subplot3_canvas)
        
        # 添加标签页到标签页控件
        self.tab_widget.addTab(self.main_tab, "Main View")
        self.tab_widget.addTab(self.subplot3_tab, "Histogram")
        
        layout.addWidget(self.tab_widget)
        self.central_area.setLayout(layout)
    
    def setup_right_panel(self):
        """设置右侧面板"""
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(280)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Fit Results组
        fit_group = QGroupBox("Fit Results")
        fit_layout = QVBoxLayout()
        fit_layout.setSpacing(10)
        
        # 创建拟合信息面板
        self.fit_info_panel = FitInfoPanel(self)
        fit_layout.addWidget(self.fit_info_panel)
        
        # Clear All按钮
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        self.clear_all_btn.clicked.connect(self.on_clear_fits_requested)
        fit_layout.addWidget(self.clear_all_btn)
        
        fit_group.setLayout(fit_layout)
        layout.addWidget(fit_group)
        
        # Cursors组
        cursors_group = QGroupBox("Cursors")
        cursors_layout = QVBoxLayout()
        cursors_layout.setSpacing(5)
        
        # 创建 Cursor 信息面板
        self.cursor_info_panel = CursorInfoPanel(self)
        cursors_layout.addWidget(self.cursor_info_panel)
        
        cursors_group.setLayout(cursors_layout)
        layout.addWidget(cursors_group)
        
        # 添加伸缩空间
        layout.addStretch()
        
        self.right_panel.setLayout(layout)
    
    def get_current_canvas(self):
        """获取当前活动的画布"""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 1:  # Histogram标签页
            return self.subplot3_canvas
        else:  # Main View标签页
            return self.plot_canvas
    
    def add_cursor(self):
        """添加cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'add_cursor'):
                cursor_id = canvas.add_cursor()
                if cursor_id is not None:
                    self.status_bar.showMessage(f"Added cursor {cursor_id}")
                    # 更新 cursor 信息面板
                    self.update_cursor_info_panel()
                else:
                    self.status_bar.showMessage("Failed to add cursor")
            else:
                self.status_bar.showMessage("Cursor functionality not available")
                
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
                    # 更新 cursor 信息面板
                    self.cursor_info_panel.clear_all_cursors()
                else:
                    self.status_bar.showMessage("Failed to clear cursors")
            else:
                self.status_bar.showMessage("Cursor functionality not available")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error clearing cursors: {str(e)}")
    
    def update_cursor_info_panel(self):
        """更新 cursor 信息面板"""
        try:
            canvas = self.get_current_canvas()
            if canvas and hasattr(canvas, 'get_cursor_info'):
                cursor_info = canvas.get_cursor_info()
                self.cursor_info_panel.refresh_cursor_list(cursor_info)
        except Exception as e:
            print(f"Error updating cursor info panel: {e}")
    
    def delete_cursor(self, cursor_id):
        """删除指定cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'remove_cursor'):
                success = canvas.remove_cursor(cursor_id)
                if success:
                    self.status_bar.showMessage(f"Deleted cursor {cursor_id}")
                    self.update_cursor_info_panel()
                else:
                    self.status_bar.showMessage(f"Failed to delete cursor {cursor_id}")
        except Exception as e:
            self.status_bar.showMessage(f"Error deleting cursor: {str(e)}")
    
    def delete_cursors(self, cursor_ids):
        """删除多个cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'remove_cursor'):
                success_count = 0
                for cursor_id in cursor_ids:
                    if canvas.remove_cursor(cursor_id):
                        success_count += 1
                
                self.status_bar.showMessage(f"Deleted {success_count} cursors")
                self.update_cursor_info_panel()
        except Exception as e:
            self.status_bar.showMessage(f"Error deleting cursors: {str(e)}")
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新cursor位置"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'update_cursor_position'):
                success = canvas.update_cursor_position(cursor_id, new_position)
                if success:
                    canvas.draw()
                    self.update_cursor_info_panel()
        except Exception as e:
            self.status_bar.showMessage(f"Error updating cursor position: {str(e)}")
    
    def select_cursor(self, cursor_id):
        """选中指定cursor"""
        try:
            canvas = self.get_current_canvas()
            if hasattr(canvas, 'select_cursor'):
                canvas.select_cursor(cursor_id if cursor_id >= 0 else None)
                self.update_cursor_info_panel()
        except Exception as e:
            self.status_bar.showMessage(f"Error selecting cursor: {str(e)}")
    
    def connect_signals(self):
        """连接信号和槽 - 修复版，避免循环调用"""
        # 【修复点1】添加信号连接防护机制
        if hasattr(self, '_connecting_signals') and self._connecting_signals:
            return
        
        try:
            self._connecting_signals = True
            
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
            self.export_tools.export_comprehensive_requested.connect(self.on_export_comprehensive)
            self.export_tools.copy_image_requested.connect(self.on_copy_images)
            
            # 拟合信息面板信号
            self.fit_info_panel.fit_deleted.connect(self.on_fit_deleted)
            self.fit_info_panel.fits_deleted.connect(self.on_fits_deleted)
            self.fit_info_panel.fit_edited.connect(self.on_fit_edited)
            self.fit_info_panel.fit_selected.connect(self.on_fit_selected)
            self.fit_info_panel.copy_all_fits.connect(self.on_copy_fit_info)
            self.fit_info_panel.toggle_fit_labels.connect(self.on_toggle_fit_labels)
            
            # 连接 Cursor 信息面板信号
            self.cursor_info_panel.add_cursor_requested.connect(self.add_cursor)
            self.cursor_info_panel.clear_cursors_requested.connect(self.clear_cursors)
            self.cursor_info_panel.cursor_selected.connect(self.select_cursor)
            self.cursor_info_panel.cursor_deleted.connect(self.delete_cursor)
            self.cursor_info_panel.cursors_deleted.connect(self.delete_cursors)
            self.cursor_info_panel.cursor_position_changed.connect(self.update_cursor_position)
            
            # Popup Cursor管理器信号
            self.popup_cursor_manager.cursor_position_changed.connect(self.on_cursor_position_changed)
            self.popup_cursor_manager.cursor_selection_changed.connect(self.on_cursor_selection_changed)
            
            # 初始化cursor manager与plot canvas的关联
            self.popup_cursor_manager.set_plot_widget(self.plot_canvas)
            
            # 优化cursor相关信号连接，避免重复连接
            # 连接plot canvas的cursor相关信号
            if hasattr(self.plot_canvas, 'cursor_selected'):
                try:
                    self.plot_canvas.cursor_selected.disconnect(self.on_plot_cursor_selected)
                except:
                    pass  # 如果没有连接则忽略
                self.plot_canvas.cursor_selected.connect(self.on_plot_cursor_selected)
                
            if hasattr(self.subplot3_canvas, 'cursor_selected'):
                try:
                    self.subplot3_canvas.cursor_selected.disconnect(self.on_plot_cursor_selected)
                except:
                    pass
                self.subplot3_canvas.cursor_selected.connect(self.on_plot_cursor_selected)
            
            # 连接 region_selected 信号用于高亮更新
            if hasattr(self.plot_canvas, 'region_selected'):
                try:
                    self.plot_canvas.region_selected.disconnect(self.on_region_selected)
                except:
                    pass
                self.plot_canvas.region_selected.connect(self.on_region_selected)
                
        except Exception as e:
            print(f"Error connecting signals: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._connecting_signals = False
    
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
                        show_kde=False,   # 默认不启用KDE
                        invert_data=False,  # 默认不取反数据
                        file_name=file_name
                    )
                    
                    # 绘制subplot3直方图
                    self.update_subplot3_histogram()
                    
                    # 更新 cursor 信息面板
                    self.update_cursor_info_panel()
            
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
        """更新subplot3直方图 - 支持拟合同步"""
        # 防止递归更新
        if (not hasattr(self.plot_canvas, 'data') or self.plot_canvas.data is None or 
            getattr(self, '_updating_subplot3', False)):
            return
        
        try:
            self._updating_subplot3 = True
        
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
            
            # 【修复Bug1】只有在确实有有效的共享拟合数据时才恢复
            # 并且要确保数据一致性
            if (self.shared_fit_data.has_fits() and 
                hasattr(self.subplot3_canvas, 'histogram_data') and 
                self.subplot3_canvas.histogram_data is not None):
                    
                print("Attempting to restore fits from shared data to subplot3")
                # 计算当前数据的哈希值用于验证
                current_data_hash = self.subplot3_canvas._calculate_data_hash() if hasattr(self.subplot3_canvas, '_calculate_data_hash') else None
                
                # 检查数据兼容性
                if (hasattr(self.shared_fit_data, 'is_compatible_with_data') and 
                    current_data_hash is not None and
                    self.shared_fit_data.is_compatible_with_data(None, current_data_hash)):
                        
                    if self.subplot3_canvas.restore_fits_from_shared_data():
                        print("Successfully restored fits to subplot3")
                    else:
                        print("Failed to restore fits - clearing shared data")
                        self.shared_fit_data.clear_fits()
                else:
                    print("Data incompatible or changed - clearing shared fit data")
                    self.shared_fit_data.clear_fits()
            
            # 设置cursor manager与subplot3 canvas的关联（如果是在Histogram标签页）
            if self.tab_widget.currentIndex() == 1:  # Histogram标签页
                self.popup_cursor_manager.set_plot_widget(self.subplot3_canvas)
                
        except Exception as e:
            print(f"Error updating subplot3 histogram: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._updating_subplot3 = False
    
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
                    show_kde=False,   # 默认不启用KDE
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
            
            # 更新 cursor 信息面板
            self.update_cursor_info_panel()
            
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
        # 【新增】清除拟合数据（数据区域变化）
        if self.shared_fit_data.has_fits():
            print("Clearing shared fit data due to highlight size change")
            self.shared_fit_data.clear_fits()
        # 更新subplot3直方图
        self.update_subplot3_histogram()
    
    def on_highlight_position_changed(self, position_percent):
        """处理高亮区域位置变化"""
        self.plot_canvas.move_highlight(position_percent)
        # 【新增】清除拟合数据（数据区域变化）
        if self.shared_fit_data.has_fits():
            print("Clearing shared fit data due to highlight position change")
            self.shared_fit_data.clear_fits()
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
        
        # 检查是否被禁用，如果被禁用则更新UI状态
        if enabled and not self.plot_canvas.log_y:
            # 对数刻度被禁用，更新复选框状态
            self.histogram_control.log_y_check.setChecked(False)
            self.status_bar.showMessage("Y-axis log scale disabled: histogram contains zero counts")
        else:
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
        """处理标签页切换 - 支持拟合同步"""
        # 防止在标签切换时产生递归调用
        if getattr(self, '_changing_tab', False):
            return
            
        try:
            self._changing_tab = True
            
            if index == 1:  # 切换到直方图标签页
                # 确保subplot3直方图是最新的
                self.update_subplot3_histogram()
                
                # 【新增】同步主视图的拟合数据到subplot3
                if hasattr(self.plot_canvas, 'gaussian_fits') and self.plot_canvas.gaussian_fits:
                    print("Syncing fits from main view to subplot3")
                    self.plot_canvas.save_current_fits()
                    
                # 更新cursor manager的关联
                if self.popup_cursor_manager.isVisible():
                    self.popup_cursor_manager.set_plot_widget(self.subplot3_canvas)
                
                # 更新 cursor 信息面板
                self.update_cursor_info_panel()
                    
            elif index == 0:  # 切换到主视图标签页
                # 【新增】同步subplot3的拟合数据到主视图（如果适用）
                if hasattr(self.subplot3_canvas, 'gaussian_fits') and self.subplot3_canvas.gaussian_fits:
                    print("Syncing fits from subplot3 to main view")
                    self.subplot3_canvas.save_current_fits()
                    # 尝试在主视图的subplot3中显示拟合结果
                    if hasattr(self.plot_canvas, 'restore_fits_from_shared_data'):
                        # 注意：这里不直接应用到主视图，因为数据格式不同
                        # 只在subplot3更新时应用
                        pass
                
                # 更新cursor manager的关联
                if self.popup_cursor_manager.isVisible():
                    self.popup_cursor_manager.set_plot_widget(self.plot_canvas)
                
                # 更新 cursor 信息面板
                self.update_cursor_info_panel()
                    
        except Exception as e:
            print(f"Error in tab change: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._changing_tab = False
    
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
            # 直接从图中删除，让 histogram_plot 负责同时更新 fit_info_panel
            if hasattr(self.subplot3_canvas, 'delete_specific_fit'):
                success = self.subplot3_canvas.delete_specific_fit(fit_index)
                if success:
                    self.status_bar.showMessage(f"Deleted fit {fit_index}")
                else:
                    self.status_bar.showMessage(f"Failed to delete fit {fit_index}")
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
            if hasattr(self.subplot3_canvas, 'delete_multiple_fits'):
                # 使用新的批量删除方法
                success_count = self.subplot3_canvas.delete_multiple_fits(fit_indices)
                self.status_bar.showMessage(f"Deleted {success_count} fits")
            else:
                # 如果新方法不存在，使用原方法
                success_count = 0
                # 从大到小排序索引，以避免删除时影响索引
                for fit_index in sorted(fit_indices, reverse=True):
                    if self.subplot3_canvas.delete_specific_fit(fit_index):
                        success_count += 1
                
                self.status_bar.showMessage(f"Deleted {success_count} fits")
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
    
    def on_export_comprehensive(self):
        """处理综合导出请求"""
        try:
            success, message = self.integrated_exporter.export_comprehensive_data()
            
            if success:
                self.status_bar.showMessage("Export completed successfully")
                QMessageBox.information(
                    self,
                    "Export Complete",
                    message
                )
            else:
                self.status_bar.showMessage(f"Export failed: {message}")
                if "cancelled" not in message.lower():
                    QMessageBox.warning(
                        self,
                        "Export Failed",
                        message
                    )
                    
        except Exception as e:
            error_msg = f"Error during comprehensive export: {str(e)}"
            self.status_bar.showMessage(error_msg)
            QMessageBox.critical(
                self,
                "Export Error",
                error_msg
            )
    
    def on_copy_images(self):
        """处理图像复制请求"""
        try:
            # 检查是否有必要的canvas对象
            if not hasattr(self, 'plot_canvas') or not hasattr(self, 'subplot3_canvas'):
                self.status_bar.showMessage("No images available to copy")
                return
            
            # 复制图像到剪贴板
            success, message = ImageClipboardManager.copy_combined_images_to_clipboard(
                self.plot_canvas, self.subplot3_canvas
            )
            
            if success:
                self.status_bar.showMessage("Images copied to clipboard successfully")
            else:
                self.status_bar.showMessage(f"Failed to copy images: {message}")
                QMessageBox.warning(
                    self,
                    "Copy Failed",
                    f"Failed to copy images to clipboard:\n{message}"
                )
                
        except Exception as e:
            error_msg = f"Error copying images: {str(e)}"
            self.status_bar.showMessage(error_msg)
            QMessageBox.critical(
                self,
                "Copy Error",
                error_msg
            )
    
    def on_cursor_position_changed(self, cursor_id, new_position):
        """处理cursor位置变化"""
        self.status_bar.showMessage(f"Cursor {cursor_id} moved to Y = {new_position:.4f}")
        # 更新 cursor 信息面板
        self.update_cursor_info_panel()
        
    def on_cursor_selection_changed(self, cursor_id):
        """处理cursor选择变化"""
        if cursor_id >= 0:
            self.status_bar.showMessage(f"Selected cursor {cursor_id}")
        else:
            self.status_bar.showMessage("No cursor selected")
        # 更新 cursor 信息面板
        self.update_cursor_info_panel()
    
    def on_plot_cursor_selected(self, cursor_id):
        """处理从 plot canvas 发来的 cursor 选中信号 - 修复防护"""
        # 防止在cursor选中时产生递归调用
        if getattr(self, '_handling_cursor_selection', False):
            return
            
        try:
            self._handling_cursor_selection = True
            
            # 更新cursor manager的状态
            if self.popup_cursor_manager.isVisible():
                self.popup_cursor_manager.update_from_plot()
            
            # 更新 cursor 信息面板
            self.update_cursor_info_panel()
            
            # 更新状态栏显示
            if cursor_id is not None and cursor_id >= 0:
                self.status_bar.showMessage(f"Selected cursor {cursor_id} from plot")
            else:
                self.status_bar.showMessage("Cursor selection cleared from plot")
                
        except Exception as e:
            print(f"Error handling plot cursor selection: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._handling_cursor_selection = False
    
    def on_region_selected(self, x_min, x_max):
        """处理区域选择信号，确保 subplot2 更新并同步拟合数据"""
        try:
            # 确保 subplot2 和 subplot3 被正确更新
            if hasattr(self.plot_canvas, 'update_highlighted_plots'):
                self.plot_canvas.update_highlighted_plots()
            
            # 【新增】清除旧的拟合数据（因为数据已经变化）
            if self.shared_fit_data.has_fits():
                print("Clearing shared fit data due to data region change")
                self.shared_fit_data.clear_fits()
            
            # 更新 subplot3 直方图
            self.update_subplot3_histogram()
            
            self.status_bar.showMessage(f"Region selected: {x_min:.3f} to {x_max:.3f}")
            
        except Exception as e:
            print(f"Error handling region selection: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_cursor_manager(self):
        """切换cursor manager面板的显示/隐藏"""
        if self.popup_cursor_manager.isVisible():
            self.popup_cursor_manager.hide()
        else:
            # 根据当前标签页设置cursor manager与正确的plot canvas的关联
            current_tab = self.tab_widget.currentIndex()
            if current_tab == 1:  # Histogram标签页
                self.popup_cursor_manager.set_plot_widget(self.subplot3_canvas)
            else:  # Main View标签页
                self.popup_cursor_manager.set_plot_widget(self.plot_canvas)
            
            # 显示弹窗
            self.popup_cursor_manager.show_popup()
            
            # 强制激活窗口并获得焦点
            self.popup_cursor_manager.raise_()
            self.popup_cursor_manager.activateWindow()
            self.popup_cursor_manager.setFocus()
    
    def toggle_fit_display(self):
        """切换主视图subplot3中拟合曲线的显示状态"""
        try:
            self.fit_curves_visible = self.fit_display_toggle_btn.isChecked()
            
            # 在主视图的subplot3中切换拟合曲线显示
            if hasattr(self.plot_canvas, '_ax3_fit_lines') and self.plot_canvas._ax3_fit_lines:
                for line in self.plot_canvas._ax3_fit_lines:
                    if line and hasattr(line, 'set_visible'):
                        line.set_visible(self.fit_curves_visible)
                
                # 重绘主视图
                self.plot_canvas.draw()
                
                # 更新状态栏
                status = "visible" if self.fit_curves_visible else "hidden"
                self.status_bar.showMessage(f"Fit curves in main view subplot3 are now {status}")
                print(f"Toggled fit display: {status}, lines count: {len(self.plot_canvas._ax3_fit_lines)}")
            else:
                self.status_bar.showMessage("No fit curves to toggle in main view")
                print("No _ax3_fit_lines found or list is empty")
                
        except Exception as e:
            self.status_bar.showMessage(f"Error toggling fit display: {str(e)}")
            print(f"Error in toggle_fit_display: {e}")
            import traceback
            traceback.print_exc()
    
    def update_subplot3_histogram_optimized(self):
        """更新subplot3直方图 - 优化版，支持cursor功能和实时更新"""
        if not hasattr(self.plot_canvas, 'data') or self.plot_canvas.data is None:
            return
        
        try:
            # 获取当前的高亮数据（从main view）
            highlight_min = self.plot_canvas.highlight_min
            highlight_max = self.plot_canvas.highlight_max
            data = self.plot_canvas.data
            
            # 应用数据取反设置
            highlighted_data = -data[highlight_min:highlight_max] if self.plot_canvas.invert_data else data[highlight_min:highlight_max]
            
            if len(highlighted_data) == 0:
                return
            
            # 在subplot3_canvas中创建直方图视图 - 使用新的优化方法
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
            
            # 设置cursor manager与subplot3 canvas的关联（如果是在Histogram标签页）
            if self.tab_widget.currentIndex() == 1:  # Histogram标签页
                self.popup_cursor_manager.set_plot_widget(self.subplot3_canvas)
                # 启动实时数据更新（如果cursor管理器可见）
                if self.popup_cursor_manager.isVisible():
                    self.popup_cursor_manager.start_real_time_updates()
                    
        except Exception as e:
            print(f"Error in update_subplot3_histogram_optimized: {e}")
            import traceback
            traceback.print_exc()
    
    def sync_cursor_data_between_views(self):
        """同步两个视图之间的cursor数据"""
        try:
            # 获取当前活跃的视图
            current_tab = self.tab_widget.currentIndex()
            
            if current_tab == 0:  # Main View
                source_canvas = self.plot_canvas
                target_canvas = self.subplot3_canvas
            else:  # Histogram View
                source_canvas = self.subplot3_canvas
                target_canvas = self.plot_canvas
            
            # 只有在两个视图都有数据时才同步
            if hasattr(source_canvas, 'cursors') and hasattr(target_canvas, 'cursors'):
                # 复制cursor数据
                target_canvas.cursors = source_canvas.cursors.copy()
                target_canvas.cursor_counter = source_canvas.cursor_counter
                target_canvas.selected_cursor = source_canvas.selected_cursor
                
                # 刷新目标视图的cursor显示
                if current_tab == 0:
                    if hasattr(target_canvas, 'refresh_cursors_for_histogram_mode'):
                        target_canvas.refresh_cursors_for_histogram_mode()
                else:
                    if hasattr(target_canvas, 'refresh_cursors_after_plot_update'):
                        target_canvas.refresh_cursors_after_plot_update()
                        
        except Exception as e:
            print(f"Error syncing cursor data: {e}")
            import traceback
            traceback.print_exc()
