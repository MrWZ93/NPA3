#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Builder - UI构建器
专门负责直方图对话框的UI布局构建
"""

from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QWidget, 
                            QSplitter, QPushButton, QTabWidget, QStatusBar)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from .histogram_plot import HistogramPlot
from .controls import HistogramControlPanel, FileChannelControl
from .export_tools import ExportToolsPanel
from .fit_info_panel import FitInfoPanel
from .cursor_info_panel import CursorInfoPanel
from .dialog_config import DialogConfig, UITexts, StyleSheets


# UIStyleManager类已移至dialog_config.py中的StyleSheets类


class HistogramUIBuilder:
    """直方图UI构建器"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.config = DialogConfig()
    
    def build_main_layout(self):
        """构建主布局"""
        # 创建主分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 构建三个面板
        left_panel = self._build_left_panel()
        central_area = self._build_central_area()
        right_panel = self._build_right_panel()
        
        # 添加到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(central_area)
        main_splitter.addWidget(right_panel)
        
        # 优化分割器比例
        main_splitter.setSizes(DialogConfig.SPLITTER_SIZES)
        main_splitter.setStretchFactor(0, 0)  # 左侧固定
        main_splitter.setStretchFactor(1, 1)  # 中央可伸缩
        main_splitter.setStretchFactor(2, 0)  # 右侧固定
        
        # 添加到主布局
        self.dialog.main_layout.addWidget(main_splitter)
        
        # 添加状态栏
        status_bar = QStatusBar()
        status_bar.showMessage("Ready")
        # 限制状态栏高度，避免窗口最大化时过宽
        status_bar.setMaximumHeight(DialogConfig.STATUS_BAR_HEIGHT)
        status_bar.setStyleSheet("""
            QStatusBar {
                border-top: 1px solid #d0d0d0;
                background-color: #f8f9fa;
                font-size: 11px;
                padding: 2px 8px;
            }
        """)
        self.dialog.main_layout.addWidget(status_bar)
        
        # 保存引用
        self.dialog.status_bar = status_bar
        
        return main_splitter
    
    def _build_left_panel(self):
        """构建左侧控制面板"""
        panel = QWidget()
        panel.setFixedWidth(DialogConfig.SIDE_PANEL_WIDTH)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.PANEL_MARGINS)
        layout.setSpacing(DialogConfig.PANEL_SPACING)
        
        # File Control组 - 最常用，放在最上面
        file_group = self._create_file_control_group()
        layout.addWidget(file_group)
        
        # Histogram Settings组
        settings_group = self._create_histogram_settings_group()
        layout.addWidget(settings_group)
        
        # Export Tools组 - 使用较少，放在最下面
        export_group = self._create_export_tools_group()
        layout.addWidget(export_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def _create_file_control_group(self):
        """创建文件控制组"""
        group = QGroupBox(UITexts.FILE_CONTROL)
        group.setStyleSheet(StyleSheets.get_groupbox_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.GROUP_MARGINS)
        layout.setSpacing(DialogConfig.GROUP_SPACING_SMALL)
        
        # 创建文件控制面板
        file_control = FileChannelControl(self.dialog)
        layout.addWidget(file_control)
        
        group.setLayout(layout)
        
        # 保存引用
        self.dialog.file_channel_control = file_control
        
        return group
    
    def _create_histogram_settings_group(self):
        """创建直方图设置组"""
        group = QGroupBox(UITexts.DISPLAY_SETTINGS)
        group.setStyleSheet(StyleSheets.get_groupbox_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.GROUP_MARGINS)
        layout.setSpacing(DialogConfig.GROUP_SPACING_SMALL)
        
        # 创建直方图控制面板
        histogram_control = HistogramControlPanel(self.dialog)
        layout.addWidget(histogram_control)
        
        group.setLayout(layout)
        
        # 保存引用
        self.dialog.histogram_control = histogram_control
        
        return group
    
    def _create_export_tools_group(self):
        """创建导出工具组"""
        group = QGroupBox(UITexts.EXPORT_TOOLS)
        group.setStyleSheet(StyleSheets.get_groupbox_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.GROUP_MARGINS)
        layout.setSpacing(DialogConfig.GROUP_SPACING_SMALL)
        
        # 创建导出工具面板
        export_tools = ExportToolsPanel(self.dialog)
        layout.addWidget(export_tools)
        
        group.setLayout(layout)
        
        # 保存引用
        self.dialog.export_tools = export_tools
        
        return group
    
    def _build_central_area(self):
        """构建中央图表显示区域"""
        central_area = QWidget()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.CENTRAL_MARGINS)
        layout.setSpacing(DialogConfig.CENTRAL_SPACING)
        
        # 创建标签页控件
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(StyleSheets.get_tabwidget_style())
        
        # 主视图标签页
        main_tab = self._create_main_view_tab()
        tab_widget.addTab(main_tab, UITexts.MAIN_VIEW_TAB)
        
        # 直方图标签页
        histogram_tab = self._create_histogram_tab()
        tab_widget.addTab(histogram_tab, UITexts.HISTOGRAM_TAB)
        
        layout.addWidget(tab_widget)
        central_area.setLayout(layout)
        
        # 保存引用
        self.dialog.tab_widget = tab_widget
        self.dialog.central_area = central_area
        
        return central_area
    
    def _create_main_view_tab(self):
        """创建主视图标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(*DialogConfig.TAB_MARGINS)
        layout.setSpacing(DialogConfig.TAB_SPACING)
        
        # 创建绘图画布
        plot_canvas = HistogramPlot(self.dialog, 
                                   width=DialogConfig.PLOT_WIDTH, 
                                   height=DialogConfig.PLOT_HEIGHT, 
                                   dpi=DialogConfig.PLOT_DPI)
        plot_canvas.set_shared_fit_data(self.dialog.shared_fit_data)
        
        # 创建工具栏
        toolbar = NavigationToolbar(plot_canvas, self.dialog)
        toolbar.setStyleSheet(StyleSheets.get_toolbar_style())
        
        layout.addWidget(toolbar)
        layout.addWidget(plot_canvas)
        
        # 保存引用
        self.dialog.plot_canvas = plot_canvas
        self.dialog.plot_toolbar = toolbar
        
        return tab
    
    def _create_histogram_tab(self):
        """创建直方图标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(*DialogConfig.TAB_MARGINS)
        layout.setSpacing(DialogConfig.TAB_SPACING)
        
        # 创建绘图画布
        subplot3_canvas = HistogramPlot(self.dialog, 
                                       width=DialogConfig.PLOT_WIDTH, 
                                       height=DialogConfig.PLOT_HEIGHT, 
                                       dpi=DialogConfig.PLOT_DPI)
        subplot3_canvas.set_shared_fit_data(self.dialog.shared_fit_data)
        
        # 创建工具栏
        toolbar = NavigationToolbar(subplot3_canvas, self.dialog)
        toolbar.setStyleSheet(StyleSheets.get_toolbar_style())
        
        layout.addWidget(toolbar)
        layout.addWidget(subplot3_canvas)
        
        # 保存引用
        self.dialog.subplot3_canvas = subplot3_canvas
        self.dialog.subplot3_toolbar = toolbar
        
        return tab
    
    def _build_right_panel(self):
        """构建右侧面板"""
        panel = QWidget()
        panel.setFixedWidth(DialogConfig.SIDE_PANEL_WIDTH)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.PANEL_MARGINS)
        layout.setSpacing(DialogConfig.PANEL_SPACING)
        
        # Fit Results组
        fit_group = self._create_fit_results_group()
        layout.addWidget(fit_group)
        
        # Cursors组
        cursor_group = self._create_cursor_control_group()
        layout.addWidget(cursor_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def _create_fit_results_group(self):
        """创建拟合结果组"""
        group = QGroupBox(UITexts.FIT_RESULTS)
        group.setStyleSheet(StyleSheets.get_groupbox_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.GROUP_MARGINS)
        layout.setSpacing(DialogConfig.GROUP_SPACING_MEDIUM)
        
        # 创建拟合信息面板
        fit_info_panel = FitInfoPanel(self.dialog)
        layout.addWidget(fit_info_panel)
        
        # Clear All按钮
        clear_btn = QPushButton(UITexts.CLEAR_ALL_FITS)
        clear_btn.setStyleSheet(StyleSheets.get_button_style('danger'))
        clear_btn.setToolTip("Clear all Gaussian fits from the histogram")
        layout.addWidget(clear_btn)
        
        group.setLayout(layout)
        
        # 保存引用
        self.dialog.fit_info_panel = fit_info_panel
        self.dialog.clear_all_btn = clear_btn
        
        return group
    
    def _create_cursor_control_group(self):
        """创建Cursor控制组"""
        group = QGroupBox(UITexts.CURSOR_MANAGEMENT)
        group.setStyleSheet(StyleSheets.get_groupbox_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*DialogConfig.GROUP_MARGINS)
        layout.setSpacing(DialogConfig.GROUP_SPACING_MEDIUM)
        
        # 创建cursor信息面板
        cursor_info_panel = CursorInfoPanel(self.dialog)
        layout.addWidget(cursor_info_panel)
        
        group.setLayout(layout)
        
        # 保存引用
        self.dialog.cursor_info_panel = cursor_info_panel
        
        return group
