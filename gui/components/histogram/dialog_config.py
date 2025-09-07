#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialog Configuration - 对话框配置文件
存储UI常量、样式和配置项
"""


class DialogConfig:
    """对话框配置类"""
    
    # 窗口配置
    WINDOW_TITLE = "Histogram Analysis - Enhanced"
    WINDOW_ICON = ""  # 移除emoji，使用空字符串或实际图标路径
    INITIAL_SIZE = (1200, 850)
    MINIMUM_SIZE = (900, 600)
    
    # 布局配置
    MAIN_MARGINS = (5, 5, 5, 5)
    MAIN_SPACING = 5
    
    # 面板宽度
    SIDE_PANEL_WIDTH = 250
    
    # 分割器比例 (左:中:右)
    SPLITTER_SIZES = [250, 900, 250]
    
    # 面板样式
    PANEL_MARGINS = (6, 6, 6, 6)
    PANEL_SPACING = 8
    GROUP_SPACING = 6
    
    # 组框内边距
    GROUP_MARGINS = (6, 6, 6, 6)
    GROUP_SPACING_SMALL = 4
    GROUP_SPACING_MEDIUM = 6
    
    # 中央区域样式
    CENTRAL_MARGINS = (3, 3, 3, 3)
    CENTRAL_SPACING = 3
    
    # 标签页内边距
    TAB_MARGINS = (2, 2, 2, 2)
    TAB_SPACING = 2
    
    # 绘图配置
    PLOT_DPI = 100
    PLOT_WIDTH = 10
    PLOT_HEIGHT = 8
    
    # 状态栏配置
    STATUS_BAR_HEIGHT = 24
    
    # 状态消息
    STATUS_MESSAGES = {
        'ready': 'Ready',
        'loading': 'Loading file...',
        'main_view': 'Main View - Signal analysis and region selection',
        'histogram_view': 'Histogram Analysis - Click and drag to select regions for Gaussian fitting',
        'fit_cleared': 'Cleared all Gaussian fits',
        'cursors_cleared': 'Cleared all cursors',
        'export_success': 'Export completed successfully',
        'images_copied': 'Images copied to clipboard successfully'
    }
    
    # 颜色配置
    COLORS = {
        'danger': '#f44336',
        'danger_hover': '#da190b',
        'danger_pressed': '#c62828',
        'primary': '#2196F3',
        'primary_hover': '#1976D2',
        'primary_pressed': '#0D47A1',
        'normal_bg': '#f5f5f5',
        'normal_hover': '#e8e8e8',
        'normal_pressed': '#d4d4d4',
        'border': '#cccccc',
        'border_hover': '#999999',
        'disabled_bg': '#cccccc',
        'disabled_text': '#666666'
    }


class UITexts:
    """UI文本常量"""
    
    # 组标题
    FILE_CONTROL = "File & Data Control"
    DISPLAY_SETTINGS = "Display Settings"
    EXPORT_TOOLS = "Export & Tools"
    FIT_RESULTS = "Gaussian Fit Results"
    CURSOR_MANAGEMENT = "Cursor Management"
    
    # 按钮文本
    CLEAR_ALL_FITS = "Clear All Fits"
    LOAD_FILE = "Load File"
    EXPORT_DATA = "Export Data"
    COPY_IMAGES = "Copy Images"
    ADD_CURSOR = "Add Cursor"
    CLEAR_CURSORS = "Clear All"
    
    # 标签页标题
    MAIN_VIEW_TAB = "Main View"
    HISTOGRAM_TAB = "Histogram Analysis"
    
    # 工具提示
    CLEAR_FITS_TOOLTIP = "Clear all Gaussian fits from the histogram"
    LOG_X_TOOLTIP = "Apply logarithmic scale to X-axis"
    LOG_Y_TOOLTIP = "Apply logarithmic scale to Y-axis"
    KDE_TOOLTIP = "Show Kernel Density Estimation curve"
    INVERT_DATA_TOOLTIP = "Invert data values (multiply by -1)"


class StyleSheets:
    """样式表常量"""
    
    @staticmethod
    def get_button_style(button_type='normal'):
        """获取按钮样式"""
        base_style = """
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
                min-height: 16px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        if button_type == 'danger':
            return base_style + """
                QPushButton {
                    background-color: #f44336;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c62828;
                }
            """
        elif button_type == 'primary':
            return base_style + """
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
            """
        else:  # normal
            return base_style + """
                QPushButton {
                    background-color: #f5f5f5;
                    color: #333333;
                    border: 1px solid #cccccc;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                    border-color: #999999;
                }
                QPushButton:pressed {
                    background-color: #d4d4d4;
                }
                QPushButton:disabled {
                    background-color: #f9f9f9;
                    color: #999999;
                    border-color: #e0e0e0;
                }
            """
    
    @staticmethod
    def get_groupbox_style():
        """获取群组框样式"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
                color: #2c3e50;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
                background-color: white;
            }
        """
    
    @staticmethod
    def get_tabwidget_style():
        """获取标签页控件样式"""
        return """
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                padding: 6px 12px;
                margin-right: 2px;
                border-radius: 4px 4px 0px 0px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
        """
    
    @staticmethod
    def get_toolbar_style():
        """获取工具栏样式"""
        return """
            QToolBar {
                border: none;
                spacing: 2px;
                background-color: #f8f9fa;
                padding: 2px;
            }
        """
