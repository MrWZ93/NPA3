#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSD可视化组件模块
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from scipy.signal import find_peaks


class PSDVisualizer(FigureCanvas):
    """功率谱密度可视化组件"""
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        
        super(PSDVisualizer, self).__init__(self.fig)
        self.setParent(parent)
        
        # 设置图表边距更紧凑
        self.fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.12)
        self.current_frequencies = None
        self.current_psd = None
        self.current_peak_indices = None
        self.normalized = False
        self.plot_params = {}  # 存储绘图参数以便导出
        
        # 添加光标跟踪
        self.cursor_annotation = self.axes.annotate('', xy=(0, 0), xytext=(10, 10),
                                               textcoords='offset points',
                                               bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                                               arrowprops=dict(arrowstyle='->'))
        self.cursor_annotation.set_visible(False)
        
        # 启用鼠标跟踪
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_click)
        
        # 光标跟踪状态
        self.cursor_tracking = False
        
        # 设置交互式区域选择器
        self.span_selector = SpanSelector(
            self.axes, self.on_region_selected, 'horizontal',
            useblit=True, props=dict(alpha=0.2, facecolor='blue'),
            interactive=True, drag_from_anywhere=True
        )
        self.span_selector.set_active(False)  # 默认禁用
        
        # 存储选中的区域
        self.selected_region = None
        
        # 图例
        self.legend = None
    
    def plot_psd(self, frequencies, psd, title="Power Spectral Density", normalized=False, 
                 log_x=True, log_y=True, exclude_bins=1, plot_type="dB", find_peaks_enabled=False,
                 peak_height=None, peak_distance=None, peak_threshold=None, window_type=None,
                 nfft=None, sampling_rate=None, low_cutoff=None, high_cutoff=None):
        """绘制PSD，采用ClampFit风格的对数坐标"""
        self.axes.clear()
        self.current_frequencies = frequencies
        self.current_psd = psd
        self.normalized = normalized
        self.current_peak_indices = None  # 清除之前的峰值索引
        
        # 存储绘图参数
        self.plot_params = {
            'normalized': normalized,
            'log_x': log_x,
            'log_y': log_y,
            'exclude_bins': exclude_bins,
            'plot_type': plot_type,
            'find_peaks_enabled': find_peaks_enabled,
            'peak_height': peak_height,
            'peak_distance': peak_distance,
            'peak_threshold': peak_threshold,
            'window_type': window_type,
            'nfft': nfft,
            'sampling_rate': sampling_rate,
            'low_cutoff': low_cutoff,
            'high_cutoff': high_cutoff
        }
        
        # 排除前n个频率箱（通常排除DC分量）
        if exclude_bins > 0 and len(frequencies) > exclude_bins:
            frequencies = frequencies[exclude_bins:]
            psd = psd[exclude_bins:]
        
        # 防止零值和负值导致对数计算问题
        psd = np.maximum(psd, 1e-20)
        
        # 频率截止处理 (添加标记)
        freq_mask = np.ones_like(frequencies, dtype=bool)
        
        # 应用低频截止
        if low_cutoff is not None and low_cutoff > 0:
            freq_mask = freq_mask & (frequencies >= low_cutoff)
            
        # 应用高频截止
        if high_cutoff is not None and high_cutoff > 0:
            freq_mask = freq_mask & (frequencies <= high_cutoff)
            
        # 应用频率过滤
        if not np.all(freq_mask):
            frequencies = frequencies[freq_mask]
            psd = psd[freq_mask]
        
        # 准备数据格式
        if plot_type == "dB":
            # 转换为dB
            if normalized and np.max(psd) > 0:
                psd_to_plot = 10 * np.log10(psd / np.max(psd))
                y_label = "Normalized Power (dB)"
            else:
                psd_to_plot = 10 * np.log10(psd)
                y_label = "Power (dB)"
        elif plot_type == "raw":
            # 使用原始功率值
            if normalized and np.max(psd) > 0:
                psd_to_plot = psd / np.max(psd)
                y_label = "Normalized Power"
            else:
                psd_to_plot = psd
                y_label = "Power (V²/Hz)"
        else:
            # 默认
            psd_to_plot = psd
            y_label = "Power (V²/Hz)"
        
        # 设置坐标轴类型
        if log_x:
            self.axes.set_xscale('log')
        else:
            self.axes.set_xscale('linear')
            
        if log_y and plot_type != "dB":  # dB已经是对数形式
            self.axes.set_yscale('log')
        else:
            self.axes.set_yscale('linear')
        
        # 构建标题并添加计算参数信息
        full_title = title
        if window_type or nfft:
            param_text = []
            if window_type:
                param_text.append(f"Window: {window_type}")
            if nfft:
                param_text.append(f"NFFT: {nfft}")
            full_title += "\n" + ", ".join(param_text)
        
        # 绘图
        line, = self.axes.plot(frequencies, psd_to_plot, label="PSD")
        
        # 峰值检测
        if find_peaks_enabled and peak_height is not None:
            # 根据不同的数据类型处理峰值检测
            if plot_type == "dB":
                if normalized:
                    # 对于归一化的dB数据，将阈值从百分比转换为dB
                    peak_height_value = 10 * np.log10(peak_height/100)
                else:
                    # 对于非归一化的dB数据，直接使用dB值
                    peak_height_value = peak_height
            else:
                if normalized:
                    # 对于归一化的原始数据，直接使用百分比值
                    peak_height_value = peak_height/100
                else:
                    # 对于非归一化的原始数据，使用相对于最大值的百分比
                    peak_height_value = np.max(psd_to_plot) * (peak_height/100)
            
            # 计算最小峰值间距（频点数量）
            if peak_distance is not None and peak_distance > 0:
                if sampling_rate is not None and sampling_rate > 0:
                    # 将Hz转换为频点索引距离
                    freq_resolution = frequencies[1] - frequencies[0] if len(frequencies) > 1 else 1
                    min_distance = max(1, int(peak_distance / freq_resolution))  # 确保距离至少为1
                else:
                    # 默认使用频点数量
                    min_distance = max(1, int(peak_distance))  # 确保距离至少为1
            else:
                # 默认间隔
                min_distance = 1
                
            # 设置相对高度阈值
            if peak_threshold is not None:
                prominence = peak_threshold_value = np.max(psd_to_plot) * (peak_threshold/100)
            else:
                prominence = None
                
            # 查找峰值
            peak_indices, peak_props = find_peaks(
                psd_to_plot, 
                height=peak_height_value,
                distance=min_distance,
                prominence=prominence
            )
            
            # 标记峰值
            if len(peak_indices) > 0:
                peak_freqs = frequencies[peak_indices]
                peak_psd = psd_to_plot[peak_indices]
                self.axes.scatter(peak_freqs, peak_psd, color='red', marker='^', s=50, label="Peaks")
                
                # 为前N个峰值添加频率标签
                max_labels = min(5, len(peak_indices))  # 最多显示5个标签
                sorted_indices = np.argsort(peak_psd)[::-1][:max_labels]  # 按功率排序
                
                for i in sorted_indices:
                    self.axes.annotate(
                        f"{peak_freqs[i]:.2f} Hz",
                        xy=(peak_freqs[i], peak_psd[i]),
                        xytext=(5, 5),
                        textcoords='offset points',
                        fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7)
                    )
                
                # 保存找到的峰值索引
                self.current_peak_indices = peak_indices
        
        # 添加图例并设置为可拖动
        if self.current_peak_indices is not None and len(self.current_peak_indices) > 0:
            legend = self.axes.legend()
            legend.set_draggable(True)
        
        # 设置标签和标题
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel(y_label)
        self.axes.set_title(full_title)
        self.axes.grid(True, which="both", ls="-", alpha=0.6)
        
        # 如果存在选中区域，重新绘制
        if self.selected_region is not None:
            xmin, xmax = self.selected_region
            if log_x:
                # 对于对数坐标，需要检查边界是否在有效范围内
                if xmin <= 0:
                    xmin = min(frequencies[frequencies > 0]) if np.any(frequencies > 0) else frequencies[0]
            self.axes.axvspan(xmin, xmax, alpha=0.2, color='green')
        
        # 使用更紧凑的布局
        self.fig.subplots_adjust(left=0.12, right=0.95, top=0.90, bottom=0.12)
        self.draw()
    
    def on_mouse_move(self, event):
        """处理鼠标移动事件，更新光标注释"""
        if not self.cursor_tracking or not event.inaxes or self.current_frequencies is None:
            return
        
        # 获取光标位置对应的数据点
        x, y = event.xdata, event.ydata
        
        # 找到最接近的频率点
        idx = np.abs(self.current_frequencies - x).argmin()
        freq = self.current_frequencies[idx]
        psd_value = self.current_psd[idx]
        
        # 根据当前显示模式格式化PSD值
        if self.plot_params.get('plot_type') == 'dB':
            if self.normalized:
                psd_display = f"{10 * np.log10(psd_value / np.max(self.current_psd)):.2f} dB"
            else:
                psd_display = f"{10 * np.log10(psd_value):.2f} dB"
        else:
            if self.normalized:
                psd_display = f"{psd_value / np.max(self.current_psd):.6f}"
            else:
                psd_display = f"{psd_value:.6e} V²/Hz"
        
        # 更新注释
        self.cursor_annotation.xy = (freq, y)
        self.cursor_annotation.set_text(f"Freq: {freq:.2f} Hz\nPSD: {psd_display}")
        self.cursor_annotation.set_visible(True)
        self.draw_idle()
    
    def on_mouse_click(self, event):
        """处理鼠标点击事件，锁定光标注释"""
        if event.inaxes and event.button == 3:  # 右键点击
            # 切换光标跟踪状态
            self.cursor_tracking = not self.cursor_tracking
            if not self.cursor_tracking:
                self.cursor_annotation.set_visible(False)
                self.draw_idle()
    
    def on_region_selected(self, xmin, xmax):
        """处理选区事件"""
        self.selected_region = (xmin, xmax)
        
        # 如果有频率数据
        if self.current_frequencies is not None and self.current_psd is not None:
            # 找到选区内的频率范围
            indices = np.where((self.current_frequencies >= xmin) & 
                              (self.current_frequencies <= xmax))[0]
            
            if len(indices) > 0:
                # 计算选区内的功率总和和平均值
                selected_psd = self.current_psd[indices]
                total_power = np.sum(selected_psd)
                avg_power = np.mean(selected_psd)
                peak_power = np.max(selected_psd)
                peak_freq = self.current_frequencies[indices[np.argmax(selected_psd)]]
                
                # 在选区上方显示信息
                self.axes.text(
                    (xmin + xmax) / 2, self.axes.get_ylim()[1] * 0.95,
                    f"Band: {xmin:.2f}-{xmax:.2f} Hz\n"
                    f"Peak: {peak_freq:.2f} Hz\n"
                    f"BW: {xmax - xmin:.2f} Hz",
                    horizontalalignment='center',
                    verticalalignment='top',
                    bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8)
                )
                
                self.draw_idle()
    
    def toggle_region_selector(self, active):
        """切换区域选择器的活动状态"""
        self.span_selector.set_active(active)
        if not active:
            self.selected_region = None
            self.draw_idle()
    
    def get_current_data(self):
        """获取当前PSD数据"""
        if self.current_frequencies is not None and self.current_psd is not None:
            return self.current_frequencies, self.current_psd, self.normalized, self.plot_params
        return None, None, False, {}
    
    def clear(self):
        """清除图表"""
        self.axes.clear()
        self.current_frequencies = None
        self.current_psd = None
        self.current_peak_indices = None
        self.plot_params = {}
        self.selected_region = None
        self.draw()
