#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nanopore Size Calculator - 纳米孔径计算模块
通过I-V曲线拟合来估算纳米孔径
"""

import numpy as np
from scipy import optimize
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
    QFormLayout, QTextEdit, QCheckBox, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class IVPlot(FigureCanvas):
    """I-V曲线绘图区域"""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(IVPlot, self).__init__(self.fig)
        self.setParent(parent)
        
    def plot_iv_curve(self, voltage, current, fit_v=None, fit_i=None, title="I-V Curve"):
        """绘制I-V曲线和拟合结果"""
        self.axes.clear()
        self.axes.scatter(voltage, current, s=20, alpha=0.7, label='Data Points')
        
        if fit_v is not None and fit_i is not None:
            self.axes.plot(fit_v, fit_i, 'r-', linewidth=2, label='Linear Fit')
        
        self.axes.set_title(title)
        self.axes.set_xlabel('Voltage (V)')
        self.axes.set_ylabel('Current (nA)')
        self.axes.grid(True, linestyle='--', alpha=0.7)
        self.axes.legend()
        
        self.fig.tight_layout()
        self.draw()

class NanoporeCalculatorTab(QWidget):
    """纳米孔径计算标签页"""
    def __init__(self, parent=None):
        super(NanoporeCalculatorTab, self).__init__(parent)
        
        # 初始化数据
        self.data = None
        self.voltage_data = None
        self.current_data = None
        self.parent_dialog = parent
        
        # 设置布局
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        
        # 顶部区域：数据选择和参数设置
        top_layout = QHBoxLayout()
        
        # 左侧：通道选择
        channel_group = QGroupBox("Channel Selection")
        channel_layout = QFormLayout(channel_group)
        
        self.voltage_channel_combo = QComboBox()
        self.current_channel_combo = QComboBox()
        
        channel_layout.addRow("Voltage Channel:", self.voltage_channel_combo)
        channel_layout.addRow("Current Channel:", self.current_channel_combo)
        
        # 反转电压/电流复选框
        self.invert_voltage_check = QCheckBox("Invert Voltage")
        self.invert_current_check = QCheckBox("Invert Current")
        
        channel_layout.addRow("", self.invert_voltage_check)
        channel_layout.addRow("", self.invert_current_check)
        
        # 自动切换电流单位（pA到nA）
        self.auto_scale_check = QCheckBox("Auto-scale Current (pA → nA)")
        self.auto_scale_check.setChecked(True)
        channel_layout.addRow("", self.auto_scale_check)
        
        # 右侧：孔径计算参数
        params_group = QGroupBox("Nanopore Parameters")
        params_layout = QFormLayout(params_group)
        
        # 电解质溶液电导率
        self.conductivity_spin = QDoubleSpinBox()
        self.conductivity_spin.setRange(0.01, 20)
        self.conductivity_spin.setValue(10.5)  # 默认为KCl溶液的电导率
        self.conductivity_spin.setSuffix(" S/m")
        self.conductivity_spin.setDecimals(2)
        params_layout.addRow("Solution Conductivity:", self.conductivity_spin)
        
        # 纳米孔长度
        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(1, 10000)
        self.length_spin.setValue(100)  # 默认100 nm
        self.length_spin.setSuffix(" nm")
        params_layout.addRow("Nanopore Length:", self.length_spin)
        
        # 模型选择
        model_group = QButtonGroup(self)
        cylindrical_radio = QRadioButton("Cylindrical Pore")
        conical_radio = QRadioButton("Conical Pore")
        cylindrical_radio.setChecked(True)
        model_group.addButton(cylindrical_radio, 1)
        model_group.addButton(conical_radio, 2)
        
        model_layout = QVBoxLayout()
        model_layout.addWidget(cylindrical_radio)
        model_layout.addWidget(conical_radio)
        
        params_layout.addRow("Pore Model:", model_layout)
        
        # 添加锥形孔的顶角参数（当选择锥形孔时启用）
        self.cone_angle_spin = QDoubleSpinBox()
        self.cone_angle_spin.setRange(1, 180)
        self.cone_angle_spin.setValue(30)  # 默认30度
        self.cone_angle_spin.setSuffix(" degrees")
        self.cone_angle_spin.setEnabled(False)
        params_layout.addRow("Cone Half-Angle:", self.cone_angle_spin)
        
        # 连接锥形孔按钮和角度参数启用状态
        conical_radio.toggled.connect(lambda checked: self.cone_angle_spin.setEnabled(checked))
        
        # 将模型按钮组保存为成员变量
        self.model_group = model_group
        
        # 计算按钮
        calculate_layout = QHBoxLayout()
        self.calculate_btn = QPushButton("Calculate Nanopore Size")
        self.calculate_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px;")
        self.calculate_btn.clicked.connect(self.calculate_nanopore_size)
        calculate_layout.addStretch(1)
        calculate_layout.addWidget(self.calculate_btn)
        
        # 添加到顶部布局
        top_layout.addWidget(channel_group)
        top_layout.addWidget(params_group)
        
        # 中间区域：I-V曲线图表
        plot_group = QGroupBox("I-V Curve")
        plot_layout = QVBoxLayout(plot_group)
        
        self.iv_plot = IVPlot(self)
        self.iv_toolbar = NavigationToolbar(self.iv_plot, self)
        
        plot_layout.addWidget(self.iv_toolbar)
        plot_layout.addWidget(self.iv_plot)
        
        # 底部区域：计算结果
        result_group = QGroupBox("Calculation Results")
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(100)
        
        result_layout.addWidget(self.result_text)
        
        # 将所有组件添加到主布局
        layout.addLayout(top_layout)
        layout.addLayout(calculate_layout)
        layout.addWidget(plot_group)
        layout.addWidget(result_group)
    
    def set_data(self, data):
        """设置数据"""
        self.data = data
        self.populate_channel_combos()
    
    def populate_channel_combos(self):
        """填充通道下拉菜单"""
        # 清空当前选项
        self.voltage_channel_combo.clear()
        self.current_channel_combo.clear()
        
        if self.data is None:
            return
        
        # 添加通道到下拉菜单
        if isinstance(self.data, dict):
            channels = list(self.data.keys())
            self.voltage_channel_combo.addItems(channels)
            self.current_channel_combo.addItems(channels)
            
            # 如果存在至少两个通道，默认第一个为电压，第二个为电流
            if len(channels) >= 2:
                self.voltage_channel_combo.setCurrentIndex(0)
                self.current_channel_combo.setCurrentIndex(1)
            
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim > 1:
                channels = [f"Channel {i+1}" for i in range(self.data.shape[1])]
                self.voltage_channel_combo.addItems(channels)
                self.current_channel_combo.addItems(channels)
                
                # 如果存在至少两个通道，默认第一个为电压，第二个为电流
                if len(channels) >= 2:
                    self.voltage_channel_combo.setCurrentIndex(0)
                    self.current_channel_combo.setCurrentIndex(1)
            else:
                # 单通道数据
                self.voltage_channel_combo.addItem("Channel 1")
                self.current_channel_combo.addItem("Channel 1")
    
    def get_channel_data(self, combo):
        """获取选定通道的数据"""
        if self.data is None:
            return None
            
        channel = combo.currentText()
        
        if isinstance(self.data, dict) and channel in self.data:
            return self.data[channel]
        elif isinstance(self.data, np.ndarray):
            if self.data.ndim > 1:
                channel_idx = int(channel.split(" ")[1]) - 1
                if channel_idx < self.data.shape[1]:
                    return self.data[:, channel_idx]
            else:
                return self.data
        
        return None

    def calculate_nanopore_size(self):
        """计算纳米孔径"""
        # 获取电压和电流数据
        voltage_data = self.get_channel_data(self.voltage_channel_combo)
        current_data = self.get_channel_data(self.current_channel_combo)
        
        if voltage_data is None or current_data is None:
            QMessageBox.warning(self, "Error", "Please select valid voltage and current channels")
            return
        
        # 确保数据长度相同
        if len(voltage_data) != len(current_data):
            QMessageBox.warning(self, "Error", "Voltage and current data must have the same length")
            return
        
        # 反转数据，如果需要
        if self.invert_voltage_check.isChecked():
            voltage_data = -voltage_data
        
        if self.invert_current_check.isChecked():
            current_data = -current_data
        
        # 自动缩放电流（假设单位从pA转换为nA）
        if self.auto_scale_check.isChecked() and np.max(np.abs(current_data)) > 100:
            current_data = current_data / 1000  # pA 到 nA
            scaling_info = " (auto-scaled from pA to nA)"
        else:
            scaling_info = ""
        
        try:
            # 执行线性拟合 (I = G*V + b)
            popt, pcov = optimize.curve_fit(lambda x, g, b: g*x + b, voltage_data, current_data)
            conductance, offset = popt
            
            # 计算误差
            perr = np.sqrt(np.diag(pcov))
            conductance_err, offset_err = perr
            
            # 计算R²和RMSE
            fit_current = conductance * voltage_data + offset
            residuals = current_data - fit_current
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((current_data - np.mean(current_data))**2)
            r_squared = 1 - (ss_res / ss_tot)
            rmse = np.sqrt(np.mean(residuals**2))
            
            # 绘制I-V曲线和拟合结果
            fit_voltage = np.linspace(min(voltage_data), max(voltage_data), 1000)
            fit_current = conductance * fit_voltage + offset
            
            self.iv_plot.plot_iv_curve(
                voltage_data, current_data, 
                fit_voltage, fit_current, 
                title=f"I-V Curve & Linear Fit (G = {conductance:.4g} nS)"
            )
            
            # 转换电导单位 (nA/V = nS)
            conductance_ns = conductance  # 已经是nS
            conductance_s = conductance_ns * 1e-9  # 转换为S (西门子)
            
            # 从电导计算孔径
            # 获取参数
            solution_conductivity = self.conductivity_spin.value()  # S/m
            pore_length = self.length_spin.value() * 1e-9  # 从nm转换为m
            
            selected_model = self.model_group.checkedId()
            
            if selected_model == 1:  # 圆柱形孔
                # 使用公式: G = σ·(πr²/L)
                # 解出r = √(G·L/(σ·π))
                pore_radius = np.sqrt(conductance_s * pore_length / (solution_conductivity * np.pi))
                pore_diameter = 2 * pore_radius
                
                # 转换为nm显示
                pore_radius_nm = pore_radius * 1e9
                pore_diameter_nm = pore_diameter * 1e9
                
                # 误差传播 (简化版)
                radius_err_nm = 0.5 * (conductance_err / conductance) * pore_radius_nm
                
                # 结果文本
                result_text = "=== I-V Curve Linear Fit ===\n"
                result_text += f"Conductance (G): {conductance_ns:.4g} ± {conductance_err*1e9:.2g} nS{scaling_info}\n"
                result_text += f"Offset (b): {offset:.4g} ± {offset_err:.2g} nA\n"
                result_text += f"R²: {r_squared:.4f}\n\n"
                
                result_text += "=== Nanopore Size Calculation ===\n"
                result_text += f"Model: Cylindrical pore\n"
                result_text += f"Solution conductivity: {solution_conductivity:.2f} S/m\n"
                result_text += f"Pore length: {self.length_spin.value():.1f} nm\n\n"
                
                result_text += f"Pore radius: {pore_radius_nm:.2f} ± {radius_err_nm:.2f} nm\n"
                result_text += f"Pore diameter: {pore_diameter_nm:.2f} ± {radius_err_nm*2:.2f} nm\n"
                
            else:  # 锥形孔
                # 使用公式: G = 2σ·π·r·tg(θ)/ln(L·tg(θ)/r + 1)
                # 这里我们使用近似解，假设锥孔较长
                
                cone_angle_rad = np.radians(self.cone_angle_spin.value())
                tan_angle = np.tan(cone_angle_rad)
                
                # 近似公式: G ≈ πσ·r²/L·α，其中α是形状因子
                # 对于锥形孔，α取决于角度和长度
                shape_factor = 4 / tan_angle
                
                pore_radius = np.sqrt(conductance_s * pore_length * shape_factor / (solution_conductivity * np.pi))
                pore_diameter = 2 * pore_radius
                
                # 转换为nm显示
                pore_radius_nm = pore_radius * 1e9
                pore_diameter_nm = pore_diameter * 1e9
                
                # 误差传播 (简化版)
                radius_err_nm = 0.5 * (conductance_err / conductance) * pore_radius_nm
                
                # 计算锥孔顶部和底部半径
                tip_radius_nm = pore_radius_nm
                base_radius_nm = tip_radius_nm + pore_length * 1e9 * tan_angle
                
                # 结果文本
                result_text = "=== I-V Curve Linear Fit ===\n"
                result_text += f"Conductance (G): {conductance_ns:.4g} ± {conductance_err*1e9:.2g} nS{scaling_info}\n"
                result_text += f"Offset (b): {offset:.4g} ± {offset_err:.2g} nA\n"
                result_text += f"R²: {r_squared:.4f}\n\n"
                
                result_text += "=== Nanopore Size Calculation ===\n"
                result_text += f"Model: Conical pore\n"
                result_text += f"Solution conductivity: {solution_conductivity:.2f} S/m\n"
                result_text += f"Pore length: {self.length_spin.value():.1f} nm\n"
                result_text += f"Cone half-angle: {self.cone_angle_spin.value():.1f}°\n\n"
                
                result_text += f"Tip radius: {tip_radius_nm:.2f} ± {radius_err_nm:.2f} nm\n"
                result_text += f"Tip diameter: {tip_radius_nm*2:.2f} ± {radius_err_nm*2:.2f} nm\n"
                result_text += f"Base radius: {base_radius_nm:.2f} nm\n"
            
            # 显示结果
            self.result_text.setText(result_text)
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error occurred during calculation:\n{str(e)}")
