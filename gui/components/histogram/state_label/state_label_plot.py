#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Label Plot Canvas - 直方图 Highlighted Region 专区画布
仅聚焦展示 Highlighted Region 部分的时间序列及对齐直方图
"""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.components.histogram.plot_utils import DataCleaner


class StateLabelPlot(FigureCanvas):
    """State Label 聚焦 Highlighted Region 画布组件"""
    
    def __init__(self, parent=None, width=12, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(StateLabelPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        self.data_cleaner = DataCleaner()
        
        # 数据与参数缓存
        self.data = None
        self.sampling_rate = 1000.0
        self.bins = 50
        self.log_x = False
        self.log_y = False
        self.show_kde = False
        self.invert_data = False
        self.file_name = ""
        self.highlight_min = 0
        self.highlight_max = 0
        self.source_plot_ref = None
        self.hmm_result = None
        self.state_params = None
        self.show_state_level = True
        
        self.setup_subplots()
        
    def setup_subplots(self):
        """设置 Highlighted Region 的单排布局（左: 区域波形, 右: 对齐直方图）"""
        self.fig.clear()
        self.fig.set_dpi(100)
        
        # 单排比例：1 行 2 列，宽度比为 3.5 : 1
        gs = self.fig.add_gridspec(1, 2, width_ratios=[3.5, 1], wspace=0.06)
        
        self.ax1 = self.fig.add_subplot(gs[0, 0])  # Highlighted Region 波形图
        self.ax2 = self.fig.add_subplot(gs[0, 1])  # Highlighted Region 直方图
        
        # 共享 Y 轴，隐藏右侧直方图的 Y 轴 Tick labels 避免重叠（纯面向对象 API，防全局 plt 字体污染）
        self.ax1.sharey(self.ax2)
        self.ax2.yaxis.set_tick_params(labelleft=False, left=False)
        
        # 设置轴标签与标题
        self.ax1.set_title("Highlighted Region", fontsize=11, pad=6, fontweight='bold')
        self.ax2.set_title("Histogram", fontsize=11, pad=6, fontweight='bold')
        
        self.ax1.set_xlabel("Time (s)", fontsize=10, labelpad=4)
        self.ax1.set_ylabel("Amplitude", fontsize=10, labelpad=4, rotation=90)
        self.ax2.set_xlabel("Count", fontsize=10, labelpad=4)
        
        self.ax1.tick_params(labelsize=9, pad=2)
        self.ax2.tick_params(labelsize=9, pad=2)
        
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.11, wspace=0.06)

    def set_hmm_result(self, result, state_params):
        """应用并保存 HMM 状态解码结果，同时触发重绘"""
        self.hmm_result = result
        self.state_params = state_params
        if self.source_plot_ref is not None:
            self.sync_with_main_plot(self.source_plot_ref)

    def set_state_level_visible(self, visible):
        """控制是否显示 HMM State Level 叠加线（用于与原始数据对比）"""
        self.show_state_level = visible
        if self.source_plot_ref is not None:
            self.sync_with_main_plot(self.source_plot_ref)

    def sync_with_main_plot(self, source_plot):
        """同步 Main View 中的 Highlighted Region 部分"""
        if source_plot is None or not hasattr(source_plot, 'data') or source_plot.data is None:
            return
            
        self.source_plot_ref = source_plot
        data = source_plot.data
        sampling_rate = getattr(source_plot, 'sampling_rate', 1000.0)
        bins = getattr(source_plot, 'bins', 50)
        log_x = getattr(source_plot, 'log_x', False)
        log_y = getattr(source_plot, 'log_y', False)
        show_kde = getattr(source_plot, 'show_kde', False)
        invert_data = getattr(source_plot, 'invert_data', False)
        file_name = getattr(source_plot, 'file_name', "")
        
        highlight_min = getattr(source_plot, 'highlight_min', 0)
        highlight_max = getattr(source_plot, 'highlight_max', len(data))
        
        clean_d = self.data_cleaner.clean_data(data)
        if clean_d is None or len(clean_d) == 0:
            return
            
        self.data = clean_d
        self.sampling_rate = sampling_rate
        self.bins = bins
        self.log_x = log_x
        self.log_y = log_y
        self.show_kde = show_kde
        self.invert_data = invert_data
        self.file_name = file_name
        self.highlight_min = highlight_min
        self.highlight_max = highlight_max
        
        self.setup_subplots()
        
        time_axis = np.arange(len(clean_d)) / sampling_rate
        plot_d = -clean_d if invert_data else clean_d
        
        # 只提取并绘制 Highlighted Region 区域
        if 0 <= highlight_min < highlight_max <= len(clean_d):
            t_start = time_axis[highlight_min]
            t_end = time_axis[min(highlight_max, len(time_axis) - 1)]
            
            h_data = plot_d[highlight_min:highlight_max]
            h_time = time_axis[highlight_min:highlight_max]
            
            # 设置标题
            self.ax1.set_title(
                f"Highlighted Region ({t_start:.3f}s - {t_end:.3f}s) [{'Inverted' if invert_data else 'Normal'}]",
                fontsize=11, pad=6, fontweight='bold'
            )
            
            # 1. 绘制波形图（原始数据）
            self.ax1.plot(h_time, h_data, linewidth=0.8, color='#2ca02c', alpha=0.9, label='Raw Signal', zorder=2)
            self.ax1.grid(True, linestyle='--', alpha=0.5)
            
            # 2. 绘制对应的高亮区域直方图
            if len(h_data) > 0:
                counts, bin_edges, patches = self.ax2.hist(
                    h_data, bins=bins, orientation='horizontal',
                    color='#3498db', alpha=0.6, edgecolor='black', linewidth=0.5
                )
                self.ax2.grid(True, linestyle='--', alpha=0.5)
                
                bin_width = bin_edges[1] - bin_edges[0] if len(bin_edges) > 1 else 1.0
                
                # 3. 如果已有 HMM 解码结果，叠加 HMM 状态波形线与高斯分布线
                if hasattr(self, 'hmm_result') and self.hmm_result is not None:
                    fitted_trace = self.hmm_result.get('fitted_trace')
                    
                    # 当且仅当 show_state_level 为 True 时才在波形图上叠加 HMM 阶梯线
                    if getattr(self, 'show_state_level', True):
                        if fitted_trace is not None and len(fitted_trace) == len(h_data):
                            # 将 alpha 调高透明度（alpha=0.6）
                            self.ax1.plot(h_time, fitted_trace, linewidth=2.0, color='#e74c3c', alpha=0.6, label='HMM State Level', zorder=5)
                        
                    # 绘制各状态均值虚线与高斯曲线
                    if hasattr(self, 'state_params') and self.state_params:
                        y_grid = np.linspace(np.min(h_data), np.max(h_data), 300)
                        
                        for p in self.state_params:
                            m = p['mean']
                            s = max(1e-5, p['std'])
                            c = p.get('color', '#e74c3c')
                            st_name = p.get('name', f"State {p['id']+1}")
                            
                            # ax1 水平均值线（当 show_state_level 为 True 时显示），使用相对 x 坐标 0.015 避开 y 轴重叠
                            if getattr(self, 'show_state_level', True):
                                self.ax1.axhline(m, color=c, linestyle='--', linewidth=1.2, alpha=0.6)
                                self.ax1.text(
                                    0.015, m, f" {st_name} ({m:.3f})",
                                    transform=self.ax1.get_yaxis_transform(),
                                    color=c, fontsize=8, verticalalignment='bottom', fontweight='bold',
                                    bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.75, edgecolor='none')
                                )
                            
                            # ax2 高斯分布拟合曲线
                            pdf = (1.0 / (s * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((y_grid - m) / s) ** 2)
                            scale_factor = len(h_data) * bin_width
                            self.ax2.plot(pdf * scale_factor, y_grid, color=c, linewidth=2.0, label=f"{st_name} PDF")
                            self.ax2.axhline(m, color=c, linestyle='--', linewidth=1.2, alpha=0.85)
                            
                self.ax1.legend(loc='upper right', fontsize=8, framealpha=0.85, edgecolor='#cccccc')
                
                # 对数轴处理
                if log_x:
                    self.ax2.set_xscale('log')
                if log_y:
                    self.ax1.set_yscale('log')
                    self.ax2.set_yscale('log')

        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.11, wspace=0.06)
        self.draw()
