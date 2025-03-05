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
from matplotlib.widgets import SpanSelector
import matplotlib.patches as patches
from scipy import stats


class HistogramPlot(FigureCanvas):
    """直方图可视化画布"""
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(HistogramPlot, self).__init__(self.fig)
        self.setParent(parent)
        
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
        
        # 绘制全数据图
        self.ax1.plot(time_axis, plot_data)
        
        # 设置初始高亮区域（默认为前10%的数据）
        self.highlight_min = 0
        self.highlight_max = len(data) // 10
        if self.highlight_max <= 0:
            self.highlight_max = len(data)
        
        # 绘制高亮区域
        self.highlight_region = self.ax1.axvspan(
            time_axis[self.highlight_min], 
            time_axis[self.highlight_max], 
            alpha=0.3, color='yellow'
        )
        
        # 获取高亮区域数据（应用数据取反）
        highlighted_data = -data[self.highlight_min:self.highlight_max] if self.invert_data else data[self.highlight_min:self.highlight_max]
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
        
        # 计算数据的实际范围，减少空白
        if len(plot_data) > 0:
            # 非常激进地减少空白 - 缩小边距共0.005
            data_range = np.max(plot_data) - np.min(plot_data)
            y_min = np.min(plot_data) - 0.005 * data_range
            y_max = np.max(plot_data) + 0.005 * data_range
        else:
            y_min, y_max = -1, 1
            
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
            data_range = np.max(highlighted_data) - np.min(highlighted_data)
            # 非常激进地减少空白
            y_min = np.min(highlighted_data) - 0.005 * data_range
            y_max = np.max(highlighted_data) + 0.005 * data_range
            self.ax2.set_ylim(y_min, y_max)
            self.ax3.set_ylim(y_min, y_max)
            
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
        time_axis = np.arange(len(self.data)) / self.sampling_rate
        highlighted_time = time_axis[self.highlight_min:self.highlight_max]
        
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
        
        # 设置适当的轴范围
        self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
        
        # 得到高亮区域数据的实际范围，减少空白
        if len(highlighted_data) > 0:
            data_range = np.max(highlighted_data) - np.min(highlighted_data)
            # 非常激进地减少空白
            y_min = np.min(highlighted_data) - 0.005 * data_range
            y_max = np.max(highlighted_data) + 0.005 * data_range
            self.ax2.set_ylim(y_min, y_max)
            self.ax3.set_ylim(y_min, y_max)
            
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
            
            # 绘制KDE曲线
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
    
    def update_highlight_size(self, size_percent):
        """更新高亮区域大小"""
        if self.data is None:
            return
        
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
    
    def move_highlight(self, position_percent):
        """移动高亮区域位置"""
        if self.data is None:
            return
        
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
