#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用程序样式定义 - 支持多主题
"""

# 主色调定义
COLORS = {
    "primary": "#2c3e50",         # 主要颜色（深蓝灰）
    "primary_light": "#34495e",    # 主要颜色亮版
    "secondary": "#3498db",       # 次要颜色（蓝色）
    "accent": "#1abc9c",          # 强调色（青绿色）
    "background": "#f5f7fa",      # 背景色（浅灰）
    "card": "#ffffff",            # 卡片背景色（白色）
    "text": "#333333",            # 文本颜色（深灰）
    "text_light": "#7f8c8d",      # 浅色文本（浅灰）
    "success": "#2ecc71",         # 成功颜色（绿色）
    "warning": "#f39c12",         # 警告颜色（橙色）
    "error": "#e74c3c",           # 错误颜色（红色）
    "border": "#d0d7de"           # 边框颜色（中灰）
}

# 定义深色主题
DARK_COLORS = {
    "primary": "#1e3b52",         # 主要颜色（深调蓝色）
    "primary_light": "#2c5282",    # 主要颜色亮版
    "secondary": "#4a6fa5",       # 次要颜色（蓝色）
    "accent": "#38b2ac",          # 强调色（青绿色）
    "background": "#1a202c",      # 背景色（近黑色）
    "card": "#2d3748",            # 卡片背景色（深灰）
    "text": "#e2e8f0",            # 文本颜色（浅色）
    "text_light": "#a0aec0",      # 浅色文本（浅灰）
    "success": "#48bb78",         # 成功颜色（绿色）
    "warning": "#ecc94b",         # 警告颜色（黄色）
    "error": "#f56565",           # 错误颜色（红色）
    "border": "#4a5568"           # 边框颜色（深灰）
}

# 深色主题的图表样式
DARK_PLOT_STYLE = {
    "figure.facecolor": DARK_COLORS["card"],
    "axes.facecolor": DARK_COLORS["card"],
    "axes.edgecolor": DARK_COLORS["border"],
    "axes.labelcolor": DARK_COLORS["text"],
    "axes.grid": True,
    "grid.color": "#4a5568",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "xtick.color": DARK_COLORS["text"],
    "ytick.color": DARK_COLORS["text"],
    "text.color": DARK_COLORS["text"],
    "lines.linewidth": 2,
    "lines.markersize": 6,
    "font.family": "sans-serif",
    "font.sans-serif": ["SF Pro Display", "Helvetica Neue", "Arial", "DejaVu Sans"],
}

# 全局样式表
GLOBAL_STYLE = f"""
QWidget {{
    font-family: Helvetica Neue, Arial;
    color: {COLORS["text"]};
}}

QMainWindow, QDialog {{
    background-color: {COLORS["background"]};
}}

/* 标题栏样式 */
#titleBar {{
    background-color: {COLORS["primary"]};
    color: white;
    border-radius: 0px;
}}

/* 按钮样式 */
QPushButton {{
    background-color: {COLORS["secondary"]};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: #2980b9;
}}

QPushButton:pressed {{
    background-color: #1c6ea4;
}}

QPushButton:disabled {{
    background-color: #bdc3c7;
    color: #7f8c8d;
}}

/* 次要按钮 */
QPushButton.secondary {{
    background-color: #ecf0f1;
    color: {COLORS["text"]};
    border: 1px solid #bdc3c7;
}}

QPushButton.secondary:hover {{
    background-color: #e0e6e8;
}}

/* 面板样式 */
QGroupBox {{
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    margin-top: 12px;
    font-weight: bold;
    background-color: {COLORS["card"]};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {COLORS["secondary"]};
}}

/* 输入框样式 */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 6px;
    background-color: white;
    selection-background-color: {COLORS["secondary"]};
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS["secondary"]};
}}

/* 列表和树样式 */
QListWidget, QTreeView {{
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    background-color: white;
    alternate-background-color: #f9f9f9;
}}

QListWidget::item, QTreeView::item {{
    padding: 4px;
    border-bottom: 1px solid #f0f0f0;
}}

QListWidget::item:selected, QTreeView::item:selected {{
    background-color: {COLORS["secondary"]};
    color: white;
}}

/* 标签页样式 */
QTabWidget::pane {{
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    background-color: {COLORS["card"]};
}}

QTabBar::tab {{
    background-color: #e6e6e6;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS["card"]};
    border-bottom: 3px solid {COLORS["accent"]};
    color: {COLORS["accent"]};
    font-weight: bold;
}}

QTabBar::tab:!selected {{
    color: {COLORS["text_light"]};
}}

QTabBar::tab:hover {{
    background-color: #f0f0f0;
}}

/* 状态栏样式 */
QStatusBar {{
    background-color: {COLORS["primary"]};
    color: white;
}}

/* 滚动条样式 */
QScrollBar:vertical {{
    border: none;
    background-color: #f0f0f0;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: #c0c0c0;
    min-height: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #a0a0a0;
}}

QScrollBar:horizontal {{
    border: none;
    background-color: #f0f0f0;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: #c0c0c0;
    min-width: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #a0a0a0;
}}

/* 去除滚动条上下按钮 */
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* 图表样式 */
QLabel#visualization_title {{
    color: {COLORS["primary"]};
    font-size: 16px;
    font-weight: bold;
    margin: 10px 0;
}}

/* 自定义标签头样式 */
QLabel.header {{
    color: {COLORS["primary"]};
    font-size: 14px;
    font-weight: bold;
    padding: 5px;
    background-color: #f8f9fa;
    border-radius: 4px;
}}

/* 卡片样式 */
QWidget.card {{
    background-color: {COLORS["card"]};
    border-radius: 6px;
    border: 1px solid {COLORS["border"]};
}}

/* 分割器样式 */
QSplitter::handle {{
    background-color: {COLORS["border"]};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* 工具提示样式 */
QToolTip {{
    background-color: {COLORS["primary"]};
    color: white;
    border: none;
    padding: 5px;
    opacity: 200;
}}
"""

# 定义图表样式
PLOT_STYLE = {
    "figure.facecolor": COLORS["card"],
    "axes.facecolor": COLORS["card"],
    "axes.edgecolor": COLORS["border"],
    "axes.labelcolor": COLORS["text"],
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "xtick.color": COLORS["text"],
    "ytick.color": COLORS["text"],
    "text.color": COLORS["text"],
    "lines.linewidth": 2,
    "lines.markersize": 6,
    "font.family": "sans-serif",
    "font.sans-serif": ["SF Pro Display", "Helvetica Neue", "Arial", "DejaVu Sans"],
}

# 定义图表颜色循环
PLOT_COLORS = [
    "#3498db",  # 蓝色
    "#2ecc71",  # 绿色
    "#e74c3c",  # 红色
    "#f39c12",  # 橙色
    "#9b59b6",  # 紫色
    "#1abc9c",  # 青绿色
    "#34495e",  # 深蓝灰色
    "#fd7e14",  # 深橙色
]

# 工具类：用于创建统一的组件样式
class StyleHelper:
    @staticmethod
    def card_widget():
        """返回一个带有卡片样式的QWidget"""
        from PyQt6.QtWidgets import QWidget
        widget = QWidget()
        widget.setObjectName("card")
        widget.setProperty("class", "card")
        widget.setStyleSheet("""
            QWidget#card {
                background-color: """ + COLORS["card"] + """;
                border-radius: 6px;
                border: 1px solid """ + COLORS["border"] + """;
            }
        """)
        return widget
    
    @staticmethod
    def header_label(text):
        """返回一个带有标题样式的QLabel"""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QFont
        label = QLabel(text)
        label.setProperty("class", "header")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        label.setFont(font)
        return label
    
    @staticmethod
    def apply_plot_style():
        """应用图表样式到matplotlib"""
        import matplotlib.pyplot as plt
        for key, value in PLOT_STYLE.items():
            plt.rcParams[key] = value
        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=PLOT_COLORS)
