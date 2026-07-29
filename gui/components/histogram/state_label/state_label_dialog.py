#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Label Dialog - 直方图 HMM 状态标记与分析窗口
从 Histogram 窗口左侧按钮触发，支持高斯拟合自动提取、采样率与滤波配置、HMM 状态解码与可视化
"""

import os
import time
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QGroupBox, QWidget, QFrame, QSplitter, QSpinBox, QDoubleSpinBox,
                            QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox, QFormLayout, QCheckBox, QFileDialog, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QColor
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from gui.styles import COLORS, StyleHelper
from .state_label_plot import StateLabelPlot
from .hmm_engine import HMMStateAnalyzer
from .exporter import StateLabelExporter


class StateLabelDialog(QDialog):
    """Histogram State Label 分析窗口 - 支持高斯拟合自动导入、低通滤波与 HMM 解码"""
    
    def __init__(self, parent=None):
        super(StateLabelDialog, self).__init__(parent)
        self.setWindowTitle("State Label - HMM State Analysis & Parameter Settings")
        self.resize(1150, 720)
        
        # 设置窗口标志为非模态独立窗口
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self.parent_dialog = parent
        self.main_plot = None
        self.current_params = []
        self.param_source_str = "Auto-Guessed"
        
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI 界面（三栏清爽布局：左侧参数控制，中间图表专区，右侧参数表与分析结果）"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        
        # 创建 3 列水平分割器（左侧：配置控制，中间：图形绘制，右侧：参数表与分析结果）
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 1. 左侧配置控制面板
        left_panel = self._build_left_control_panel()
        self.main_splitter.addWidget(left_panel)
        
        # 2. 中间图表展示区域
        center_panel = self._build_center_plot_panel()
        self.main_splitter.addWidget(center_panel)
        
        # 3. 右侧参数表与分析结果面板
        right_panel = self._build_right_results_panel()
        self.main_splitter.addWidget(right_panel)
        
        # 设置分割器初始尺寸比例 (260px, 680px, 340px)
        self.main_splitter.setSizes([260, 680, 340])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        
        main_layout.addWidget(self.main_splitter, 1)
        
    def _build_left_control_panel(self):
        """构建左侧参数控制面板：包含采样率、高级 HMM 参数、状态数目设置与运行按钮"""
        panel = QWidget()
        panel.setMinimumWidth(250)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)
        
        # A. 采样率设置组 (Sampling Rate)
        proc_group = QGroupBox("Sampling Rate Settings")
        proc_form = QFormLayout(proc_group)
        proc_form.setSpacing(6)
        
        self.sr_spin = QDoubleSpinBox()
        self.sr_spin.setRange(0.1, 10000000.0)
        self.sr_spin.setDecimals(1)
        self.sr_spin.setSingleStep(100.0)
        self.sr_spin.setValue(1000.0)
        self.sr_spin.setSuffix(" Hz")
        self.sr_spin.setToolTip("Active sampling rate used for time and dwell duration calculations")
        proc_form.addRow("Sampling Rate (fs):", self.sr_spin)
        
        layout.addWidget(proc_group)
        
        # B. 高级 HMM 算法控制参数组 (Advanced HMM Parameters Controls)
        algo_group = QGroupBox("Advanced HMM Controls")
        algo_form = QFormLayout(algo_group)
        algo_form.setSpacing(6)
        
        # 1. 期望平均停留时间 (Expected Dwell Time, expected_dwell_ms)
        self.expected_dwell_spin = QDoubleSpinBox()
        self.expected_dwell_spin.setRange(0.01, 1000.0)
        self.expected_dwell_spin.setDecimals(2)
        self.expected_dwell_spin.setSingleStep(0.2)
        self.expected_dwell_spin.setValue(1.0)
        self.expected_dwell_spin.setSuffix(" ms")
        self.expected_dwell_spin.setToolTip(
            "Expected Dwell Time (τ ms): 期望平均停留时间(ms)。\n"
            "物理含义：决定状态保持的自转移惯性。\n"
            "• 调大（如 2.0 ms）：惯性更强，防止噪声引起误跳变\n"
            "• 调小（如 0.2 ms）：对微弱快速跳跃更敏感"
        )
        algo_form.addRow("Exp. Dwell (τ):", self.expected_dwell_spin)
        
        # 2. 跨级跳跃衰减惩罚 (Jump Decay, jump_decay)
        self.jump_decay_spin = QDoubleSpinBox()
        self.jump_decay_spin.setRange(0.0, 10.0)
        self.jump_decay_spin.setDecimals(1)
        self.jump_decay_spin.setSingleStep(0.5)
        self.jump_decay_spin.setValue(2.0)
        self.jump_decay_spin.setToolTip(
            "Jump Decay Penalty (λ): 跨级跳跃衰减惩罚强度。\n"
            "物理含义：控制 P(i->j) 随状态等级跨度 |i-j| 的指数衰减。\n"
            "• 调大（如 3.0）：强力惩罚跨级跃迁，必须逐级顺序切换\n"
            "• 调小（如 0.5）：允许直接跨跃多个电平状态"
        )
        algo_form.addRow("Jump Decay (λ):", self.jump_decay_spin)
        
        # 3. 最短有效事件持续时间 (Min Dwell Time, min_dwell_ms)
        self.min_dwell_spin = QDoubleSpinBox()
        self.min_dwell_spin.setRange(0.0, 100.0)
        self.min_dwell_spin.setDecimals(2)
        self.min_dwell_spin.setSingleStep(0.05)
        self.min_dwell_spin.setValue(0.25)
        self.min_dwell_spin.setSuffix(" ms")
        self.min_dwell_spin.setToolTip(
            "Min Dwell Time (Tmin ms): 最短有效事件持续时间(ms)。\n"
            "物理含义：判定为真实独立台阶的硬性最小时间门槛。\n"
            "• 调大（如 0.5 ms）：强力滤除低于此时间的所有微短单点毛刺\n"
            "• 设为 0 ms：关闭假事件合并，保留全部单点跳动"
        )
        algo_form.addRow("Min Dwell (Tmin):", self.min_dwell_spin)
        
        # 4. 标准差限制上限比例 (Max Sigma Fraction, max_sigma_fraction)
        self.max_sigma_frac_spin = QDoubleSpinBox()
        self.max_sigma_frac_spin.setRange(0.05, 2.0)
        self.max_sigma_frac_spin.setDecimals(2)
        self.max_sigma_frac_spin.setSingleStep(0.05)
        self.max_sigma_frac_spin.setValue(0.45)
        self.max_sigma_frac_spin.setToolTip(
            "Max Sigma Fraction: 标准差限制上限比例。\n"
            "物理含义：限制状态有效 σ <= 该比例 × 相邻状态间距。\n"
            "• 调小（如 0.25）：边界极严格，防止宽 σ 状态吞噬过渡点\n"
            "• 调大（如 0.80）：允许状态吸收更大范围的幅值波动"
        )
        algo_form.addRow("Max Sigma Frac:", self.max_sigma_frac_spin)
        
        layout.addWidget(algo_group)
        
        # C. 状态设置与拟合结果提取组
        settings_group = QGroupBox("HMM State Configuration")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(6)
        
        states_count_layout = QHBoxLayout()
        states_count_layout.addWidget(QLabel("Number of States (K):"))
        
        self.num_states_spin = QSpinBox()
        self.num_states_spin.setRange(2, 50)
        self.num_states_spin.setValue(2)
        self.num_states_spin.valueChanged.connect(self._on_num_states_changed)
        states_count_layout.addWidget(self.num_states_spin)
        states_count_layout.addStretch()
        
        settings_layout.addLayout(states_count_layout)
        
        # 按钮组：高斯拟合提取 vs 按数据估计
        btns_row = QHBoxLayout()
        
        self.import_fit_btn = QPushButton("Import from Gaussian Fits")
        self.import_fit_btn.setToolTip("Automatically import state Mean (μ) and Std (σ) from Histogram Gaussian Fit Results")
        self.import_fit_btn.setStyleSheet(f"background-color: #27ae60; color: white; font-weight: bold;")
        self.import_fit_btn.clicked.connect(self.import_from_gaussian_fits)
        btns_row.addWidget(self.import_fit_btn)
        
        self.auto_guess_btn = QPushButton("Auto-Guess (μ, σ)")
        self.auto_guess_btn.setToolTip("Estimate mean and std based on percentiles")
        self.auto_guess_btn.clicked.connect(self.auto_guess_parameters)
        btns_row.addWidget(self.auto_guess_btn)
        
        settings_layout.addLayout(btns_row)
        
        # 状态来源标注 Label
        self.param_source_label = QLabel("Source: Auto-Guessed")
        self.param_source_label.setStyleSheet("color: #7f8c8d; font-size: 8.5pt; font-style: italic;")
        settings_layout.addWidget(self.param_source_label)
        
        layout.addWidget(settings_group)
        
        # D. 显示控制选项 (Show HMM State Level Checkbox)
        disp_layout = QHBoxLayout()
        disp_layout.setContentsMargins(2, 2, 2, 2)
        
        self.show_state_level_chk = QCheckBox("Show HMM State Level Overlay")
        self.show_state_level_chk.setToolTip("Toggle on/off the HMM state step line overlay to compare directly with raw data")
        self.show_state_level_chk.setChecked(True)
        self.show_state_level_chk.toggled.connect(self._on_toggle_state_level)
        disp_layout.addWidget(self.show_state_level_chk)
        disp_layout.addStretch()
        
        layout.addLayout(disp_layout)
        
        # E. 执行 HMM 分析按钮
        self.run_hmm_btn = QPushButton("Run HMM State Analysis")
        self.run_hmm_btn.setMinimumHeight(42)
        self.run_hmm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['secondary']};
                color: white;
                font-weight: bold;
                font-size: 10.5pt;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)
        self.run_hmm_btn.clicked.connect(self.run_hmm_analysis)
        layout.addWidget(self.run_hmm_btn)
        layout.addStretch()
        
        return panel

    def _build_center_plot_panel(self):
        """构建中间图形与工具栏展示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        
        # 1. 顶部 Header / 状态栏
        header_group = QGroupBox("State Label - Highlighted Region Focus")
        header_layout = QHBoxLayout(header_group)
        header_layout.setContentsMargins(10, 6, 10, 6)
        
        self.info_label = QLabel("Data Source: Not synchronized")
        self.info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.info_label.setStyleSheet(f"color: {COLORS['primary']};")
        
        header_layout.addWidget(self.info_label)
        header_layout.addStretch(1)
        
        layout.addWidget(header_group)
        
        # 2. 画布与工具栏
        self.plot_canvas = StateLabelPlot(self, width=10, height=7)
        self.toolbar = NavigationToolbar(self.plot_canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.plot_canvas, 1)
        
        # 3. 底部按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        
        sync_btn = QPushButton("Sync from Main View")
        sync_btn.setIcon(QIcon.fromTheme("view-refresh"))
        sync_btn.clicked.connect(self.sync_from_parent)
        btn_layout.addWidget(sync_btn)
        
        export_btn = QPushButton("Export Results & Plot")
        export_btn.setIcon(QIcon.fromTheme("document-save"))
        export_btn.setToolTip("Export raw data, HMM state level trace, statistics CSV/summary, and high-res plot image into a designated folder")
        export_btn.setStyleSheet(f"background-color: #27ae60; color: white; font-weight: bold; padding: 5px 14px;")
        export_btn.clicked.connect(self.export_analysis_results)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch(1)
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        return panel

    def _build_right_results_panel(self):
        """构建右侧状态参数表格与分析结果显示面板"""
        panel = QWidget()
        panel.setMinimumWidth(320)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)
        
        # 1. 状态参数表格 (Mean μ & Std Dev σ)
        params_group = QGroupBox("State Parameters (Mean μ & Std Dev σ)")
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(6, 6, 6, 6)
        
        self.params_table = QTableWidget()
        self.params_table.setColumnCount(3)
        self.params_table.setHorizontalHeaderLabels(["State", "Mean (μ)", "Std Dev (σ)"])
        self.params_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.params_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.params_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.setMinimumHeight(140)
        
        params_layout.addWidget(self.params_table)
        layout.addWidget(params_group)
        
        # 2. 统计分析结果与转换速率矩阵面板
        stats_group = QGroupBox("Analysis Results & Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(6, 6, 6, 6)
        
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        self.stats_display.setPlaceholderText("HMM analysis results and transition rates matrix will appear here after execution...")
        self.stats_display.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                font-family: Arial;
                font-size: 9.5pt;
            }
        """)
        stats_layout.addWidget(self.stats_display)
        layout.addWidget(stats_group, 1)
        
        # 初始化表格
        self._rebuild_params_table(2)
        
        return panel

    def _on_num_states_changed(self, k):
        """状态数量改变时的响应"""
        self._rebuild_params_table(k)
        if self._get_current_data() is not None and self.param_source_str == "Auto-Guessed":
            self.auto_guess_parameters()

    def _on_toggle_state_level(self, checked):
        """切换是否在图形中显示 HMM State Level 阶梯线（方便与原始数据对比）"""
        self.plot_canvas.set_state_level_visible(checked)

    def _rebuild_params_table(self, num_states):
        """重新构建参数输入表格"""
        self.params_table.setRowCount(num_states)
        
        color_palette = [
            '#e74c3c', '#2ecc71', '#3498db', '#f39c12', '#9b59b6', 
            '#1abc9c', '#d35400', '#34495e', '#e67e22', '#7f8c8d'
        ]
        
        new_params = []
        for i in range(num_states):
            st_name = f"State {i+1}"
            color = color_palette[i % len(color_palette)]
            
            # State 列 Item
            item_name = QTableWidgetItem(st_name)
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_name.setForeground(QColor(color))
            font = item_name.font()
            font.setBold(True)
            item_name.setFont(font)
            self.params_table.setItem(i, 0, item_name)
            
            # Mean (μ) SpinBox
            mean_spin = QDoubleSpinBox()
            mean_spin.setRange(-1e6, 1e6)
            mean_spin.setDecimals(4)
            mean_spin.setSingleStep(0.01)
            mean_spin.setValue(float(i + 1))
            self.params_table.setCellWidget(i, 1, mean_spin)
            
            # Std (σ) SpinBox
            std_spin = QDoubleSpinBox()
            std_spin.setRange(1e-5, 1e6)
            std_spin.setDecimals(4)
            std_spin.setSingleStep(0.01)
            std_spin.setValue(0.5)
            self.params_table.setCellWidget(i, 2, std_spin)
            
            new_params.append({
                'id': i,
                'name': st_name,
                'mean_widget': mean_spin,
                'std_widget': std_spin,
                'color': color
            })
            
        self.current_params = new_params

    def get_gaussian_fits_from_parent(self):
        """从 Histogram 窗口的高斯拟合结果中提取 (mean, std) 参数"""
        fits = []
        if self.parent_dialog is None:
            return fits
            
        # Source 1: fitting_manager.gaussian_fits
        if hasattr(self.parent_dialog, 'plot_canvas') and hasattr(self.parent_dialog.plot_canvas, 'fitting_manager'):
            fm = self.parent_dialog.plot_canvas.fitting_manager
            if hasattr(fm, 'gaussian_fits') and fm.gaussian_fits:
                for item in fm.gaussian_fits:
                    popt = item.get('popt')
                    if popt is not None and len(popt) >= 3:
                        amp, mu, sigma = popt[0], popt[1], popt[2]
                        fits.append({'mean': float(mu), 'std': float(sigma), 'color': item.get('color')})
                        
        # Source 2: fit_info_panel
        if not fits and hasattr(self.parent_dialog, 'fit_info_panel'):
            fip = self.parent_dialog.fit_info_panel
            if hasattr(fip, 'fits') and fip.fits:
                for item in fip.fits:
                    if isinstance(item, dict):
                        mu = item.get('mu') or item.get('mean')
                        sigma = item.get('sigma') or item.get('std')
                        if mu is not None and sigma is not None:
                            fits.append({'mean': float(mu), 'std': float(sigma), 'color': item.get('color')})
                            
        # Source 3: shared_fit_data / fit_data_manager
        if not fits and hasattr(self.parent_dialog, 'plot_canvas') and hasattr(self.parent_dialog.plot_canvas, 'shared_fit_data'):
            sfd = self.parent_dialog.plot_canvas.shared_fit_data
            if sfd and hasattr(sfd, 'gaussian_fits') and sfd.gaussian_fits:
                for item in sfd.gaussian_fits:
                    popt = item.get('popt')
                    if popt is not None and len(popt) >= 3:
                        fits.append({'mean': float(popt[1]), 'std': float(popt[2]), 'color': item.get('color')})
                        
        # 按均值从小到大排序
        if fits:
            fits = sorted(fits, key=lambda x: x['mean'])
            for idx, p in enumerate(fits):
                p['id'] = idx
                p['name'] = f"State {idx+1}"
                
        return fits

    def import_from_gaussian_fits(self):
        """从 Histogram 高斯拟合结果中自动导入参数"""
        fits = self.get_gaussian_fits_from_parent()
        if not fits:
            QMessageBox.information(
                self, "No Gaussian Fits Found",
                "No active Gaussian fit results found in the Histogram view.\n"
                "Please perform Gaussian fitting in the Histogram window first, or use 'Auto-Guess'."
            )
            self.auto_guess_parameters()
            return
            
        K = len(fits)
        self.num_states_spin.blockSignals(True)
        self.num_states_spin.setValue(K)
        self.num_states_spin.blockSignals(False)
        
        self._rebuild_params_table(K)
        
        for i, p in enumerate(fits):
            if i < len(self.current_params):
                self.current_params[i]['mean_widget'].setValue(p['mean'])
                self.current_params[i]['std_widget'].setValue(p['std'])
                
        self.param_source_str = f"Imported from {K} Gaussian Fits"
        self.param_source_label.setText(f"Source: {self.param_source_str}")
        self.param_source_label.setStyleSheet("color: #27ae60; font-size: 8.5pt; font-weight: bold;")

    def _get_current_data(self):
        """获取当前 Highlighted Region 区域的物理数据片段"""
        target_plot = self.main_plot
        if target_plot is None and self.parent_dialog is not None:
            if hasattr(self.parent_dialog, 'plot_canvas'):
                target_plot = self.parent_dialog.plot_canvas
                
        if target_plot is not None and hasattr(target_plot, 'data') and target_plot.data is not None:
            data = target_plot.data
            invert = getattr(target_plot, 'invert_data', False)
            plot_d = -data if invert else data
            
            h_min = getattr(target_plot, 'highlight_min', 0)
            h_max = getattr(target_plot, 'highlight_max', len(data))
            
            if 0 <= h_min < h_max <= len(plot_d):
                return plot_d[h_min:h_max]
            return plot_d
        return None

    def auto_guess_parameters(self):
        """根据当前 Highlighted Region 数据自动估算 μ 和 σ 参数"""
        h_data = self._get_current_data()
        if h_data is None or len(h_data) == 0:
            QMessageBox.information(self, "Notice", "Please load data in Main View first.")
            return
            
        K = self.num_states_spin.value()
        guessed = HMMStateAnalyzer.auto_guess_parameters(h_data, K)
        
        if len(guessed) == K:
            for i, p in enumerate(guessed):
                if i < len(self.current_params):
                    self.current_params[i]['mean_widget'].setValue(p['mean'])
                    self.current_params[i]['std_widget'].setValue(p['std'])
                    
        self.param_source_str = "Auto-Guessed (Percentiles)"
        self.param_source_label.setText(f"Source: {self.param_source_str}")
        self.param_source_label.setStyleSheet("color: #7f8c8d; font-size: 8.5pt; font-style: italic;")

    def run_hmm_analysis(self):
        """提取参数输入，基于真实采样率与高级算法参数执行 HMM Viterbi 状态解码并渲染"""
        h_data = self._get_current_data()
        if h_data is None or len(h_data) == 0:
            QMessageBox.warning(self, "Error", "No valid data available for HMM analysis.")
            return
            
        # 获取采样率与高级算法参数
        sr = self.sr_spin.value()
        exp_dwell = self.expected_dwell_spin.value()
        j_decay = self.jump_decay_spin.value()
        m_dwell = self.min_dwell_spin.value()
        max_sig_frac = self.max_sigma_frac_spin.value()
        
        # 收集用户输入的 μ 和 σ 参数
        state_params = []
        for item in self.current_params:
            m_val = item['mean_widget'].value()
            s_val = item['std_widget'].value()
            state_params.append({
                'id': item['id'],
                'name': item['name'],
                'mean': float(m_val),
                'std': max(1e-5, float(s_val)),
                'color': item['color']
            })
            
        # 执行 HMM 解码
        try:
            result = HMMStateAnalyzer.decode_states(
                h_data,
                state_params,
                sampling_rate=sr,
                expected_dwell_ms=exp_dwell,
                jump_decay=j_decay,
                min_dwell_ms=m_dwell,
                max_sigma_fraction=max_sig_frac
            )
            if result is None:
                QMessageBox.warning(self, "Error", "HMM decoding failed.")
                return
                
            # 将解码结果推送至 StateLabelPlot 渲染
            self.plot_canvas.set_hmm_result(result, state_params)
            
            # 显示结果与时间统计信息
            self._display_stats_results(result)
            
        except Exception as e:
            QMessageBox.warning(self, "HMM Error", f"Error during HMM execution: {str(e)}")

    def _display_stats_results(self, result):
        """格式化输出 HMM 状态分析结果，包含显式的当前使用参数卡片与统计表"""
        if not result or 'stats' not in result:
            self.stats_display.setHtml("<i>No state statistics available.</i>")
            return
            
        stats = result['stats']
        total_duration_sec = result.get('total_duration_sec', 0.0)
        sr = result.get('sampling_rate', 1000.0)
        total_pts = result.get('total_points', 0)
        
        exp_dwell = self.expected_dwell_spin.value()
        j_decay = self.jump_decay_spin.value()
        m_dwell = self.min_dwell_spin.value()
        max_sig_frac = self.max_sigma_frac_spin.value()
        
        html = "<style>table {width:100%; border-collapse:collapse;} td,th {padding:4px; border-bottom:1px solid #ddd; font-size:9pt;} th {background-color:#f2f2f2; text-align:left;}</style>"
        html += "<h4 style='margin-bottom:4px; color:#2c3e50;'>Active Parameters & Summary</h4>"
        html += f"<div style='font-size:9pt; margin-bottom:8px; color:#444; background-color:#f8f9fa; padding:6px; border-radius:4px; border:1px solid #e9ecef;'>"
        html += f"<b>Sampling Rate (fs):</b> {sr:.1f} Hz | <b>Source:</b> {self.param_source_str}<br/>"
        html += f"<b>Exp Dwell (τ):</b> {exp_dwell:.2f} ms | <b>Jump Decay (λ):</b> {j_decay:.1f} | <b>Min Dwell:</b> {m_dwell:.2f} ms | <b>Max Sigma Frac:</b> {max_sig_frac:.2f}<br/>"
        html += f"<b>Total Region Duration:</b> {total_duration_sec:.4f} s ({total_duration_sec*1000.0:.1f} ms) | <b>Points:</b> {total_pts}"
        html += f"</div>"
        
        html += "<table><tr><th>State</th><th>Mean (μ)</th><th>Std (σ)</th><th>Total Time</th><th>Occ. %</th><th>Events</th><th>Avg Dwell</th></tr>"
        
        for s in stats:
            st_color = s['color']
            st_name = s['name']
            m = s['mean']
            sd = s['std']
            occ = s['occupancy_pct']
            evts = s['num_events']
            
            t_sec = s.get('total_state_sec', 0.0)
            t_ms = s.get('total_state_ms', 0.0)
            avg_ms = s.get('avg_dwell_ms', 0.0)
            
            time_str = f"{t_ms:.1f} ms" if t_sec < 1.0 else f"{t_sec:.3f} s"
            avg_dwell_str = f"{avg_ms:.1f} ms" if avg_ms < 1000.0 else f"{avg_ms/1000.0:.3f} s"
            
            html += f"<tr>"
            html += f"<td style='color:{st_color}; font-weight:bold;'>{st_name}</td>"
            html += f"<td>{m:.4f}</td>"
            html += f"<td>{sd:.4f}</td>"
            html += f"<td><b>{time_str}</b></td>"
            html += f"<td>{occ:.1f}%</td>"
            html += f"<td>{evts}</td>"
            html += f"<td>{avg_dwell_str}</td>"
            html += f"</tr>"
            
        html += "</table>"
        
        if 'transition_rates_per_s' in result:
            tr = result['transition_rates_per_s']
            html += "<h4 style='margin-top:10px; margin-bottom:4px; color:#2c3e50;'>Transition Rates Matrix (s<sup>-1</sup>)</h4>"
            html += "<table><tr><th>From \\ To</th>"
            for s in stats:
                html += f"<th style='color:{s['color']};'>{s['name']}</th>"
            html += "</tr>"
            for i, s_from in enumerate(stats):
                html += f"<tr><td style='color:{s_from['color']}; font-weight:bold;'>{s_from['name']}</td>"
                for j in range(len(stats)):
                    val = tr[i, j]
                    val_str = "-" if i == j else f"{val:.1f}"
                    html += f"<td>{val_str}</td>"
                html += "</tr>"
            html += "</table>"
            
        self.stats_display.setHtml(html)

    def sync_with_main_view(self, main_plot):
        """同步并更新来自 Main View 的数据"""
        self.main_plot = main_plot
        self.sync_from_parent()

    def sync_from_parent(self):
        """重新拉取父窗口 Main View 的数据并重绘，自动同步采样率与高斯拟合"""
        target_plot = self.main_plot
        if target_plot is None and self.parent_dialog is not None:
            if hasattr(self.parent_dialog, 'plot_canvas'):
                target_plot = self.parent_dialog.plot_canvas
                self.main_plot = target_plot
                
        if target_plot is not None and hasattr(target_plot, 'data') and target_plot.data is not None:
            self.plot_canvas.sync_with_main_plot(target_plot)
            
            # 自动同步采样率
            sr = float(getattr(target_plot, 'sampling_rate', 1000.0))
            self.sr_spin.setValue(sr)
            
            # 如果存在高斯拟合，自动导入高斯拟合；否则自动估计
            fits = self.get_gaussian_fits_from_parent()
            if fits:
                self.import_from_gaussian_fits()
            else:
                self.auto_guess_parameters()
            
            # 更新 Header 信息
            f_name = getattr(target_plot, 'file_name', 'Current Main View') or 'Current Main View'
            pts = len(target_plot.data)
            h_min = getattr(target_plot, 'highlight_min', 0)
            h_max = getattr(target_plot, 'highlight_max', pts)
            t_min = h_min / sr
            t_max = h_max / sr
            self.info_label.setText(
                f"File: {f_name} | SR: {sr:.0f} Hz | Total: {pts} pts | Highlighted: {t_min:.3f}s - {t_max:.3f}s"
            )
        else:
            self.info_label.setText("Data Source: No active Main View data available")

    def _get_default_export_info(self):
        """获取当前加载数据文件所在的文件夹目录以及建议的导出文件夹名称"""
        default_dir = os.path.expanduser("~/Desktop")
        f_name = "Data"
        
        target_plot = self.main_plot
        if target_plot is None and self.parent_dialog is not None:
            if hasattr(self.parent_dialog, 'plot_canvas'):
                target_plot = self.parent_dialog.plot_canvas
                
        candidate_paths = []
        if target_plot and hasattr(target_plot, 'file_name') and target_plot.file_name:
            candidate_paths.append(target_plot.file_name)
            
        if self.parent_dialog:
            if hasattr(self.parent_dialog, 'file_path') and self.parent_dialog.file_path:
                candidate_paths.append(self.parent_dialog.file_path)
            if hasattr(self.parent_dialog, 'parent') and callable(self.parent_dialog.parent):
                pw = self.parent_dialog.parent()
                if pw and hasattr(pw, 'current_file_path') and pw.current_file_path:
                    candidate_paths.append(pw.current_file_path)

        for p in candidate_paths:
            if p and os.path.exists(p):
                default_dir = os.path.dirname(os.path.abspath(p))
                f_name = os.path.splitext(os.path.basename(p))[0]
                break
            elif p:
                f_name = os.path.splitext(os.path.basename(p))[0]

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        suggested_folder_name = f"StateLabel_Export_{f_name}_{timestamp_str}"
        return default_dir, suggested_folder_name

    def export_analysis_results(self):
        """一键导出原始数据、HMM 阶梯数据、统计指标与高分辨率图像至指定文件夹"""
        target_plot = self.main_plot
        if target_plot is None and self.parent_dialog is not None:
            if hasattr(self.parent_dialog, 'plot_canvas'):
                target_plot = self.parent_dialog.plot_canvas
                
        if target_plot is None or not hasattr(target_plot, 'data') or target_plot.data is None:
            QMessageBox.warning(self, "Export Error", "No active data available for export.")
            return
            
        h_data = self._get_current_data()
        if h_data is None or len(h_data) == 0:
            QMessageBox.warning(self, "Export Error", "No valid highlighted region data available.")
            return
            
        hmm_res = getattr(self.plot_canvas, 'hmm_result', None)
        if hmm_res is None:
            QMessageBox.warning(
                self, "Export Warning",
                "No HMM analysis results available to export.\n"
                "Please click 'Run HMM State Analysis' before exporting."
            )
            return
            
        sr = self.sr_spin.value()
        time_axis = np.arange(len(h_data)) / sr
        
        # 1. 提取当前数据文件默认所在路径与建议的导出文件夹名称
        default_dir, suggested_folder_name = self._get_default_export_info()
        
        # 2. 弹出导出设置对话框（默认路径为当前数据文件路径，且允许用户修改保存文件夹名称）
        dlg = StateLabelExportDialog(self, default_dir=default_dir, suggested_folder_name=suggested_folder_name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
            
        final_export_dir = dlg.get_export_path()
        
        f_name = getattr(target_plot, 'file_name', 'Data') or 'Data'
        metadata = {
            'file_name': f_name,
            'sampling_rate': sr,
            'total_points': len(h_data),
            't_min': time_axis[0] if len(time_axis) > 0 else 0.0,
            't_max': time_axis[-1] if len(time_axis) > 0 else 0.0,
            'param_source': self.param_source_str
        }
        
        # 3. 执行全量数据与图像导出
        res = StateLabelExporter.export_all(
            target_dir=final_export_dir,
            time_axis=time_axis,
            raw_data=h_data,
            hmm_result=hmm_res,
            state_params=self.current_params,
            fig=self.plot_canvas.fig,
            metadata=metadata
        )
        
        if res.get('success'):
            files_str = "\n".join([f"• {os.path.basename(p)}" for p in res['saved_files']])
            QMessageBox.information(
                self, "Export Successful",
                f"All data, statistics, and high-res plot exported successfully!\n\n"
                f"Target Folder:\n{final_export_dir}\n\n"
                f"Exported Files:\n{files_str}"
            )
        else:
            QMessageBox.critical(self, "Export Error", res.get('message', 'Export failed.'))


class StateLabelExportDialog(QDialog):
    """导出配置对话框：默认使用数据文件路径，并允许用户自由修改导出的文件夹名称"""
    
    def __init__(self, parent=None, default_dir="", suggested_folder_name=""):
        super(StateLabelExportDialog, self).__init__(parent)
        self.setWindowTitle("Export Analysis Results & Plot")
        self.resize(580, 210)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        
        info_lbl = QLabel("Select Save Location Directory and Export Folder Name:")
        info_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(info_lbl)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # 1. 保存路径 (Save Location Directory)
        dir_layout = QHBoxLayout()
        self.dir_line = QLineEdit(default_dir)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_dir)
        
        dir_layout.addWidget(self.dir_line, 1)
        dir_layout.addWidget(self.browse_btn)
        form_layout.addRow("Save Location:", dir_layout)
        
        # 2. 文件夹名称 (Export Folder Name)
        self.folder_name_line = QLineEdit(suggested_folder_name)
        form_layout.addRow("Export Folder Name:", self.folder_name_line)
        
        layout.addLayout(form_layout)
        
        # 按钮栏 (Export / Cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ok_btn = QPushButton("Export")
        ok_btn.setMinimumWidth(100)
        ok_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 16px;")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
    def _browse_dir(self):
        curr = self.dir_line.text().strip() or os.path.expanduser("~/Desktop")
        chosen = QFileDialog.getExistingDirectory(self, "Select Save Location Directory", curr)
        if chosen:
            self.dir_line.setText(chosen)

    def get_export_path(self):
        parent_dir = self.dir_line.text().strip() or os.path.expanduser("~/Desktop")
        folder_name = self.folder_name_line.text().strip() or "StateLabel_Export"
        return os.path.join(parent_dir, folder_name)
