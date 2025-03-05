#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拟合功能对话框
"""

import numpy as np
from scipy import optimize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QTabWidget, QWidget, QCheckBox,
    QMessageBox, QHeaderView, QApplication, QFormLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 导入自定义样式
from gui.styles import PLOT_STYLE, PLOT_COLORS, COLORS, StyleHelper

class FitResultsTable(QTableWidget):
    """拟合结果表格"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(['Parameter', 'Value', 'Error', 'Min', 'Max'])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cccccc;
                gridline-color: #eeeeee;
                background-color: white;
                selection-background-color: #0078d7;
                selection-color: white;
            }
            QTableWidget QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #cccccc;
                border-bottom: 1px solid #cccccc;
                font-weight: bold;
            }
        """)
    
    def update_fit_results(self, params, errors=None, bounds=None):
        """更新拟合结果"""
        self.setRowCount(0)  # 清空表格
        
        if not params:
            return
            
        self.setRowCount(len(params))
        
        for i, (param_name, value) in enumerate(params.items()):
            # 参数名称
            self.setItem(i, 0, QTableWidgetItem(param_name))
            
            # 值
            value_item = QTableWidgetItem(f"{value:.6g}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 1, value_item)
            
            # 误差
            if errors and param_name in errors:
                error_item = QTableWidgetItem(f"{errors[param_name]:.6g}")
                error_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i, 2, error_item)
            else:
                self.setItem(i, 2, QTableWidgetItem("N/A"))
            
            # 最小值和最大值
            if bounds and param_name in bounds:
                min_val, max_val = bounds[param_name]
                
                if min_val is not None:
                    min_item = QTableWidgetItem(f"{min_val:.6g}")
                else:
                    min_item = QTableWidgetItem("-∞")
                min_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i, 3, min_item)
                
                if max_val is not None:
                    max_item = QTableWidgetItem(f"{max_val:.6g}")
                else:
                    max_item = QTableWidgetItem("∞")
                max_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i, 4, max_item)
            else:
                self.setItem(i, 3, QTableWidgetItem("N/A"))
                self.setItem(i, 4, QTableWidgetItem("N/A"))

class FitPlot(FigureCanvas):
    """拟合结果绘图区域"""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        
        # 应用绘图样式
        for key, value in PLOT_STYLE.items():
            plt.rcParams[key] = value
        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=PLOT_COLORS)
        
        super(FitPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        self.fig.patch.set_facecolor(COLORS["card"])
        self.fig.tight_layout()
    
    def plot_fit(self, x_data, y_data, fit_func=None, fit_params=None, fit_x=None, fit_y=None, title="数据拟合"):
        """绘制数据和拟合曲线"""
        self.axes.clear()
        
        # 绘制原始数据点
        self.axes.scatter(x_data, y_data, s=20, alpha=0.7, label='数据点')
        
        # 如果提供了拟合函数和参数，计算并绘制拟合曲线
        if fit_func and fit_params and fit_x is None:
            # 生成平滑的x轴数据用于绘制拟合曲线
            fit_x = np.linspace(min(x_data), max(x_data), 1000)
            fit_y = fit_func(fit_x, **fit_params)
        
        # 如果直接提供了拟合曲线数据
        if fit_x is not None and fit_y is not None:
            self.axes.plot(fit_x, fit_y, 'r-', linewidth=2, label='拟合曲线')
        
        # 设置图表属性
        self.axes.set_title(title, fontsize=12, fontweight='bold', color=COLORS["primary"])
        self.axes.set_xlabel('X', fontsize=10, fontweight='bold')
        self.axes.set_ylabel('Y', fontsize=10, fontweight='bold')
        self.axes.tick_params(labelsize=9)
        self.axes.grid(True, linestyle='--', alpha=0.7)
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)
        self.axes.legend()
        
        self.fig.tight_layout()
        self.draw()

class FitterDialog(QDialog):
    """拟合功能对话框"""
    def __init__(self, parent=None):
        super(FitterDialog, self).__init__(parent)
        self.setWindowTitle("数据拟合")
        self.resize(900, 700)
        
        # 数据和拟合结果
        self.x_data = None
        self.y_data = None
        self.fit_result = None
        self.fit_params = None
        self.fit_errors = None
        self.fit_bounds = None
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建控制和图表的标签页
        self.tabs = QTabWidget()
        
        # 拟合设置标签页
        self.setup_fit_settings_tab()
        
        # 拟合结果标签页
        self.setup_fit_results_tab()
        
        # 添加标签页到主布局
        self.main_layout.addWidget(self.tabs)
        
        # 添加按钮区域
        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(0, 10, 0, 0)
        
        # 创建拟合按钮
        self.fit_button = QPushButton("执行拟合")
        self.fit_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.fit_button.setMinimumHeight(36)
        self.fit_button.clicked.connect(self.perform_fit)
        
        # 关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.setIcon(QIcon.fromTheme("window-close"))
        self.close_button.setMinimumHeight(36)
        self.close_button.clicked.connect(self.close)
        
        # 将按钮添加到布局
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.fit_button)
        self.button_layout.addWidget(self.close_button)
        
        # 添加按钮布局到主布局
        self.main_layout.addLayout(self.button_layout)
        
        # 初始化模型参数
        self.initialize_models()
        
        # 禁用拟合按钮直到加载数据
        self.fit_button.setEnabled(False)
    
    def setup_fit_settings_tab(self):
        """设置拟合参数标签页"""
        settings_tab = QWidget()
        tab_layout = QVBoxLayout(settings_tab)
        
        # 数据选择和预览区域
        data_group = QGroupBox("数据选择")
        data_layout = QGridLayout()
        
        # 创建通道选择下拉列表
        self.channel_label = QLabel("选择通道:")
        self.channel_combo = QComboBox()
        self.channel_combo.setMinimumWidth(200)
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        
        # 创建数据范围选择
        self.range_label = QLabel("数据范围:")
        self.start_idx_spin = QSpinBox()
        self.start_idx_spin.setRange(0, 1000000)
        self.start_idx_spin.setValue(0)
        self.start_idx_spin.valueChanged.connect(self.on_range_changed)
        
        self.end_idx_spin = QSpinBox()
        self.end_idx_spin.setRange(1, 1000000)
        self.end_idx_spin.setValue(1000)
        self.end_idx_spin.valueChanged.connect(self.on_range_changed)
        
        self.points_label = QLabel("数据点:")
        self.points_value = QLabel("0")
        
        # 创建数据预览绘图区
        self.data_preview = FitPlot()
        
        # 添加控件到网格布局
        data_layout.addWidget(self.channel_label, 0, 0)
        data_layout.addWidget(self.channel_combo, 0, 1, 1, 3)
        
        data_layout.addWidget(self.range_label, 1, 0)
        data_layout.addWidget(QLabel("起始:"), 1, 1)
        data_layout.addWidget(self.start_idx_spin, 1, 2)
        data_layout.addWidget(QLabel("结束:"), 1, 3)
        data_layout.addWidget(self.end_idx_spin, 1, 4)
        
        data_layout.addWidget(self.points_label, 2, 0)
        data_layout.addWidget(self.points_value, 2, 1, 1, 3)
        
        # 添加预览图
        data_layout.addWidget(self.data_preview, 3, 0, 1, 5)
        
        data_group.setLayout(data_layout)
        
        # 拟合模型选择区域
        model_group = QGroupBox("拟合模型")
        model_layout = QVBoxLayout()
        
        # 创建模型选择下拉列表
        model_form = QFormLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "请选择...",
            "线性拟合 (y = a*x + b)",
            "多项式拟合",
            "高斯拟合 (y = a*exp(-((x-b)/c)^2) + d)",
            "指数拟合 (y = a*exp(b*x) + c)",
            "对数拟合 (y = a*ln(x) + b)",
            "幂函数拟合 (y = a*x^b + c)",
            "双曲正切拟合 (y = a*tanh(b*(x-c)) + d)",
            "洛伦兹拟合 (y = a/((x-b)^2 + c) + d)",
            "S型函数拟合 (y = a/(1+exp(-b*(x-c))) + d)"
        ])
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        model_form.addRow("选择模型:", self.model_combo)
        
        # 多项式阶数选择器（初始隐藏）
        self.poly_order_layout = QHBoxLayout()
        self.poly_order_label = QLabel("多项式阶数:")
        self.poly_order_spin = QSpinBox()
        self.poly_order_spin.setRange(1, 10)
        self.poly_order_spin.setValue(2)
        self.poly_order_layout.addWidget(self.poly_order_label)
        self.poly_order_layout.addWidget(self.poly_order_spin)
        self.poly_order_layout.addStretch(1)
        
        # 隐藏多项式阶数选择器
        self.poly_order_label.setVisible(False)
        self.poly_order_spin.setVisible(False)
        
        model_layout.addLayout(model_form)
        model_layout.addLayout(self.poly_order_layout)
        
        # 模型参数区域
        self.params_group = QGroupBox("模型参数")
        self.params_layout = QGridLayout()
        self.params_group.setLayout(self.params_layout)
        self.params_group.setVisible(False)
        
        model_layout.addWidget(self.params_group)
        model_layout.addStretch(1)
        model_group.setLayout(model_layout)
        
        # 将分组添加到标签页布局
        tab_layout.addWidget(data_group, 2)  # 数据预览占用更多空间
        tab_layout.addWidget(model_group, 1)
        
        # 添加到标签页
        self.tabs.addTab(settings_tab, "拟合设置")
    
    def setup_fit_results_tab(self):
        """设置拟合结果标签页"""
        results_tab = QWidget()
        tab_layout = QVBoxLayout(results_tab)
        
        # 结果可视化区域
        viz_group = QGroupBox("拟合结果可视化")
        viz_layout = QVBoxLayout()
        
        # 拟合绘图区
        self.fit_plot = FitPlot()
        self.fit_toolbar = NavigationToolbar(self.fit_plot, self)
        
        viz_layout.addWidget(self.fit_toolbar)
        viz_layout.addWidget(self.fit_plot)
        viz_group.setLayout(viz_layout)
        
        # 拟合参数结果表格
        params_group = QGroupBox("拟合参数")
        params_layout = QVBoxLayout()
        
        self.fit_stats_label = QLabel("拟合统计:")
        self.fit_stats_value = QLabel("尚未执行拟合")
        self.fit_stats_value.setStyleSheet("font-weight: bold;")
        
        self.results_table = FitResultsTable()
        
        # 导出按钮
        export_layout = QHBoxLayout()
        self.export_button = QPushButton("导出结果")
        self.export_button.setIcon(QIcon.fromTheme("document-save"))
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        
        self.copy_button = QPushButton("复制参数")
        self.copy_button.setIcon(QIcon.fromTheme("edit-copy"))
        self.copy_button.clicked.connect(self.copy_params)
        self.copy_button.setEnabled(False)
        
        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.copy_button)
        export_layout.addStretch(1)
        
        params_layout.addWidget(self.fit_stats_label)
        params_layout.addWidget(self.fit_stats_value)
        params_layout.addWidget(self.results_table)
        params_layout.addLayout(export_layout)
        params_group.setLayout(params_layout)
        
        # 将分组添加到标签页布局
        tab_layout.addWidget(viz_group, 3)  # 可视化占用更多空间
        tab_layout.addWidget(params_group, 2)
        
        # 添加到标签页
        self.tabs.addTab(results_tab, "拟合结果")
