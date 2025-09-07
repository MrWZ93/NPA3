#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Plot - 基础绘图功能
提供直方图的基本绘图能力
"""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector
import matplotlib.gridspec as gridspec
from scipy import stats
from PyQt6.QtCore import pyqtSignal

from .plot_utils import RecursionGuard, DataCleaner, AxisCalculator


class BasePlot(FigureCanvas):
    """基础绘图画布"""
    
    # 定义信号
    region_selected = pyqtSignal(float, float)
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(BasePlot, self).__init__(self.fig)
        self.setParent(parent)
        
        # 保存父组件引用
        self.parent_dialog = parent
        
        # 初始化防护机制
        self.guard = RecursionGuard()
        self.data_cleaner = DataCleaner()
        self.axis_calc = AxisCalculator()
        
        # 创建三个子图
        self.setup_subplots()
        
        # 初始化数据
        self.data = None
        self.sampling_rate = 1000.0
        self.highlight_min = 0
        self.highlight_max = 0
        self.highlight_region = None
        self.bins = 50
        
        # 显示选项
        self.log_x = False
        self.log_y = False
        self.show_kde = False
        self.kde_line = None
        self.invert_data = False
        self.file_name = ""
        
        # 初始化选择器优化定时器
        self._init_span_updater()
    
    def setup_subplots(self):
        """设置三个子图的布局"""
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1.2, 0.8], width_ratios=[3.5, 1], hspace=0.2)
        
        self.ax1 = self.fig.add_subplot(gs[0, :])  # 顶部跨列的子图
        self.ax2 = self.fig.add_subplot(gs[1, 0])  # 左下子图
        self.ax3 = self.fig.add_subplot(gs[1, 1])  # 右下子图
        
        # 旋转右下角子图90度，使X轴与左下角子图的Y轴对齐
        self.ax3.set_xticklabels([])
        self.ax3.set_xticks([])
        
        # 共享左下角子图的Y轴
        self.ax2.sharey(self.ax3)
        self.ax3.invert_xaxis()
        
        # 设置标题和标签
        self.ax1.set_title("Full Data", fontsize=10, pad=2)
        self.ax2.set_title("Highlighted Region", fontsize=10, pad=2)
        self.ax3.set_title("Histogram", fontsize=10, pad=2)
        
        self.ax1.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax1.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax2.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax2.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax3.set_xlabel("Count", fontsize=9, labelpad=1)
        
        # 减小刻度大小
        self.ax1.tick_params(labelsize=8, pad=1)
        self.ax2.tick_params(labelsize=8, pad=1)
        self.ax3.tick_params(labelsize=8, pad=1)
        
        # 调整布局
        self.fig.tight_layout(pad=0.5)
        self.fig.subplots_adjust(left=0.08, right=0.99, wspace=0.05)
    
    def plot_data(self, data, sampling_rate=1000.0, bins=50, log_x=False, log_y=False, 
                  show_kde=False, invert_data=False, file_name=""):
        """绘制数据并设置初始高亮区域"""
        if data is None or len(data) == 0:
            print("Warning: Empty or invalid data provided to plot_data")
            return
        
        # 清理数据
        data = self.data_cleaner.clean_data(data)
        if data is None or len(data) == 0:
            print("Warning: Data became empty after cleaning")
            return
        
        # 保存数据和参数
        self.data = data
        self.sampling_rate = sampling_rate
        self.bins = bins
        self.log_x = log_x
        self.log_y = log_y
        self.show_kde = show_kde
        self.invert_data = invert_data
        self.file_name = file_name
        
        # 清除子图
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        
        # 重新设置标题和标签
        self._reset_axes_labels()
        
        # 计算时间轴
        time_axis = np.arange(len(data)) / sampling_rate
        
        # 应用数据取反
        plot_data = -data if self.invert_data else data
        plot_data = self.data_cleaner.clean_data(plot_data)
        if plot_data is None or len(plot_data) == 0:
            print("Warning: Plot data became invalid after processing")
            return
        
        # 绘制全数据图
        self.ax1.plot(time_axis, plot_data, linewidth=0.7)
        
        # 设置初始高亮区域
        self._set_initial_highlight_region(data, time_axis)
        
        # 绘制高亮区域数据
        self._plot_highlighted_region(data, time_axis)
        
        # 绘制直方图
        self._plot_histogram()
        
        # 设置轴范围和比例
        self._configure_axes(plot_data, time_axis)
        
        # 创建SpanSelector
        self._create_span_selector()
        
        # 调整布局
        self.fig.tight_layout(pad=0.5)
        self.fig.subplots_adjust(left=0.08, right=0.99, wspace=0.05)
        
        self.guard.throttled_draw(self)
    
    def _reset_axes_labels(self):
        """重新设置轴标签和标题"""
        if self.file_name:
            self.ax1.set_title(self.file_name, fontsize=10, pad=2)
        else:
            self.ax1.set_title("Full Data", fontsize=10, pad=2)
        
        self.ax2.set_title("Highlighted Region", fontsize=10, pad=2)
        self.ax3.set_title("Histogram", fontsize=10, pad=2)
        
        self.ax1.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax1.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax2.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax2.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax3.set_xlabel("Count", fontsize=9, labelpad=1)
        
        self.ax1.tick_params(labelsize=8, pad=1)
        self.ax2.tick_params(labelsize=8, pad=1)
        self.ax3.tick_params(labelsize=8, pad=1)
    
    def _set_initial_highlight_region(self, data, time_axis):
        """设置初始高亮区域"""
        self.highlight_min = 0
        self.highlight_max = max(1, len(data) // 10)
        if self.highlight_max <= self.highlight_min or self.highlight_max > len(data):
            self.highlight_max = min(max(1, len(data) // 10), len(data))
        
        self._validate_highlight_indices()
        
        # 绘制高亮区域
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
    
    def _plot_highlighted_region(self, data, time_axis):
        """绘制高亮区域数据"""
        highlighted_data = -data[self.highlight_min:self.highlight_max] if self.invert_data else data[self.highlight_min:self.highlight_max]
        highlighted_data = self.data_cleaner.clean_data(highlighted_data)
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        
        self.ax2.plot(highlighted_time, highlighted_data, linewidth=0.7)
    
    def _plot_histogram(self):
        """绘制直方图"""
        highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
        highlighted_data = self.data_cleaner.clean_data(highlighted_data)
        
        counts, bins, _ = self.ax3.hist(
            highlighted_data, 
            bins=self.bins, 
            orientation='horizontal',
            alpha=0.7
        )
        
        return counts, bins
    
    def _configure_axes(self, plot_data, time_axis):
        """配置轴的范围和比例"""
        # 计算Y轴范围
        y_min, y_max = self.axis_calc.calculate_safe_ylim(plot_data)
        
        self.ax1.set_xlim(time_axis[0], time_axis[-1])
        self.ax1.set_ylim(y_min, y_max)
        
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        if len(highlighted_time) > 0:
            self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 设置对数轴
        if self.log_x:
            self.ax3.set_xscale('log')
        else:
            self.ax3.set_xscale('linear')
            
        if self.log_y:
            self.ax3.set_yscale('log')
        else:
            self.ax3.set_yscale('linear')
        
        # 设置高亮区域Y轴范围
        highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
        highlighted_data = self.data_cleaner.clean_data(highlighted_data)
        if len(highlighted_data) > 0:
            h_y_min, h_y_max = self.axis_calc.calculate_safe_ylim(highlighted_data)
            self.ax2.set_ylim(h_y_min, h_y_max)
            self.ax3.set_ylim(h_y_min, h_y_max)
            
            # 添加KDE曲线
            if self.show_kde and len(highlighted_data) > 1:
                self.plot_kde(highlighted_data)
    
    def _create_span_selector(self):
        """创建SpanSelector"""
        self.span_selector = SpanSelector(
            self.ax1, 
            self.on_select_span, 
            'horizontal', 
            useblit=True,
            props=dict(alpha=0.3, facecolor='yellow'),
            interactive=True, 
            drag_from_anywhere=True
        )
    
    def update_highlighted_plots(self):
        """更新高亮区域和直方图"""
        if self.data is None:
            return
        
        if self.guard.is_updating("update_highlighted_plots"):
            return
            
        try:
            self.guard.set_updating("update_highlighted_plots", True)
            
            # 验证和修正高亮区域索引
            self._validate_highlight_indices()
            
            # 清除子图2和子图3
            self.ax2.clear()
            self.ax3.clear()
            
            # 重设标题和标签
            self.ax2.set_title("Highlighted Region", fontsize=10, pad=2)
            self.ax3.set_title("Histogram", fontsize=10, pad=2)
            self.ax2.set_xlabel("Time (s)", fontsize=9, labelpad=1)
            self.ax2.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
            self.ax3.set_xlabel("Count", fontsize=9, labelpad=1)
            self.ax2.tick_params(labelsize=8, pad=1)
            self.ax3.tick_params(labelsize=8, pad=1)
            
            # 获取高亮区域数据
            highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
            highlighted_data = self.data_cleaner.clean_data(highlighted_data)
            
            time_axis = np.arange(len(self.data)) / self.sampling_rate
            highlighted_time = time_axis[self.highlight_min:self.highlight_max]
            
            if highlighted_data is None or len(highlighted_data) == 0 or len(highlighted_time) == 0:
                print("Warning: Empty highlighted region detected, skipping plot update")
                self.ax2.set_xlim(0, 1)
                self.ax2.set_ylim(-1, 1)
                self.ax3.set_xlim(0, 1)
                self.ax3.set_ylim(-1, 1)
                return
            
            # 绘制高亮区域数据
            self.ax2.plot(highlighted_time, highlighted_data, linewidth=0.7)
            
            # 绘制直方图
            counts, bins, _ = self.ax3.hist(
                highlighted_data, 
                bins=self.bins, 
                orientation='horizontal',
                alpha=0.7
            )
            
            # 检查对数刻度的有效性
            if self.log_y and not np.all(counts > 0):
                print("Warning: Disabling Y log scale due to zero counts in histogram")
                self.log_y = False
            
            # 设置对数轴
            if self.log_x:
                self.ax3.set_xscale('log')
            else:
                self.ax3.set_xscale('linear')
                
            if self.log_y and np.all(counts > 0):
                self.ax3.set_yscale('log')
            else:
                self.ax3.set_yscale('linear')
            
            # 设置轴范围
            if len(highlighted_time) > 0:
                self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
            
            if len(highlighted_data) > 0:
                h_y_min, h_y_max = self.axis_calc.calculate_safe_ylim(highlighted_data)
                self.ax2.set_ylim(h_y_min, h_y_max)
                self.ax3.set_ylim(h_y_min, h_y_max)
                    
                # 绘制KDE曲线
                if self.show_kde and len(highlighted_data) > 1:
                    self.plot_kde(highlighted_data)
                    
        except Exception as e:
            print(f"Error in update_highlighted_plots: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.guard.set_updating("update_highlighted_plots", False)
    
    def plot_kde(self, data):
        """绘制核密度估计曲线"""
        if hasattr(self, 'kde_line') and self.kde_line:
            try:
                self.kde_line.remove()
            except:
                pass
        
        try:
            if len(np.unique(data)) < 2:
                return
                
            density = stats.gaussian_kde(data)
            
            min_val = np.min(data)
            max_val = np.max(data)
            xs = np.linspace(min_val, max_val, 1000)
            ys = density(xs)
            
            bins_in_range = self.bins * (max_val - min_val) / (np.max(data) - np.min(data))
            bin_width = (max_val - min_val) / bins_in_range
            scaling_factor = bin_width * len(data)
            ys = ys * scaling_factor
            
            self.kde_line, = self.ax3.plot(ys, xs, 'r-', linewidth=2)
            
        except Exception as e:
            print(f"Error plotting KDE: {e}")
    
    def _init_span_updater(self):
        """初始化延时更新定时器"""
        self.span_update_timer = None
        try:
            from PyQt6.QtCore import QTimer
            self.span_update_timer = QTimer()
            self.span_update_timer.setSingleShot(True)
            self.span_update_timer.setInterval(50)
            self.span_update_timer.timeout.connect(self._delayed_span_update)
            self.pending_span = None
        except ImportError:
            pass
    
    def on_select_span(self, xmin, xmax):
        """处理用户在全数据图上选择的区域"""
        if self.guard.is_updating("cursor"):
            return
            
        try:
            min_idx = max(0, int(xmin * self.sampling_rate))
            max_idx = min(len(self.data) - 1, int(xmax * self.sampling_rate))
            
            if hasattr(self, 'span_update_timer') and self.span_update_timer:
                self.pending_span = (min_idx, max_idx)
                self.span_update_timer.start()
                return
            
            self._update_span(min_idx, max_idx)
        except Exception as e:
            print(f"Error in on_select_span: {e}")
    
    def _delayed_span_update(self):
        """延时更新span选择器的改变"""
        if self.pending_span:
            self._update_span(*self.pending_span)
            self.pending_span = None
    
    def _update_span(self, min_idx, max_idx):
        """实际更新span选择器的改变"""
        if self.data is None or len(self.data) == 0:
            return
        
        try:
            # 验证和修正索引
            data_len = len(self.data)
            min_idx = max(0, min(min_idx, data_len - 1))
            max_idx = max(min_idx + 1, min(max_idx, data_len))
            
            # 更新高亮区域
            self.highlight_min = min_idx
            self.highlight_max = max_idx
            
            # 更新高亮区域绘图
            if self.highlight_region:
                self.highlight_region.remove()
            
            time_axis = np.arange(len(self.data)) / self.sampling_rate
            self.highlight_region = self.ax1.axvspan(
                time_axis[self.highlight_min], 
                time_axis[self.highlight_max], 
                alpha=0.3, color='yellow'
            )
            
            # 清除拟合数据（因为选择了新的高亮区域）
            if hasattr(self, 'shared_fit_data') and self.shared_fit_data and self.shared_fit_data.has_fits():
                print("[Fix] Clearing shared fit data due to region selection")
                self.shared_fit_data.clear_fits()
                
                # 通知父组件清除相关显示
                if hasattr(self, 'parent_dialog') and self.parent_dialog:
                    if hasattr(self.parent_dialog, '_clear_shared_fits_on_data_change'):
                        print("[Fix] Calling parent dialog clear method from region selection")
                        self.parent_dialog._clear_shared_fits_on_data_change()
            
            # 更新子图2和子图3（传递clear_fits=True以确保清除拟合显示）
            if hasattr(self, 'update_highlighted_plots'):
                # 检查是否有clear_fits参数支持
                import inspect
                if 'clear_fits' in inspect.signature(self.update_highlighted_plots).parameters:
                    self.update_highlighted_plots(clear_fits=True)
                else:
                    self.update_highlighted_plots()
            
            self.guard.throttled_draw(self)
            
        except Exception as e:
            print(f"Error in _update_span: {e}")
    
    def _validate_highlight_indices(self):
        """验证和修正高亮区域索引"""
        if self.data is None or len(self.data) == 0:
            self.highlight_min = 0
            self.highlight_max = 0
            return
        
        data_len = len(self.data)
        
        self.highlight_min = max(0, min(self.highlight_min, data_len - 1))
        self.highlight_max = max(0, min(self.highlight_max, data_len))
        
        if self.highlight_min >= self.highlight_max:
            default_size = min(max(1, data_len // 10), 100)
            self.highlight_min = 0
            self.highlight_max = min(default_size, data_len)
            print(f"Warning: Invalid highlight indices corrected to {self.highlight_min}-{self.highlight_max}")
    
    def update_bins(self, bins):
        """更新直方图箱数"""
        self.bins = bins
        self.update_highlighted_plots()
        self.draw()
    
    def set_log_x(self, enabled):
        """设置X轴对数显示"""
        if self.log_x != enabled:
            self.log_x = enabled
            
            if self.log_x:
                self.ax3.set_xscale('log')
            else:
                self.ax3.set_xscale('linear')
            
            self.draw()
    
    def set_log_y(self, enabled):
        """设置Y轴对数显示"""
        if self.log_y != enabled:
            self.log_y = enabled
            
            if self.log_y and enabled:
                can_use_log = self._check_log_scale_validity()
                if not can_use_log:
                    print("Warning: Cannot apply log scale - data contains zero or negative values")
                    self.log_y = False
                    return
            
            if self.log_y:
                self.ax3.set_yscale('log')
            else:
                self.ax3.set_yscale('linear')
            
            self.draw()
    
    def set_kde(self, enabled):
        """设置KDE显示"""
        if self.show_kde != enabled:
            self.show_kde = enabled
            self.update_highlighted_plots()
            self.draw()
    
    def set_invert_data(self, enabled):
        """设置数据取反"""
        if self.invert_data != enabled:
            self.invert_data = enabled
            
            if self.data is not None:
                self.plot_data(
                    self.data,
                    sampling_rate=self.sampling_rate,
                    bins=self.bins,
                    log_x=self.log_x,
                    log_y=self.log_y,
                    show_kde=self.show_kde,
                    invert_data=self.invert_data,
                    file_name=self.file_name
                )
    
    def update_highlight_size(self, size_percent):
        """更新高亮区域大小"""
        if self.data is None or len(self.data) == 0:
            return
        
        self._validate_highlight_indices()
        
        center_idx = (self.highlight_min + self.highlight_max) // 2
        
        if size_percent >= 100:
            new_min = 0
            new_max = len(self.data) - 1
        else:
            half_size = int(len(self.data) * size_percent / 100) // 2
            new_min = max(0, center_idx - half_size)
            new_max = min(len(self.data) - 1, center_idx + half_size)
        
        if new_min == self.highlight_min and new_max == self.highlight_max:
            return
            
        self.highlight_min = new_min
        self.highlight_max = new_max
        
        # 清除拟合数据（因为高亮区域大小变化了）
        if hasattr(self, 'shared_fit_data') and self.shared_fit_data and self.shared_fit_data.has_fits():
            print("[Fix] Clearing shared fit data due to highlight size change")
            self.shared_fit_data.clear_fits()
            
            # 通知父组件清除相关显示
            if hasattr(self, 'parent_dialog') and self.parent_dialog:
                if hasattr(self.parent_dialog, '_clear_shared_fits_on_data_change'):
                    print("[Fix] Calling parent dialog clear method from highlight size change")
                    self.parent_dialog._clear_shared_fits_on_data_change()
        
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新高亮区域显示（传递clear_fits=True以确保清除拟合显示）
        if hasattr(self, 'update_highlighted_plots'):
            # 检查是否有clear_fits参数支持
            import inspect
            if 'clear_fits' in inspect.signature(self.update_highlighted_plots).parameters:
                self.update_highlighted_plots(clear_fits=True)
            else:
                self.update_highlighted_plots()
        
        self.guard.throttled_draw(self)
    
    def _check_log_scale_validity(self):
        """检查数据是否适合对数刻度"""
        try:
            if not hasattr(self, 'hist_counts') or self.hist_counts is None:
                if self.data is None:
                    return False
                
                highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
                highlighted_data = self.data_cleaner.clean_data(highlighted_data)
                
                if highlighted_data is None or len(highlighted_data) == 0:
                    return False
                
                try:
                    counts, _ = np.histogram(highlighted_data, bins=self.bins)
                    return np.all(counts > 0)
                except:
                    return False
            else:
                return np.all(self.hist_counts > 0)
            
        except Exception as e:
            print(f"Error checking log scale validity: {e}")
            return False
