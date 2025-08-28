#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Plot - 直方图绘图组件
提供直方图的数据可视化功能
"""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector, RectangleSelector
import matplotlib.patches as patches
from scipy import stats
from scipy.optimize import curve_fit
import matplotlib.gridspec as gridspec
from PyQt6.QtCore import pyqtSignal, QTimer

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector, RectangleSelector
import matplotlib.patches as patches
from scipy import stats
from scipy.optimize import curve_fit
import matplotlib.gridspec as gridspec
from PyQt6.QtCore import pyqtSignal, QTimer


class HistogramPlot(FigureCanvas):
    """直方图可视化画布"""
    
    # 定义信号
    region_selected = pyqtSignal(float, float)
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(HistogramPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        # 保存父组件引用，这样可以访问拟合信息面板
        self.parent_dialog = parent
        print(f"HistogramPlot initialized with parent: {parent}")
        
        # 创建三个子图，按照要求布局
        self.setup_subplots()
        
        # 初始化数据
        self.data = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.highlight_min = 0
        self.highlight_max = 0
        self.highlight_region = None
        self.bins = 50  # 默认直方图箱数
        
        # 初始化选择器更新器以提高性能
        self.__init_span_updater()
        
        # 显示选项
        self.log_x = False
        self.log_y = False
        self.show_kde = False
        self.kde_line = None
        self.invert_data = False  # 是否取反数据
        
        # 标题
        self.file_name = ""  # 文件名称
        
    def setup_subplots(self):
        """设置三个子图的布局"""
        # 创建一个Gridspec来管理子图的布局
        # 增加左侧子图的宽度比例，为顶部图分配更多空间，减少空白
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1.2, 0.8], width_ratios=[3.5, 1], hspace=0.2)
        
        # 创建三个子图
        self.ax1 = self.fig.add_subplot(gs[0, :])  # 顶部跨列的子图
        self.ax2 = self.fig.add_subplot(gs[1, 0])  # 左下子图
        self.ax3 = self.fig.add_subplot(gs[1, 1])  # 右下子图
        
        # 旋转右下角子图90度，使X轴与左下角子图的Y轴对齐
        self.ax3.set_xticklabels([])  # 隐藏X轴刻度标签
        self.ax3.set_xticks([])       # 隐藏X轴刻度线
        
        # 共享左下角子图的Y轴
        self.ax2.sharey(self.ax3)
        self.ax3.invert_xaxis()  # 反转X轴方向以对齐
        
        # 设置标题和标签 - 使用紧凑的布局
        self.ax1.set_title("Full Data", fontsize=10, pad=2)
        self.ax2.set_title("Highlighted Region", fontsize=10, pad=2)
        self.ax3.set_title("Histogram", fontsize=10, pad=2)
        
        self.ax1.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax1.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax2.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax2.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax3.set_xlabel("Count", fontsize=9, labelpad=1)
        
        # 减小刷度大小以节省空间
        self.ax1.tick_params(labelsize=8, pad=1)
        self.ax2.tick_params(labelsize=8, pad=1)
        self.ax3.tick_params(labelsize=8, pad=1)
        
        # 调整布局 - 显著减少左右边距，但保留足够空间显示y轴标题
        self.fig.tight_layout(pad=0.5)
        
        # 调整左边距以确保Y轴标题可见
        self.fig.subplots_adjust(left=0.08, right=0.99, wspace=0.05)
        
    def plot_data(self, data, sampling_rate=1000.0, bins=50, log_x=False, log_y=False, show_kde=False, invert_data=False, file_name=""):
        """绘制数据并设置初始高亮区域"""
        # 检查数据有效性
        if data is None or len(data) == 0:
            print("Warning: Empty or invalid data provided to plot_data")
            return
        
        # 添加数据清理步骤
        data = self._clean_data(data)
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
        
        # 设置标题（使用文件名作为标题）- 使用紧凑布局
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
        
        # 减小刷度大小以节省空间
        self.ax1.tick_params(labelsize=8, pad=1)
        self.ax2.tick_params(labelsize=8, pad=1)
        self.ax3.tick_params(labelsize=8, pad=1)
        
        # 计算时间轴
        time_axis = np.arange(len(data)) / sampling_rate
        
        # 应用数据取反（如果开启）
        plot_data = -data if self.invert_data else data
        
        # 清理处理后的数据
        plot_data = self._clean_data(plot_data)
        if plot_data is None or len(plot_data) == 0:
            print("Warning: Plot data became invalid after processing")
            return
        
        # 绘制全数据图
        self.ax1.plot(time_axis, plot_data)
        
        # 设置初始高亮区域（默认为前10%的数据）
        self.highlight_min = 0
        self.highlight_max = max(1, len(data) // 10)  # 至少为1
        if self.highlight_max <= self.highlight_min or self.highlight_max > len(data):
            self.highlight_max = min(max(1, len(data) // 10), len(data))
        
        # 验证初始索引
        self._validate_highlight_indices()
        
        # 绘制高亮区域
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 获取高亮区域数据（应用数据取反）
        highlighted_data = -data[self.highlight_min:self.highlight_max] if self.invert_data else data[self.highlight_min:self.highlight_max]
        highlighted_data = self._clean_data(highlighted_data)
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        
        # 绘制高亮区域数据
        self.ax2.plot(highlighted_time, highlighted_data)
        
        # 绘制直方图
        counts, bins, _ = self.ax3.hist(
            highlighted_data, 
            bins=self.bins, 
            orientation='horizontal',
            alpha=0.7
        )
        
        # 安全计算数据的实际范围，减少空白
        y_min, y_max = self._calculate_safe_ylim(plot_data)
            
        # 设置适当的轴范围 - 减少数据图左右两边的空白
        self.ax1.set_xlim(time_axis[0], time_axis[-1])
        self.ax1.set_ylim(y_min, y_max)
        self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 设置对数轴 - 只对直方图进行设置
        if self.log_x:
            self.ax3.set_xscale('log')
        else:
            self.ax3.set_xscale('linear')
            
        if self.log_y:
            self.ax3.set_yscale('log')
        else:
            self.ax3.set_yscale('linear')
        
        # 得到高亮区域数据的实际范围，减少空白
        if len(highlighted_data) > 0:
            h_y_min, h_y_max = self._calculate_safe_ylim(highlighted_data)
            self.ax2.set_ylim(h_y_min, h_y_max)
            self.ax3.set_ylim(h_y_min, h_y_max)
            
            # 添加KDE曲线
            if self.show_kde and len(highlighted_data) > 1:
                self.plot_kde(highlighted_data)
        
        # 创建SpanSelector，允许用户在全数据图上选择高亮区域
        self.span_selector = SpanSelector(
            self.ax1, 
            self.on_select_span, 
            'horizontal', 
            useblit=True,
            props=dict(alpha=0.3, facecolor='yellow'),
            interactive=True, 
            drag_from_anywhere=True
        )
        
        # 调整布局 - 显著减少左右边距，但保留足够空间显示y轴标题
        self.fig.tight_layout(pad=0.5)
        
        # 调整左边距以确保Y轴标题可见
        self.fig.subplots_adjust(left=0.08, right=0.99, wspace=0.05)
        
        # 重绘
        self.draw()
    
    def _clean_data(self, data):
        """清理数据，移除NaN和Inf值"""
        if data is None:
            return None
            
        try:
            # 转换为numpy数组
            data = np.asarray(data, dtype=np.float64)
            
            # 检查是否包含无效值
            invalid_mask = np.isnan(data) | np.isinf(data)
            
            if np.any(invalid_mask):
                print(f"Warning: Found {np.sum(invalid_mask)} invalid values (NaN/Inf) in data")
                
                # 如果所有数据都是无效的
                if np.all(invalid_mask):
                    print("Error: All data values are invalid (NaN/Inf)")
                    return None
                
                # 移除无效值的策略：用插值替换
                if np.sum(~invalid_mask) >= 2:  # 至少需要两个有效值进行插值
                    # 使用线性插值填充无效值
                    valid_indices = np.where(~invalid_mask)[0]
                    invalid_indices = np.where(invalid_mask)[0]
                    
                    # 对于开头和结尾的无效值，用最近的有效值填充
                    data[invalid_indices] = np.interp(
                        invalid_indices, 
                        valid_indices, 
                        data[valid_indices]
                    )
                    print(f"Interpolated {len(invalid_indices)} invalid values")
                else:
                    # 如果有效值太少，无法插值，则移除无效值
                    data = data[~invalid_mask]
                    print(f"Removed {np.sum(invalid_mask)} invalid values")
            
            # 最终检查数据是否仍然有效
            if len(data) == 0:
                print("Error: No valid data remaining after cleaning")
                return None
                
            return data
            
        except Exception as e:
            print(f"Error cleaning data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_safe_ylim(self, data):
        """安全计算Y轴限制，避免NaN和Inf"""
        try:
            if data is None or len(data) == 0:
                return -1, 1
            
            # 确保数据已清理
            data = self._clean_data(data)
            if data is None or len(data) == 0:
                return -1, 1
            
            # 计算数据范围
            data_min = np.min(data)
            data_max = np.max(data)
            
            # 检查计算结果是否有效
            if not (np.isfinite(data_min) and np.isfinite(data_max)):
                print(f"Warning: Invalid data range: min={data_min}, max={data_max}")
                return -1, 1
            
            # 如果最小值和最大值相等（常数数据）
            if data_min == data_max:
                center_val = data_min if np.isfinite(data_min) else 0
                return center_val - 0.1, center_val + 0.1
            
            # 计算数据范围和边距
            data_range = data_max - data_min
            if not np.isfinite(data_range) or data_range == 0:
                return data_min - 0.1, data_max + 0.1
            
            # 应用5‰的边距
            margin = 0.005 * data_range
            y_min = data_min - margin
            y_max = data_max + margin
            
            # 最终安全检查
            if not (np.isfinite(y_min) and np.isfinite(y_max)):
                print(f"Warning: Calculated invalid y limits: y_min={y_min}, y_max={y_max}")
                return -1, 1
            
            return y_min, y_max
            
        except Exception as e:
            print(f"Error calculating safe y limits: {e}")
            import traceback
            traceback.print_exc()
            return -1, 1
        
    def toggle_fit_labels(self, visible):
        """切换拟合标签的可见性"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return False
            
            # 设置标签可见性状态
            self.labels_visible = visible
            
            # 更新所有拟合标签的可见性
            for fit in self.gaussian_fits:
                if 'text' in fit:
                    fit['text'].set_visible(visible)
            
            # 重绘
            self.draw()
            return True
        except Exception as e:
            print(f"Error in toggle_fit_labels: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _validate_highlight_indices(self):
        """验证和修正高亮区域索引"""
        if self.data is None or len(self.data) == 0:
            self.highlight_min = 0
            self.highlight_max = 0
            return
        
        data_len = len(self.data)
        
        # 确保索引在有效范围内
        self.highlight_min = max(0, min(self.highlight_min, data_len - 1))
        self.highlight_max = max(0, min(self.highlight_max, data_len))
        
        # 确保 highlight_min < highlight_max
        if self.highlight_min >= self.highlight_max:
            # 如果索引无效，设置为默认区域（前10%或至少前100个样本）
            default_size = min(max(1, data_len // 10), 100)
            self.highlight_min = 0
            self.highlight_max = min(default_size, data_len)
            print(f"Warning: Invalid highlight indices corrected to {self.highlight_min}-{self.highlight_max}")
    
    def __init_span_updater(self):
        """初始化延时更新定时器用于优化span选择器"""
        self.span_update_timer = None
        try:
            from PyQt6.QtCore import QTimer
            self.span_update_timer = QTimer()
            self.span_update_timer.setSingleShot(True)
            self.span_update_timer.setInterval(50)  # 50ms延迟
            self.span_update_timer.timeout.connect(self._delayed_span_update)
            
            # 保存当前范围
            self.pending_span = None
        except ImportError:
            # 如果无法创建定时器，则不使用优化
            pass
    
    def on_select_span(self, xmin, xmax):
        """处理用户在全数据图上选择的区域"""
        # 将时间转换为数据点索引
        min_idx = max(0, int(xmin * self.sampling_rate))
        max_idx = min(len(self.data) - 1, int(xmax * self.sampling_rate))
        
        # 如果有定时器，使用延时更新来优化性能
        if hasattr(self, 'span_update_timer') and self.span_update_timer:
            self.pending_span = (min_idx, max_idx)
            self.span_update_timer.start()
            return
        
        # 否则直接更新
        self._update_span(min_idx, max_idx)
    
    def _delayed_span_update(self):
        """延时更新span选择器的改变"""
        if self.pending_span:
            self._update_span(*self.pending_span)
            self.pending_span = None
    
    def _update_span(self, min_idx, max_idx):
        """实际更新span选择器的改变"""
        if self.data is None or len(self.data) == 0:
            return
        
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
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()
    
    def update_highlighted_plots(self):
        """更新高亮区域和直方图"""
        if self.data is None:
            return
            
        # 验证和修正高亮区域索引
        self._validate_highlight_indices()
        
        # 清除子图2和子图3
        self.ax2.clear()
        self.ax3.clear()
        
        # 重设标题和标签 - 使用紧凑布局
        self.ax2.set_title("Highlighted Region", fontsize=10, pad=2)
        self.ax3.set_title("Histogram", fontsize=10, pad=2)
        
        self.ax2.set_xlabel("Time (s)", fontsize=9, labelpad=1)
        self.ax2.set_ylabel("Amplitude", fontsize=9, labelpad=2, rotation=90)
        self.ax3.set_xlabel("Count", fontsize=9, labelpad=1)
        
        # 减小刷度大小以节省空间
        self.ax2.tick_params(labelsize=8, pad=1)
        self.ax3.tick_params(labelsize=8, pad=1)
        
        # 获取高亮区域数据（应用数据取反）
        highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
        # 清理高亮数据
        highlighted_data = self._clean_data(highlighted_data)
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        
        # 检查是否有有效的高亮数据
        if highlighted_data is None or len(highlighted_data) == 0 or len(highlighted_time) == 0:
            print("Warning: Empty highlighted region detected, skipping plot update")
            # 设置默认的轴范围避免错误
            self.ax2.set_xlim(0, 1)
            self.ax2.set_ylim(-1, 1)
            self.ax3.set_xlim(0, 1)
            self.ax3.set_ylim(-1, 1)
            return
        
        # 绘制高亮区域数据
        self.ax2.plot(highlighted_time, highlighted_data)
        
        # 设置对数轴 - 只对直方图生效
        if self.log_x:
            self.ax3.set_xscale('log')
        else:
            self.ax3.set_xscale('linear')
            
        if self.log_y:
            self.ax3.set_yscale('log')
        else:
            self.ax3.set_yscale('linear')
        
        # 绘制直方图
        counts, bins, _ = self.ax3.hist(
            highlighted_data, 
            bins=self.bins, 
            orientation='horizontal',
            alpha=0.7
        )
        
        # 安全地设置轴范围
        if len(highlighted_time) > 0:
            self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 安全计算高亮区域数据的实际范围
        if len(highlighted_data) > 0:
            h_y_min, h_y_max = self._calculate_safe_ylim(highlighted_data)
            self.ax2.set_ylim(h_y_min, h_y_max)
            self.ax3.set_ylim(h_y_min, h_y_max)
            
            # 绘制KDE曲线
            if self.show_kde and len(highlighted_data) > 1:
                self.plot_kde(highlighted_data)
    
    def plot_kde(self, data):
        """绘制核密度估计曲线"""
        # 先移除先前的KDE曲线
        if hasattr(self, 'kde_line') and self.kde_line:
            try:
                self.kde_line.remove()
            except:
                pass
        
        try:
            # 确保数据在KDE有意义
            if len(np.unique(data)) < 2:
                return
                
            # 计算KDE
            density = stats.gaussian_kde(data)
            
            # 创建计算点
            min_val = np.min(data)
            max_val = np.max(data)
            xs = np.linspace(min_val, max_val, 1000)
            ys = density(xs)
            
            # 将KDE缩放以与hist高度匹配
            bins_in_range = self.bins * (max_val - min_val) / (np.max(data) - np.min(data))
            bin_width = (max_val - min_val) / bins_in_range
            scaling_factor = bin_width * len(data)
            ys = ys * scaling_factor
            
            # 绘制KDE曲线，不添加标签和图例
            self.kde_line, = self.ax3.plot(ys, xs, 'r-', linewidth=2)
            
        except Exception as e:
            print(f"Error plotting KDE: {e}")
            import traceback
            traceback.print_exc()
    
    def update_bins(self, bins):
        """更新直方图箱数"""
        self.bins = bins
        self.update_highlighted_plots()
        self.draw()
    
    def set_log_x(self, enabled):
        """设置X轴对数显示"""
        if self.log_x != enabled:
            self.log_x = enabled
            
            # 只更新直方图的轴类型
            if self.log_x:
                self.ax3.set_xscale('log')
            else:
                self.ax3.set_xscale('linear')
            
            # 重绘
            self.draw()
    
    def set_log_y(self, enabled):
        """设置Y轴对数显示"""
        if self.log_y != enabled:
            self.log_y = enabled
            
            # 只更新直方图的轴类型
            if self.log_y:
                self.ax3.set_yscale('log')
            else:
                self.ax3.set_yscale('linear')
            
            # 重绘
            self.draw()
    
    def set_kde(self, enabled):
        """设置KDE显示"""
        if self.show_kde != enabled:
            self.show_kde = enabled
            
            # 重新计算高亮区域的绘图
            self.update_highlighted_plots()
            
            # 重绘
            self.draw()
    
    def set_invert_data(self, enabled):
        """设置数据取反"""
        if self.invert_data != enabled:
            self.invert_data = enabled
            
            # 如果有数据，重新绘制
            if self.data is not None:
                # 先更新变量值
                time_axis = np.arange(len(self.data)) / self.sampling_rate
                plot_data = -self.data if self.invert_data else self.data
                
                # 重新绘制全部数据，完全刷新所有图表
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
                
                # 如果是在subplot3直方图视图中，那么需要单独处理
                if not hasattr(self, 'ax1'):
                    # 获取高亮区域数据
                    highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
                    
                    # 重新绘制subplot3直方图
                    self.plot_subplot3_histogram(
                        highlighted_data,
                        bins=self.bins,
                        log_x=self.log_x,
                        log_y=self.log_y,
                        show_kde=self.show_kde,
                        file_name=self.file_name
                    )
    
    def update_highlight_size(self, size_percent):
        """更新高亮区域大小"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 验证当前索引
        self._validate_highlight_indices()
        
        # 计算新的高亮区域大小
        center_idx = (self.highlight_min + self.highlight_max) // 2
        
        # 处理特殊情况：100%应该覆盖全部数据
        if size_percent >= 100:
            new_min = 0
            new_max = len(self.data) - 1
        else:
            # 计算与中心点的距离（单侧）
            half_size = int(len(self.data) * size_percent / 100) // 2  # 除以100把百分比转为小数，再除以2得到单侧距离
            
            # 更新高亮区域
            new_min = max(0, center_idx - half_size)
            new_max = min(len(self.data) - 1, center_idx + half_size)
        
        # 检查是否真的变化，如果没有变化则不更新
        if new_min == self.highlight_min and new_max == self.highlight_max:
            return
            
        self.highlight_min = new_min
        self.highlight_max = new_max
        
        # 更新高亮区域绘图
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()
    
    def plot_subplot3_histogram(self, data, bins=50, log_x=False, log_y=False, show_kde=False, file_name=""):
        """创建一个单独的subplot3直方图视图"""
        if data is None or len(data) == 0:
            return
        
        # 清理数据
        data = self._clean_data(data)
        if data is None or len(data) == 0:
            print("Warning: Data became empty after cleaning in subplot3")
            return
            
        # 清除当前figure
        self.fig.clear()
        
        # 创建一个subplot
        self.ax = self.fig.add_subplot(111)
        
        # 保存数据和显示参数
        self.histogram_data = data
        self.histogram_bins = bins
        self.histogram_log_x = log_x
        self.histogram_log_y = log_y
        self.histogram_show_kde = show_kde
        self.histogram_file_name = file_name
        
        # 初始化矩形选择器的优化定时器
        if not hasattr(self, 'rect_select_timer'):
            self.rect_select_timer = QTimer()
            self.rect_select_timer.setSingleShot(True)
            self.rect_select_timer.setInterval(800)  # 增加到800ms的延迟来降低卡顿
            self.rect_select_timer.timeout.connect(self._delayed_rect_select)
        self.pending_rect_coords = None
        
        # 初始化高斯拟合区域列表
        if not hasattr(self, 'fit_regions'):
            self.fit_regions = []
        else:
            self.fit_regions.clear()
        
        # 初始化高斯拟合结果列表
        if not hasattr(self, 'gaussian_fits'):
            self.gaussian_fits = []
        else:
            self.gaussian_fits.clear()
            
        # 当前高亮的拟合索引
        self.highlighted_fit_index = -1
        
        # 设置标题
        title = "Histogram of Highlighted Region"
        if file_name:
            title = f"{file_name} - {title}"
        self.ax.set_title(title, fontsize=12)
        
        # 添加使用提示 - 放在右下角避免与标题重叠
        msg = "Click and drag to select regions for Gaussian fitting"
        self.ax.annotate(msg, xy=(0.98, 0.02), xycoords='figure fraction', 
                    ha='right', va='bottom', fontsize=9, color='navy',
                    bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        # 设置坐标轴标签
        self.ax.set_xlabel("Amplitude", fontsize=10)
        self.ax.set_ylabel("Count", fontsize=10)
        
        # 设置对数轴（如果启用）
        if log_x:
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')
            
        if log_y:
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        
        # 绘制直方图 - 调低透明度使背景更浅，并设置较低的zorder以使其位于数据后面
        self.histogram = self.ax.hist(
            data, 
            bins=bins, 
            alpha=0.5,
            color='skyblue',
            edgecolor='black',
            zorder=5  # 设置较低的层级
        )
        
        # 解析直方图数据
        self.hist_counts = self.histogram[0]
        self.hist_bin_edges = self.histogram[1]
        self.hist_bin_centers = (self.hist_bin_edges[:-1] + self.hist_bin_edges[1:]) / 2
        
        # 绘制KDE曲线（如果启用）
        if show_kde and len(np.unique(data)) > 1:
            try:
                # 计算KDE
                density = stats.gaussian_kde(data)
                
                # 创建计算点
                min_val = np.min(data)
                max_val = np.max(data)
                xs = np.linspace(min_val, max_val, 1000)
                ys = density(xs)
                
                # 将KDE缩放以与hist高度匹配
                bins_in_range = bins * (max_val - min_val) / (np.max(data) - np.min(data))
                bin_width = (max_val - min_val) / bins_in_range
                scaling_factor = bin_width * len(data)
                ys = ys * scaling_factor
                
                # 绘制KDE曲线 - 将其放在直方图之上
                self.ax.plot(xs, ys, 'r-', linewidth=2, zorder=10)
                # 移除legend
                
            except Exception as e:
                print(f"Error plotting KDE for subplot3: {e}")
                import traceback
                traceback.print_exc()
        
        # 添加网格线以便于阅读
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        # 移除统计信息文本框
        # (已删除文本框)
        
        # 创建矩形选择器，允许框选区域进行高斯拟合
        self.rect_selector = RectangleSelector(
            self.ax,
            self.on_rect_select,
            useblit=True,
            button=[1],  # 只使用左键
            minspanx=10,  # 增加最小距离
            minspany=10,  # 增加最小距离
            spancoords='pixels',
            interactive=False,  # 禁用交互式以减少卡顿
            props=dict(facecolor='red', edgecolor='black', alpha=0.15, fill=True)
        )
        
        # 初始化信息显示面板
        # 不再创建setup_info_panel，因为我们现在使用单独的FitInfoPanel
        # 只保留信息字符串用于其它功能
        self.fit_info_str = "No fits yet"
        
        # 标签可见性状态
        self.labels_visible = True
        
        # 调整布局
        self.fig.tight_layout()
        
        # 重绘
        self.draw()
        
    def on_rect_select(self, eclick, erelease):
        """处理矩形器的框选区域"""
        try:
            # 获取选择的x范围
            x_min, x_max = sorted([eclick.xdata, erelease.xdata])
            
            # 使用延时定时器来减少卡顿
            self.pending_rect_coords = (x_min, x_max)
            self.rect_select_timer.start()
            
        except Exception as e:
            print(f"Error in rectangle selector: {e}")
            import traceback
            traceback.print_exc()
            
    def _delayed_rect_select(self):
        """延迟处理框选区域，以减少卡顿"""
        if not self.pending_rect_coords:
            return
            
        x_min, x_max = self.pending_rect_coords
        
        # 将坐标发送给相应的信号
        self.region_selected.emit(x_min, x_max)
        
        # 高亮选择区域
        self.highlight_selected_region(x_min, x_max)
        
        # 进行高斯拟合
        self.fit_gaussian_to_selected_region(x_min, x_max)
        
        # 重置坐标
        self.pending_rect_coords = None
    
    def highlight_selected_region(self, x_min, x_max):
        """高亮框选的区域"""
        # 添加到拟合区域列表
        region = self.ax.axvspan(x_min, x_max, alpha=0.08, color='green', zorder=0)
        self.fit_regions.append((x_min, x_max, region))
    
    def fit_gaussian_to_selected_region(self, x_min, x_max):
        """对选择的区域进行高斯拟合"""
        try:
            # 获取数据在选择区域内的部分
            mask = (self.histogram_data >= x_min) & (self.histogram_data <= x_max)
            selected_data = self.histogram_data[mask]
            
            if len(selected_data) < 10:  # 至少需要足够的数据点进行拟合
                print("Not enough data points for Gaussian fitting")
                return
            
            # 取得箱子下标
            bin_mask = (self.hist_bin_centers >= x_min) & (self.hist_bin_centers <= x_max)
            x_data = self.hist_bin_centers[bin_mask]
            y_data = self.hist_counts[bin_mask]
            
            if len(x_data) < 3:  # 至少需要足够的直方图点进行拟合
                print("Not enough histogram bins for Gaussian fitting")
                return
                
            # 高斯函数
            def gaussian(x, amp, mu, sigma):
                return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
            
            # 初始估计高斯参数: 振幅，均值，标准差
            amp_init = y_data.max()  # 使用直方图的最大高度估计振幅
            mean_init = np.mean(selected_data)
            std_init = np.std(selected_data)
            
            # 添加边界约束以提高拟合稳定性
            bounds = (
                [0, x_min, 0],           # 下界: 振幅大于0，均值在选择区域内，标准差大于0
                [amp_init*3, x_max, (x_max-x_min)]  # 上界: 振幅有合理限制，均值在选择区域内，标准差有合理限制
            )
            
            p0 = [amp_init, mean_init, std_init]
            
            # 在图上创建微小的bin来拟合高斯曲线 - 减少点数以提高性能
            x_fit = np.linspace(x_min, x_max, 150)
            
            # 拟合高斯函数并让其更应对拟合失败
            try:
                popt, _ = curve_fit(gaussian, x_data, y_data, p0=p0, bounds=bounds, maxfev=2000)
                
                # 计算指定高斯组件的颜色
                colors = ['red', 'blue', 'purple', 'orange', 'green', 'magenta', 'cyan', 'brown', 'olive', 'teal']
                color_idx = len(self.gaussian_fits) % len(colors)
                fit_color = colors[color_idx]
                
                # 将拟合曲线绘到图上，使用颜色循环
                y_fit = gaussian(x_fit, *popt)
                line, = self.ax.plot(x_fit, y_fit, '-', linewidth=2.5, color=fit_color, zorder=15)
                
                # 创建文本标签显示拟合参数
                amp, mu, sigma = popt
                fwhm = 2.355 * sigma  # 半高宽计算
                fit_num = len(self.gaussian_fits) + 1
                text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
                
                # 使用水平和垂直偏移来定位文本，更清晰
                # 使用与曲线相同的颜色
                text_obj = self.ax.text(mu, amp*1.05, text, ha='center', va='bottom', fontsize=9,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor=fit_color, boxstyle='round'),
                    color=fit_color, zorder=20)
                
                # 如果当前标签不可见，隐藏文本
                if not self.labels_visible:
                    text_obj.set_visible(False)
                
                # 将拟合参数添加到列表
                self.gaussian_fits.append({
                    'popt': popt,
                    'x_range': (x_min, x_max),
                    'line': line,
                    'text': text_obj,
                    'color': fit_color
                })
                
                # 添加到拟合信息面板（如果存在）
                if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                    print(f"Adding fit to panel: {len(self.gaussian_fits)}, {amp:.2f}, {mu:.4f}, {sigma:.4f}")
                    self.parent_dialog.fit_info_panel.add_fit(len(self.gaussian_fits), amp, mu, sigma, (x_min, x_max), fit_color)
                
                # 收集拟合信息字符串
                # 全部拟合信息
                self.update_fit_info_string()
                
                # 重绘
                self.draw()
                
            except RuntimeError as e:
                print(f"Error fitting Gaussian: {e}")
                
        except Exception as e:
            print(f"Error in Gaussian fitting: {e}")
            import traceback
            traceback.print_exc()
    
    def update_fit_info_string(self):
        """更新拟合信息字符串(用于导出和复制)"""
        if not hasattr(self, 'gaussian_fits') or len(self.gaussian_fits) == 0:
            self.fit_info_str = "No fits yet"
            return
            
        # 创建拟合信息字符串，包含半高宽（FWHM）
        info_lines = ["===== Fitting Results ====="]
        for i, fit in enumerate(self.gaussian_fits):
            amp, mu, sigma = fit['popt']
            fwhm = 2.355 * sigma  # 计算半高宽（FWHM）
            info_lines.append(f"Gaussian {i+1}:")
            info_lines.append(f"  Peak position: {mu:.4f}")
            info_lines.append(f"  Amplitude: {amp:.2f}")
            info_lines.append(f"  Sigma: {sigma:.4f}")
            info_lines.append(f"  FWHM: {fwhm:.4f}")
            info_lines.append(f"  Range: {fit['x_range'][0]:.3f}-{fit['x_range'][1]:.3f}")
            info_lines.append("")
        
        # 计算总结
        if len(self.gaussian_fits) > 1:
            info_lines.append("==== Multi-Peak Analysis ====")
            peaks = [fit['popt'][1] for fit in self.gaussian_fits]
            # 计算相邻峰之间的距离
            sorted_peaks = sorted(peaks)
            for i in range(len(sorted_peaks)-1):
                delta = sorted_peaks[i+1] - sorted_peaks[i]
                info_lines.append(f"Peak{i+1} to Peak{i+2} distance: {delta:.4f}")
            
        self.fit_info_str = "\n".join(info_lines)
    
    def clear_fits(self):
        """清除所有高斯拟合"""
        try:
            if hasattr(self, 'gaussian_fits'):
                # 删除所有拟合曲线和文本
                for fit in self.gaussian_fits:
                    if 'line' in fit and fit['line'] in self.ax.lines:
                        fit['line'].remove()
                    if 'text' in fit:
                        fit['text'].remove()
                self.gaussian_fits.clear()
            
            if hasattr(self, 'fit_regions'):
                # 删除所有区域高亮
                for _, _, region in self.fit_regions:
                    if region in self.ax.patches:
                        region.remove()
                self.fit_regions.clear()
            
            # 重置拟合信息字符串
            self.fit_info_str = "No fits yet"
            
            # 清除拟合信息面板
            if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                self.parent_dialog.fit_info_panel.clear_all_fits()
            
            # 重绘
            self.draw()
            
        except Exception as e:
            print(f"Error clearing fits: {e}")
            import traceback
            traceback.print_exc()
    
    def delete_specific_fit(self, fit_index):
        """删除特定的拟合"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return
                
            # 查找对应索引的拟合
            for i, fit in enumerate(self.gaussian_fits):
                if len(self.gaussian_fits) == fit_index or i+1 == fit_index:  # 支持以集合索引或显示索引查找
                    # 移除环境中的元素
                    if 'line' in fit and fit['line'] in self.ax.lines:
                        fit['line'].remove()
                    if 'text' in fit:
                        fit['text'].remove()
                    
                    # 移除相关的区域高亮
                    for j, (x_min, x_max, region) in enumerate(self.fit_regions):
                        if j == i:  # 假设区域和拟合是一一对应的
                            if region in self.ax.patches:
                                region.remove()
                            self.fit_regions.pop(j)
                            break
                    
                    # 从列表中移除
                    self.gaussian_fits.pop(i)
                    
                    # 重新绘制
                    self.draw()
                    return True
            
            return False  # 返回是否成功删除
                
        except Exception as e:
            print(f"Error in delete_specific_fit: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_specific_fit(self, fit_index, new_params):
        """更新特定拟合的参数"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return False
                
            # 查找对应索引的拟合
            for i, fit in enumerate(self.gaussian_fits):
                if len(self.gaussian_fits) == fit_index or i+1 == fit_index:  # 支持以集合索引或显示索引查找
                    # 获取当前拟合的x范围
                    x_range = fit['x_range']
                    color = fit['color']
                    
                    # 定义高斯函数
                    def gaussian(x, amp, mu, sigma):
                        return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
                    
                    # 更新拟合参数
                    amp = new_params['amp']
                    mu = new_params['mu']
                    sigma = new_params['sigma']
                    
                    # 计算新的拟合曲线
                    x_fit = np.linspace(x_range[0], x_range[1], 150)
                    y_fit = gaussian(x_fit, amp, mu, sigma)
                    
                    # 移除旧的曲线和文本
                    if 'line' in fit and fit['line'] in self.ax.lines:
                        fit['line'].remove()
                    if 'text' in fit:
                        fit['text'].remove()
                    
                    # 创建新的曲线和文本
                    line, = self.ax.plot(x_fit, y_fit, '-', linewidth=2.5, color=color, zorder=15)
                    
                    # 更新呈现参数
                    fit_num = i + 1
                    text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
                    text_obj = self.ax.text(mu, amp*1.05, text, ha='center', va='bottom', fontsize=9,
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor=color, boxstyle='round'),
                        color=color, zorder=20)
                    
                    # 如果标签当前不可见，则隐藏文本
                    text_obj.set_visible(self.labels_visible)
                    
                    # 更新拟合对象
                    self.gaussian_fits[i] = {
                        'popt': (amp, mu, sigma),
                        'x_range': x_range,
                        'line': line,
                        'text': text_obj,
                        'color': color
                    }
                    
                    # 更新拟合信息字符串
                    self.update_fit_info_string()
                    
                    # 更新拟合信息面板(如果存在)
                    if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                        self.parent_dialog.fit_info_panel.update_fit(fit_num, amp, mu, sigma, x_range, color)
                    
                    # 重新绘制
                    self.draw()
                    return True
            
            return False  # 返回是否成功更新
                
        except Exception as e:
            print(f"Error in update_specific_fit: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def highlight_specific_fit(self, fit_index):
        """高亮显示特定的拟合"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return False
                
            # 取消之前的高亮
            if self.highlighted_fit_index >= 0 and self.highlighted_fit_index < len(self.gaussian_fits):
                old_fit = self.gaussian_fits[self.highlighted_fit_index]
                if 'line' in old_fit:
                    old_fit['line'].set_linewidth(2.5)  # 恢复正常线宽
                
            # 查找对应索引的拟合
            actual_index = -1
            for i, fit in enumerate(self.gaussian_fits):
                if len(self.gaussian_fits) == fit_index or i+1 == fit_index:  # 支持以集合索引或显示索引查找
                    # 高亮显示该拟合
                    if 'line' in fit:
                        fit['line'].set_linewidth(4.0)  # 增加线宽高亮显示
                    
                    # 记录当前高亮的索引
                    self.highlighted_fit_index = i
                    actual_index = i
                    break
            
            # 重新绘制
            if actual_index >= 0:
                self.draw()
                return True
            else:
                self.highlighted_fit_index = -1
                return False
                
        except Exception as e:
            print(f"Error in highlight_specific_fit: {e}")
            import traceback
            traceback.print_exc()
            self.highlighted_fit_index = -1
            return False
        
    def move_highlight(self, position_percent):
        """移动高亮区域位置"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 验证当前索引
        self._validate_highlight_indices()
        
        # 计算高亮区域大小
        highlight_size = self.highlight_max - self.highlight_min
        
        # 处理特殊情况：100%大小
        if highlight_size >= len(self.data) - 1:
            new_min = 0
            new_max = len(self.data) - 1
        else:
            # 根据百分比计算新的中心位置
            max_position = len(self.data) - 1
            new_center = int(max_position * position_percent / 100)
            
            # 算出新的边界
            new_min = new_center - highlight_size // 2
            new_max = new_min + highlight_size
            
            # 处理右边界超出情况
            if new_max > max_position:
                # 将右边界调整到数据结尾
                new_max = max_position
                # 相应地调整左边界，保持高亮区域大小不变
                new_min = max(0, new_max - highlight_size)
            
            # 处理左边界超出情况
            if new_min < 0:
                new_min = 0
                # 相应地调整右边界，保持高亮区域大小不变
                new_max = min(max_position, new_min + highlight_size)
        
        # 检查是否真的变化，如果没有变化则不更新
        if new_min == self.highlight_min and new_max == self.highlight_max:
            return
            
        # 更新高亮区域
        self.highlight_min = new_min
        self.highlight_max = new_max
        
        # 更新高亮区域绘图
        if self.highlight_region:
            self.highlight_region.remove()
        
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 更新子图2和子图3
        self.update_highlighted_plots()
        
        # 重绘
        self.draw()

    def toggle_fit_labels(self, visible):
        """切换拟合标签的可见性"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return False
            
            # 设置标签可见性状态
            self.labels_visible = visible
            
            # 更新所有拟合标签的可见性
            for fit in self.gaussian_fits:
                if 'text' in fit:
                    fit['text'].set_visible(visible)
            
            # 重绘
            self.draw()
            return True
        except Exception as e:
            print(f"Error in toggle_fit_labels: {e}")
            import traceback
            traceback.print_exc()
            return False
