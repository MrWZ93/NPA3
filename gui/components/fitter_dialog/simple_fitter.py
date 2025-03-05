#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版拟合功能对话框
"""

import numpy as np
from scipy import optimize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QComboBox, QPushButton, QTabWidget, QWidget,
    QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QCoreApplication

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# 导入nanopore计算器
from .nanopore_calculator import NanoporeCalculatorTab

class FitPlot(FigureCanvas):
    """拟合结果绘图区域"""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(FitPlot, self).__init__(self.fig)
        self.setParent(parent)
        
    def plot_data(self, x_data, y_data, fit_x=None, fit_y=None, title="Data Fitting"):
        """绘制数据和拟合曲线"""
        self.axes.clear()
        self.axes.scatter(x_data, y_data, s=20, alpha=0.7, label='Data Points')
        
        if fit_x is not None and fit_y is not None:
            self.axes.plot(fit_x, fit_y, 'r-', linewidth=2, label='Fitted Curve')
        
        self.axes.set_title(title)
        self.axes.set_xlabel('X')
        self.axes.set_ylabel('Y')
        self.axes.grid(True, linestyle='--', alpha=0.7)
        self.axes.legend()
        
        self.fig.tight_layout()
        self.draw()

class SimpleFitterDialog(QDialog):
    """简化版拟合对话框"""
    def __init__(self, parent=None):
        super(SimpleFitterDialog, self).__init__(parent)
        self.setWindowTitle("Curve Fitting")
        self.resize(800, 600)
        
        # 初始化数据
        self.data = None
        self.x_data = None
        self.y_data = None
        
        # 主布局
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 设置标签页
        self.setup_tabs()
        
        # 添加到布局
        layout.addWidget(self.tabs)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.fit_button = QPushButton("Perform Fit")
        self.fit_button.clicked.connect(self.perform_fit)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.fit_button)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def setup_tabs(self):
        """设置标签页"""
        # 数据选择标签页
        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        
        # 通道选择
        channel_group = QGroupBox("Data Selection")
        channel_layout = QVBoxLayout(channel_group)
        
        self.channel_combo = QComboBox()
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        
        channel_layout.addWidget(QLabel("Select Channel:"))
        channel_layout.addWidget(self.channel_combo)
        
        # 模型选择
        model_group = QGroupBox("Fitting Model")
        model_layout = QVBoxLayout(model_group)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Linear Fit (y = a*x + b)",
            "Polynomial Fit (2nd order)",
            "Gaussian Fit",
            "Exponential Fit"
        ])
        
        model_layout.addWidget(QLabel("Select Model:"))
        model_layout.addWidget(self.model_combo)
        
        # 数据预览
        preview_group = QGroupBox("Data Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.data_plot = FitPlot()
        preview_layout.addWidget(self.data_plot)
        
        # 添加到布局
        data_layout.addWidget(channel_group)
        data_layout.addWidget(model_group)
        data_layout.addWidget(preview_group)
        
        # 结果标签页
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        
        self.result_plot = FitPlot()
        self.result_toolbar = NavigationToolbar(self.result_plot, self)
        
        # 创建结果详情区域
        result_details_group = QGroupBox("Fitting Details")
        details_layout = QVBoxLayout(result_details_group)
        
        # 使用文本框显示详细结果
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(150)
        details_layout.addWidget(self.result_text)
        
        # 添加复制结果按钮
        copy_button = QPushButton("Copy Results")
        copy_button.clicked.connect(self.copy_results)
        details_layout.addWidget(copy_button)
        
        result_layout.addWidget(self.result_toolbar)
        result_layout.addWidget(self.result_plot)
        result_layout.addWidget(result_details_group)
        
        # 添加标签页
        self.tabs.addTab(data_tab, "Data Selection")
        self.tabs.addTab(result_tab, "Fitting Results")
        
        # 添加纳米孔计算器标签页
        self.nanopore_tab = NanoporeCalculatorTab(self)
        self.tabs.addTab(self.nanopore_tab, "Nanopore Size")
    
    def set_data(self, data):
        """设置数据"""
        self.data = data
        self.channel_combo.clear()
        
        if isinstance(data, dict):
            # 如果是字典，添加所有键作为通道
            self.channel_combo.addItems(list(data.keys()))
        elif isinstance(data, np.ndarray):
            # 如果是数组，添加通道索引
            channels = [f"Channel {i+1}" for i in range(data.shape[1] if data.ndim > 1 else 1)]
            self.channel_combo.addItems(channels)
        
        # 为纳米孔计算器标签页设置数据
        self.nanopore_tab.set_data(data)
    
    def on_channel_changed(self, index):
        """通道变更处理"""
        if index < 0 or self.data is None:
            return
        
        channel = self.channel_combo.currentText()
        
        if isinstance(self.data, dict) and channel in self.data:
            self.y_data = self.data[channel]
            self.x_data = np.arange(len(self.y_data))
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim > 1:
                channel_idx = int(channel.split(" ")[1]) - 1
                self.y_data = self.data[:, channel_idx]
            else:
                self.y_data = self.data
            self.x_data = np.arange(len(self.y_data))
        
        # 更新预览
        self.data_plot.plot_data(self.x_data, self.y_data, title="Data Preview")
    
    def copy_results(self):
        """复制拟合结果到剪贴板"""
        if self.result_text.toPlainText():
            QCoreApplication.instance().clipboard().setText(self.result_text.toPlainText())
            QMessageBox.information(self, "Information", "Results copied to clipboard")
    
    def perform_fit(self):
        """执行拟合"""
        if self.x_data is None or self.y_data is None:
            QMessageBox.warning(self, "Error", "Please select a data channel first")
            return
        
        model_name = self.model_combo.currentText()
        
        try:
            if "Linear Fit" in model_name:
                # 线性拟合 y = a*x + b
                popt, pcov = optimize.curve_fit(lambda x, a, b: a*x + b, self.x_data, self.y_data)
                a, b = popt
                
                # 计算误差
                perr = np.sqrt(np.diag(pcov))
                a_err, b_err = perr
                
                # 计算R^2和RMSE
                fit_y = a * self.x_data + b
                residuals = self.y_data - fit_y
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((self.y_data - np.mean(self.y_data))**2)
                r_squared = 1 - (ss_res / ss_tot)
                rmse = np.sqrt(np.mean(residuals**2))
                
                # 生成拟合曲线
                fit_x = np.linspace(min(self.x_data), max(self.x_data), 1000)
                fit_y = a * fit_x + b
                
                # 显示结果
                self.result_plot.plot_data(self.x_data, self.y_data, fit_x, fit_y, title="Linear Fit")
                
                # 详细结果
                result_text = f"Model: Linear Fit (y = a*x + b)\n\n"
                result_text += f"Parameters:\n"
                result_text += f"a = {a:.6g} ± {a_err:.6g}\n"
                result_text += f"b = {b:.6g} ± {b_err:.6g}\n\n"
                result_text += f"Equation: y = {a:.6g}x + {b:.6g}\n\n"
                result_text += f"Statistics:\n"
                result_text += f"R² = {r_squared:.6f}\n"
                result_text += f"RMSE = {rmse:.6g}\n"
                result_text += f"Sum of Squared Residuals = {ss_res:.6g}\n"
                
                self.result_text.setText(result_text)
                
            elif "Polynomial Fit" in model_name:
                # 多项式拟合（2阶）
                popt = np.polyfit(self.x_data, self.y_data, 2)
                a, b, c = popt
                
                # 计算协方差矩阵
                residuals = np.polyval(popt, self.x_data) - self.y_data
                var_res = np.sum(residuals**2) / (len(self.x_data) - 3)
                # Covariance matrix calculation
                X = np.vander(self.x_data, 3)
                cov = var_res * np.linalg.inv(X.T @ X)
                perr = np.sqrt(np.diag(cov))
                
                # 计算R^2和RMSE
                fit_y = np.polyval(popt, self.x_data)
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((self.y_data - np.mean(self.y_data))**2)
                r_squared = 1 - (ss_res / ss_tot)
                rmse = np.sqrt(np.mean(residuals**2))
                
                # 生成拟合曲线
                fit_x = np.linspace(min(self.x_data), max(self.x_data), 1000)
                fit_y = a * fit_x**2 + b * fit_x + c
                
                # 显示结果
                self.result_plot.plot_data(self.x_data, self.y_data, fit_x, fit_y, title="Polynomial Fit")
                
                # 详细结果
                result_text = f"Model: Polynomial Fit (y = ax² + bx + c)\n\n"
                result_text += f"Parameters:\n"
                result_text += f"a = {a:.6g} ± {perr[0]:.6g}\n"
                result_text += f"b = {b:.6g} ± {perr[1]:.6g}\n"
                result_text += f"c = {c:.6g} ± {perr[2]:.6g}\n\n"
                result_text += f"Equation: y = {a:.6g}x² + {b:.6g}x + {c:.6g}\n\n"
                result_text += f"Statistics:\n"
                result_text += f"R² = {r_squared:.6f}\n"
                result_text += f"RMSE = {rmse:.6g}\n"
                result_text += f"Sum of Squared Residuals = {ss_res:.6g}\n"
                
                self.result_text.setText(result_text)
                
            elif "Gaussian Fit" in model_name:
                # 高斯拟合 y = a * exp(-((x-b)/c)^2) + d
                def gaussian(x, a, b, c, d):
                    return a * np.exp(-((x-b)/c)**2) + d
                
                # 初始猜测参数
                p0 = [
                    max(self.y_data) - min(self.y_data),  # 振幅
                    self.x_data[np.argmax(self.y_data)],  # 中心位置
                    (max(self.x_data) - min(self.x_data))/10,  # 宽度
                    min(self.y_data)  # 偏移
                ]
                
                popt, pcov = optimize.curve_fit(gaussian, self.x_data, self.y_data, p0=p0)
                a, b, c, d = popt
                
                # 计算误差
                perr = np.sqrt(np.diag(pcov))
                a_err, b_err, c_err, d_err = perr
                
                # 计算R^2和RMSE
                fit_y = gaussian(self.x_data, *popt)
                residuals = self.y_data - fit_y
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((self.y_data - np.mean(self.y_data))**2)
                r_squared = 1 - (ss_res / ss_tot)
                rmse = np.sqrt(np.mean(residuals**2))
                
                # 生成拟合曲线
                fit_x = np.linspace(min(self.x_data), max(self.x_data), 1000)
                fit_y = gaussian(fit_x, a, b, c, d)
                
                # 显示结果
                self.result_plot.plot_data(self.x_data, self.y_data, fit_x, fit_y, title="Gaussian Fit")
                
                # 详细结果
                result_text = f"Model: Gaussian Fit (y = a*exp(-((x-b)/c)²) + d)\n\n"
                result_text += f"Parameters:\n"
                result_text += f"a (amplitude) = {a:.6g} ± {a_err:.6g}\n"
                result_text += f"b (center) = {b:.6g} ± {b_err:.6g}\n"
                result_text += f"c (width) = {c:.6g} ± {c_err:.6g}\n"
                result_text += f"d (offset) = {d:.6g} ± {d_err:.6g}\n\n"
                result_text += f"Equation: y = {a:.6g}*exp(-((x-{b:.6g})/{c:.6g})²) + {d:.6g}\n\n"
                result_text += f"Statistics:\n"
                result_text += f"R² = {r_squared:.6f}\n"
                result_text += f"RMSE = {rmse:.6g}\n"
                result_text += f"Sum of Squared Residuals = {ss_res:.6g}\n"
                
                self.result_text.setText(result_text)
                
            elif "Exponential Fit" in model_name:
                # 指数拟合 y = a * exp(b*x) + c
                def exponential(x, a, b, c):
                    return a * np.exp(b * x) + c
                
                # 初始猜测
                p0 = [1.0, 0.1, 0.0]
                
                popt, pcov = optimize.curve_fit(exponential, self.x_data, self.y_data, p0=p0)
                a, b, c = popt
                
                # 计算误差
                perr = np.sqrt(np.diag(pcov))
                a_err, b_err, c_err = perr
                
                # 计算R^2和RMSE
                fit_y = exponential(self.x_data, *popt)
                residuals = self.y_data - fit_y
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((self.y_data - np.mean(self.y_data))**2)
                r_squared = 1 - (ss_res / ss_tot)
                rmse = np.sqrt(np.mean(residuals**2))
                
                # 生成拟合曲线
                fit_x = np.linspace(min(self.x_data), max(self.x_data), 1000)
                fit_y = exponential(fit_x, a, b, c)
                
                # 显示结果
                self.result_plot.plot_data(self.x_data, self.y_data, fit_x, fit_y, title="Exponential Fit")
                
                # 详细结果
                result_text = f"Model: Exponential Fit (y = a*exp(b*x) + c)\n\n"
                result_text += f"Parameters:\n"
                result_text += f"a (amplitude) = {a:.6g} ± {a_err:.6g}\n"
                result_text += f"b (rate) = {b:.6g} ± {b_err:.6g}\n"
                result_text += f"c (offset) = {c:.6g} ± {c_err:.6g}\n\n"
                result_text += f"Equation: y = {a:.6g}*exp({b:.6g}*x) + {c:.6g}\n\n"
                result_text += f"Statistics:\n"
                result_text += f"R² = {r_squared:.6f}\n"
                result_text += f"RMSE = {rmse:.6g}\n"
                result_text += f"Sum of Squared Residuals = {ss_res:.6g}\n"
                
                self.result_text.setText(result_text)
            
            # 切换到结果标签页
            self.tabs.setCurrentIndex(1)
            
        except Exception as e:
            QMessageBox.critical(self, "Fitting Error", f"Error occurred during fitting:\n{str(e)}")
