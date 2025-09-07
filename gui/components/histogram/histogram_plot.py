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
from PyQt6.QtCore import pyqtSignal, QTimer, Qt


class FitDataManager:
    """拟合数据管理器，用于在不同的视图之间同步拟合结果"""
    
    def __init__(self):
        self.gaussian_fits = []  # 存储所有拟合结果
        self.fit_regions = []    # 存储拟合区域
        self.data_range = None   # 数据范围（用于验证拟合是否适用）
        self.data_hash = None    # 数据哈希值（用于检测数据变化）
    
    def save_fits(self, fits, regions, data_range=None, data_hash=None):
        """保存拟合结果"""
        self.gaussian_fits = [self._copy_fit(fit) for fit in fits]
        self.fit_regions = [(r[0], r[1]) for r in regions if len(r) >= 2] if regions else []
        self.data_range = data_range
        self.data_hash = data_hash
        print(f"Saved {len(self.gaussian_fits)} fits")
    
    def get_fits(self):
        """获取拟合结果"""
        return self.gaussian_fits, self.fit_regions
    
    def has_fits(self):
        """检查是否有拟合结果"""
        return len(self.gaussian_fits) > 0
    
    def clear_fits(self):
        """清除所有拟合结果"""
        self.gaussian_fits.clear()
        self.fit_regions.clear()
        self.data_range = None
        self.data_hash = None
    
    def is_compatible_with_data(self, data_range, data_hash):
        """检查拟合结果是否与当前数据兼容"""
        if self.data_hash is None or data_hash is None:
            return False
        return self.data_hash == data_hash
    
    def _copy_fit(self, fit):
        """复制拟合数据（不包括绘图对象）"""
        return {
            'popt': fit.get('popt'),
            'x_range': fit.get('x_range'),
            'color': fit.get('color')
        }


class HistogramPlot(FigureCanvas):
    """直方图可视化画布（修复版）"""
    
    # 定义信号
    region_selected = pyqtSignal(float, float)
    cursor_deselected = pyqtSignal()  # cursor被取消选中
    cursor_selected = pyqtSignal(int)    # cursor被选中（发送cursor_id）
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(HistogramPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        # 保存父组件引用，这样可以访问拟合信息面板
        self.parent_dialog = parent
        print(f"HistogramPlot initialized with parent: {parent}")
        
        # 【新增】拟合数据管理系统
        self.shared_fit_data = None  # 共享的拟合数据引用
        self.fit_data_manager = FitDataManager()  # 本地拟合数据管理器
        
        # 【修复点1】添加递归调用防护机制
        self._updating_plot = False  # 防止plot更新的递归
        self._updating_cursors = False  # 防止cursor更新的递归
        self._drawing = False  # 防止draw()调用的递归
        self._last_draw_time = 0  # 限制draw()调用频率
        self._draw_throttle_interval = 0.05  # 50ms的绘制间隔限制
        
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
        
        # Cursor 功能相关变量
        self.cursors = []  # 存储所有cursor的列表
        self.selected_cursor = None  # 当前选中的cursor
        self.dragging = False  # 是否正在拖拽
        self.drag_start_y = None  # 拖拽开始的y坐标
        self.cursor_colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        self.cursor_counter = 0  # cursor计数器，用于生成唯一ID
        
        # 【新增】初始化主视图中subplot3拟合线条跟踪
        self._ax3_fit_lines = []  # 确保在初始化时就创建空列表
        
        # 设置焦点策略以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 连接鼠标事件
        self.mpl_connect('button_press_event', self.on_cursor_mouse_press)
        self.mpl_connect('motion_notify_event', self.on_cursor_mouse_move)
        self.mpl_connect('button_release_event', self.on_cursor_mouse_release)
    
    def _throttled_draw(self):
        """限制频率的绘制方法，防止过度绘制导致的性能问题"""
        # 【修复点7】限制draw()调用频率
        if self._drawing:
            return  # 如果正在绘制中，跳过
            
        import time
        current_time = time.time()
        
        # 检查是否在限制间隔内
        if current_time - self._last_draw_time < self._draw_throttle_interval:
            return  # 距离上次绘制时间太短，跳过
        
        try:
            self._drawing = True
            self._last_draw_time = current_time
            self.draw()
        except Exception as e:
            print(f"Error in _throttled_draw: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._drawing = False
        
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
        self.ax1.plot(time_axis, plot_data, linewidth=0.7)
        
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
        self.ax2.plot(highlighted_time, highlighted_data, linewidth=0.7)
        
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
        
        # 使用限制频率的重绘
        self._throttled_draw()
    
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
    
    def _check_log_scale_validity(self):
        """检查数据是否适合对数刻度"""
        try:
            # 检查是否有直方图数据
            if not hasattr(self, 'hist_counts') or self.hist_counts is None:
                # 如果没有直方图数据，检查原始数据
                if self.data is None:
                    return False
                
                # 获取高亮数据并检查
                highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
                highlighted_data = self._clean_data(highlighted_data)
                
                if highlighted_data is None or len(highlighted_data) == 0:
                    return False
                
                # 计算直方图统计
                try:
                    counts, _ = np.histogram(highlighted_data, bins=self.bins)
                    return np.all(counts > 0)  # 所有bin都必须有正值
                except:
                    return False
            else:
                # 使用已存在的直方图数据
                return np.all(self.hist_counts > 0)
            
        except Exception as e:
            print(f"Error checking log scale validity: {e}")
            return False
        

    
    def plot_subplot3_histogram(self, data, bins=50, log_x=False, log_y=False, show_kde=False, file_name=""):
        """
        为subplot3绘制直方图（用于Histogram标签页）
        支持cursor功能和实时更新
        """
        try:
            # 清理数据
            cleaned_data = self._clean_data(data)
            if cleaned_data is None or len(cleaned_data) == 0:
                print("Warning: No valid data for subplot3 histogram")
                return
            
            # 设置当前绘图为histogram模式（为了区分主视图模式）
            self.is_histogram_mode = True
            self.histogram_data = cleaned_data
            self.histogram_bins = bins
            
            # 使用ax作为主要的直方图轴（对于subplot3，ax就是唯一的轴）
            if not hasattr(self, 'ax'):
                # 如果没有ax，创建一个新的figure和axis
                self.fig.clear()
                self.ax = self.fig.add_subplot(111)
            else:
                self.ax.clear()
            
            # 绘制直方图
            self.hist_counts, self.hist_bin_edges, _ = self.ax.hist(
                cleaned_data, bins=bins, alpha=0.7, density=False
            )
            
            # 设置标题和标签
            if file_name:
                self.ax.set_title(f"Histogram - {file_name}", fontsize=12, pad=10)
            else:
                self.ax.set_title("Histogram", fontsize=12, pad=10)
            
            self.ax.set_xlabel("Value", fontsize=11)
            self.ax.set_ylabel("Count", fontsize=11)
            
            # 设置对数刻度
            if log_x:
                try:
                    self.ax.set_xscale('log')
                    self.log_x = True
                except:
                    print("Cannot set X-axis to log scale")
                    self.log_x = False
            else:
                self.ax.set_xscale('linear')
                self.log_x = False
                
            if log_y:
                # 检查是否适合对数刻度
                if self._check_log_scale_validity():
                    try:
                        self.ax.set_yscale('log')
                        self.log_y = True
                    except:
                        print("Cannot set Y-axis to log scale")
                        self.log_y = False
                        self.ax.set_yscale('linear')
                else:
                    print("Y-axis log scale disabled: histogram contains zero counts")
                    self.log_y = False
                    self.ax.set_yscale('linear')
            else:
                self.ax.set_yscale('linear')
                self.log_y = False
            
            # 添加KDE曲线
            if show_kde and len(cleaned_data) > 1:
                try:
                    from scipy.stats import gaussian_kde
                    kde = gaussian_kde(cleaned_data)
                    x_range = np.linspace(cleaned_data.min(), cleaned_data.max(), 200)
                    kde_values = kde(x_range)
                    
                    # 将KDE值缩放到直方图的尺度
                    scale_factor = len(cleaned_data) * (self.hist_bin_edges[1] - self.hist_bin_edges[0])
                    kde_values = kde_values * scale_factor
                    
                    self.kde_line = self.ax.plot(x_range, kde_values, 'r-', 
                                               linewidth=2, alpha=0.8, label='KDE')[0]
                    self.ax.legend()
                except Exception as e:
                    print(f"Error adding KDE: {e}")
            
            # 在histogram模式下，cursor显示在主axis上
            # 刷新cursor显示
            if hasattr(self, 'cursors') and self.cursors:
                self.refresh_cursors_for_histogram_mode()
            
            # 调整布局
            self.fig.tight_layout(pad=1.0)
            
            # 使用限制频率的重绘
            self._throttled_draw()
            
        except Exception as e:
            print(f"Error plotting subplot3 histogram: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_cursors_for_histogram_mode(self):
        """
        在直方图模式下刷新cursor显示
        """
        try:
            if not hasattr(self, 'cursors') or not self.cursors:
                return
                
            # 在直方图模式下，cursor显示为垂直线（因为直方图是垂直的）
            for cursor in self.cursors:
                y_pos = cursor['y_position']
                color = cursor['color']
                
                # 在主轴上创建垂直线
                if hasattr(self, 'ax'):
                    # 移除之前的线（如果存在）
                    if 'histogram_line' in cursor and cursor['histogram_line']:
                        try:
                            cursor['histogram_line'].remove()
                        except:
                            pass
                    
                    # 创建新的垂直线
                    cursor['histogram_line'] = self.ax.axvline(
                        x=y_pos, color=color, 
                        linestyle='--', linewidth=0.8, 
                        alpha=0.6, zorder=20
                    )
                    
                    # 如果是选中的cursor，加粗显示
                    if cursor.get('selected', False):
                        cursor['histogram_line'].set_linewidth(1.5)
                        cursor['histogram_line'].set_alpha(0.9)
                        
        except Exception as e:
            print(f"Error refreshing cursors for histogram mode: {e}")
            import traceback
            traceback.print_exc()
    
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
        """处理用户在全数据图上选择的区域 - 修复更新问题"""
        # 移除过于严格的递归防护，只在真正需要时防护
        if self._updating_cursors:  # 只在更新cursor时防护
            return
            
        try:
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
        except Exception as e:
            print(f"Error in on_select_span: {e}")
            import traceback
            traceback.print_exc()
    
    def _delayed_span_update(self):
        """延时更新span选择器的改变"""
        if self.pending_span:
            self._update_span(*self.pending_span)
            self.pending_span = None
    
    def _update_span(self, min_idx, max_idx):
        """实际更新span选择器的改变 - 修复更新问题"""
        # 简化防护逻辑，只检查基本数据有效性
        if self.data is None or len(self.data) == 0:
            return
        
        try:
            # [核心修复] 当数据区域即将改变时，旧的拟合曲线就失效了。
            # 在执行任何重绘操作之前，先清除共享数据模型。
            if self.shared_fit_data and self.shared_fit_data.has_fits():
                print("[Fix] Clearing shared fit data from _update_span")
                self.shared_fit_data.clear_fits()

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
            
            # 更新子图2和子图3 (此时它将读到已被清空的模型)
            self.update_highlighted_plots()
            
            # 使用限制频率的重绘
            self._throttled_draw()
            
        except Exception as e:
            print(f"Error in _update_span: {e}")
            import traceback
            traceback.print_exc()
    
    def update_highlighted_plots(self):
        """更新高亮区域和直方图 - 修复更新问题"""
        # 简化防护逻辑
        if self.data is None:
            return

            # 【新增】提前定义变量，避免作用域问题
        highlighted_data = None
        
        # 确保 _ax3_fit_lines 已初始化
        if not hasattr(self, '_ax3_fit_lines'):
            self._ax3_fit_lines = []  
        try:
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
        
            # 减小刻度大小以节省空间（原代码“刷度”应为“刻度”，此处修正笔误）
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
            self.ax2.plot(highlighted_time, highlighted_data, linewidth=0.7)
            
            # 绘制直方图
            counts, bins, _ = self.ax3.hist(
                highlighted_data, 
                bins=self.bins, 
                orientation='horizontal',
                alpha=0.7
            )
            
            # 检查对数刻度的有效性并在必要时禁用
            if self.log_y and not np.all(counts > 0):
                print("Warning: Disabling Y log scale due to zero counts in histogram")
                self.log_y = False
            
            # 设置对数轴 - 只对直方图生效，并验证数据有效性
            if self.log_x:
                self.ax3.set_xscale('log')
            else:
                self.ax3.set_xscale('linear')
                
            if self.log_y and np.all(counts > 0):
                self.ax3.set_yscale('log')
            else:
                self.ax3.set_yscale('linear')
            
            # 安全地设置轴范围
            if len(highlighted_time) > 0:
                self.ax2.set_xlim(highlighted_time[0], highlighted_time[-1])
            
            # 安全计算高亮区域数据的实际范围
            if len(highlighted_data) > 0:
                h_y_min, h_y_max = self._calculate_safe_ylim(highlighted_data)
                self.ax2.set_ylim(h_y_min, h_y_max)
                # 为subplot3设置y轴范围，但要考虑拟合曲线的范围
                if hasattr(self, '_ax3_fit_lines') and self._ax3_fit_lines:
                    # 如果有拟合线条，扩展范围以确保可见
                    self.ax3.set_ylim(h_y_min, h_y_max)
                else:
                    self.ax3.set_ylim(h_y_min, h_y_max)
                    
                # 绘制KDE曲线
                if self.show_kde and len(highlighted_data) > 1:
                    self.plot_kde(highlighted_data)
                
                # 刷新cursor显示
                self.refresh_cursors_after_plot_update()

        # 【修复1】最外层try的except必须紧跟try块，中间不插入其他代码
        except Exception as e:
            print(f"Error in main plotting logic of update_highlighted_plots: {e}")
            import traceback
            traceback.print_exc()

        # 【修复2】拟合逻辑放在最外层try-except之后，且判断highlighted_data是否有效
        # 【关键修复】无论是否有共享拟合数据，都先清除ax3中的旧拟合线条
        if hasattr(self, '_ax3_fit_lines') and self._ax3_fit_lines:
            for line in self._ax3_fit_lines[:]:
                try:
                    if line and line in self.ax3.lines:
                        line.remove()
                except:
                    pass  # 忽略已经被删除的线条
            self._ax3_fit_lines.clear()
        else:
            # 确保列表存在
            self._ax3_fit_lines = []
        
        if (highlighted_data is not None and  # 确保变量已定义且有效
            hasattr(self, 'ax3') and 
            self.shared_fit_data is not None and 
            self.shared_fit_data.has_fits()):
            try:
                # 获取拟合数据
                fits, regions = self.shared_fit_data.get_fits()
                
                # 在ax3中绘制拟合曲线
                for fit_data in fits:
                    if not fit_data or 'popt' not in fit_data:
                        continue
                        
                    popt = fit_data['popt']
                    x_range = fit_data['x_range']
                    color = fit_data['color']
                    
                    # 【修复】改进范围检查 - 只要有重叠就显示，不要求完全包含
                    data_min, data_max = highlighted_data.min(), highlighted_data.max()
                    data_range = data_max - data_min
                    tolerance = max(0.1 * data_range, 0.001)  # 10%容差，最小0.001
                    
                    # 检查是否有重叠（而不是要求完全包含）
                    has_overlap = (x_range[1] > data_min - tolerance and x_range[0] < data_max + tolerance)
                    
                    print(f"Fit range check: data=[{data_min:.4f}, {data_max:.4f}], fit=[{x_range[0]:.4f}, {x_range[1]:.4f}], overlap={has_overlap}")
                    
                    if has_overlap:
                        # 高斯函数（建议放在函数外部定义，避免每次循环重新创建）
                        def gaussian(x, amp, mu, sigma):
                            return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
                        
                        # 创建拟合曲线数据
                        x_fit = np.linspace(x_range[0], x_range[1], 150)
                        y_fit = gaussian(x_fit, *popt)
                        
                        # 绘制曲线（注意直方图是horizontal，所以x/y对应count/amplitude）
                        # 调细拟合曲线
                        line, = self.ax3.plot(y_fit, x_fit, '-', linewidth=1.0, color=color, zorder=15)
                        self._ax3_fit_lines.append(line)
                        
                        print(f"Applied fit {len(self._ax3_fit_lines)} to subplot3: color={color}, range={x_range}")
                    else:
                        print(f"Skipped fit due to no overlap: fit_range={x_range}, data_range=[{data_min:.4f}, {data_max:.4f}]")
                        
                # 确保轴范围能显示所有拟合曲线
                if self._ax3_fit_lines:
                    # 获取当前轴范围
                    current_ylim = self.ax3.get_ylim()
                    # 如果有拟合线条，确保范围包含所有拟合数据
                    all_fit_ranges = [fit_data['x_range'] for fit_data in fits if fit_data and 'x_range' in fit_data]
                    if all_fit_ranges:
                        fit_min = min(r[0] for r in all_fit_ranges)
                        fit_max = max(r[1] for r in all_fit_ranges)
                        # 扩展轴范围以包含所有拟合区间
                        new_ymin = min(current_ylim[0], fit_min)
                        new_ymax = max(current_ylim[1], fit_max)
                        if new_ymin != current_ylim[0] or new_ymax != current_ylim[1]:
                            self.ax3.set_ylim(new_ymin, new_ymax)
                            print(f"Extended ax3 y-axis range to [{new_ymin:.4f}, {new_ymax:.4f}] to show all fits")
                        
                print(f"Applied {len(fits)} fits to subplot3 in main view, displayed {len(self._ax3_fit_lines) if hasattr(self, '_ax3_fit_lines') else 0} lines")
                
            except Exception as e:
                print(f"Error applying fits to subplot3 in main view: {e}")
                import traceback
                traceback.print_exc()
    
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
            
            # 检查数据是否适合对数刻度
            if self.log_y and enabled:
                can_use_log = self._check_log_scale_validity()
                if not can_use_log:
                    print("Warning: Cannot apply log scale - data contains zero or negative values")
                    self.log_y = False
                    return
            
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
        """更新高亮区域大小"""
        if self.data is None or len(self.data) == 0:
            return
        
        # [核心修复] 当数据区域即将改变时，旧的拟合曲线就失效了。
        # 在执行任何重绘操作之前，先清除共享数据模型。
        if self.shared_fit_data and self.shared_fit_data.has_fits():
            print("[Fix] Clearing shared fit data from update_highlight_size")
            self.shared_fit_data.clear_fits()

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
        
        # 更新子图2和子图3 (此时它将读到已被清空的模型)
        self.update_highlighted_plots()
        
        # 使用限制频率的重绘
        self._throttled_draw()
    
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
            
        # 当前高亮的拟合索引（初始化为-1，表示没有高亮）
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
        
        # 绘制直方图 - 调低透明度使背景更浅，并设置较低的zorder以使其位于数据后面
        self.histogram = self.ax.hist(
            data, 
            bins=bins, 
            alpha=0.5,
            color='skyblue',
            edgecolor='black',
            zorder=5  # 设置较低的层级
        )
        
        # 获取直方图计数并检查对数刻度的有效性
        hist_counts = self.histogram[0]
        if log_y and not np.all(hist_counts > 0):
            print("Warning: Disabling Y log scale due to zero counts in histogram")
            log_y = False
            self.histogram_log_y = False
        
        # 设置对数轴（如果启用并且数据有效）
        if log_x:
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')
            
        if log_y and np.all(hist_counts > 0):
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        
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
        
    def set_shared_fit_data(self, shared_fit_data):
        """设置共享的拟合数据引用"""
        self.shared_fit_data = shared_fit_data
        print(f"Set shared fit data: {shared_fit_data}")
    
    def save_current_fits(self):
        """保存当前的拟合结果到共享数据"""
        try:
            # 【修复Bug1关键修复】不管是否有拟合结果，都要更新共享数据状态
            # 计算数据哈希值
            data_hash = self._calculate_data_hash()
            data_range = (self.histogram_data.min(), self.histogram_data.max()) if hasattr(self, 'histogram_data') and self.histogram_data is not None else None
            
            # 获取当前的拟合结果（可能为空）
            current_fits = self.gaussian_fits if hasattr(self, 'gaussian_fits') else []
            current_regions = [(r[0], r[1]) for r in self.fit_regions if len(r) >= 2] if hasattr(self, 'fit_regions') else []
            
            # 保存到本地管理器
            self.fit_data_manager.save_fits(current_fits, current_regions, data_range, data_hash)
            
            # 保存到共享数据（即使是空的也要保存，这样可以清空共享数据）
            if self.shared_fit_data is not None:
                self.shared_fit_data.save_fits(current_fits, current_regions, data_range, data_hash)
                print(f"Saved {len(current_fits)} fits to shared data (including empty state)")
                
        except Exception as e:
            print(f"Error saving fits: {e}")
            import traceback
            traceback.print_exc()
    
    def immediate_sync_to_main_view(self):
        """立即同步拟合结果到主视图的subplot3"""
        try:
            if (hasattr(self, 'parent_dialog') and self.parent_dialog and 
                hasattr(self.parent_dialog, 'plot_canvas')):
                # 获取主视图画布
                main_canvas = self.parent_dialog.plot_canvas
                
                # 确保主视图的_ax3_fit_lines列表存在
                if not hasattr(main_canvas, '_ax3_fit_lines'):
                    main_canvas._ax3_fit_lines = []
                
                # 触发主视图subplot3的更新
                if hasattr(main_canvas, 'update_highlighted_plots'):
                    print(f"Triggering sync to main view - current fits: {len(self.gaussian_fits)}")
                    main_canvas.update_highlighted_plots()
                    main_canvas._throttled_draw()
                    print(f"Immediate sync to main view subplot3 completed - lines: {len(main_canvas._ax3_fit_lines)}")
        except Exception as e:
            print(f"Error in immediate sync to main view: {e}")
            import traceback
            traceback.print_exc()
    
    def restore_fits_from_shared_data(self):
        """从共享数据恢复拟合结果"""
        if self.shared_fit_data is None or not self.shared_fit_data.has_fits():
            return False
            
        try:
            # 检查数据兼容性
            data_hash = self._calculate_data_hash()
            if not self.shared_fit_data.is_compatible_with_data(None, data_hash):
                print("Shared fit data is not compatible with current data")
                return False
            
            # 获取共享的拟合数据
            fits, regions = self.shared_fit_data.get_fits()
            
            # 应用到当前图表
            self.apply_fits_to_plot(fits, regions)
            
            print(f"Restored {len(fits)} fits from shared data")
            return True
            
        except Exception as e:
            print(f"Error restoring fits from shared data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def apply_fits_to_plot(self, fits, regions):
        """将拟合结果应用到当前图表"""
        try:
            # 清除现有的拟合
            self._clear_existing_fits()
            
            # 初始化拟合数据结构
            if not hasattr(self, 'gaussian_fits'):
                self.gaussian_fits = []
            if not hasattr(self, 'fit_regions'):
                self.fit_regions = []
                
            self.gaussian_fits.clear()
            self.fit_regions.clear()
            
            # 应用每个拟合
            for i, fit_data in enumerate(fits):
                if not fit_data or 'popt' not in fit_data:
                    continue
                    
                popt = fit_data['popt']
                x_range = fit_data['x_range']
                color = fit_data['color']
                
                # 绘制拟合曲线
                self._draw_fit_curve(popt, x_range, color, i + 1)
                
            # 更新拟合信息面板
            if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                self.parent_dialog.fit_info_panel.clear_all_fits()
                for i, fit_data in enumerate(fits):
                    if fit_data and 'popt' in fit_data:
                        amp, mu, sigma = fit_data['popt']
                        self.parent_dialog.fit_info_panel.add_fit(
                            i + 1, amp, mu, sigma, fit_data['x_range'], fit_data['color']
                        )
            
            # 更新拟合信息字符串
            if hasattr(self, 'update_fit_info_string'):
                self.update_fit_info_string()
                
        except Exception as e:
            print(f"Error applying fits to plot: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_fit_curve(self, popt, x_range, color, fit_num):
        """绘制单个拟合曲线"""
        try:
            if not hasattr(self, 'ax'):
                return
                
            # 高斯函数
            def gaussian(x, amp, mu, sigma):
                return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
            
            # 创建拟合曲线数据
            x_fit = np.linspace(x_range[0], x_range[1], 150)
            y_fit = gaussian(x_fit, *popt)
            
            # 绘制曲线 - 调细拟合曲线
            line, = self.ax.plot(x_fit, y_fit, '-', linewidth=1.0, color=color, zorder=15)
            
            # 创建文本标签
            amp, mu, sigma = popt
            text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
            text_obj = self.ax.text(mu, amp*1.05, text, ha='center', va='bottom', fontsize=9,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor=color, boxstyle='round'),
                color=color, zorder=20)
            
            # 检查标签可见性
            if hasattr(self, 'labels_visible'):
                text_obj.set_visible(self.labels_visible)
            
            # 添加到拟合列表
            fit_data = {
                'popt': popt,
                'x_range': x_range,
                'line': line,
                'text': text_obj,
                'color': color
            }
            self.gaussian_fits.append(fit_data)
            
            # 添加区域高亮（如果需要）
            if hasattr(self, 'fit_regions'):
                region = self.ax.axvspan(x_range[0], x_range[1], alpha=0.08, color='green', zorder=0)
                self.fit_regions.append((x_range[0], x_range[1], region))
                
        except Exception as e:
            print(f"Error drawing fit curve: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_existing_fits(self):
        """清除现有的拟合绘图对象"""
        try:
            if hasattr(self, 'gaussian_fits'):
                for fit in self.gaussian_fits:
                    if 'line' in fit and fit['line'] and hasattr(self, 'ax') and fit['line'] in self.ax.lines:
                        fit['line'].remove()
                    if 'text' in fit and fit['text']:
                        fit['text'].remove()
            
            if hasattr(self, 'fit_regions'):
                for region_data in self.fit_regions:
                    if len(region_data) >= 3 and region_data[2] and hasattr(self, 'ax') and region_data[2] in self.ax.patches:
                        region_data[2].remove()
                        
        except Exception as e:
            print(f"Error clearing existing fits: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_data_hash(self):
        """计算数据哈希值用于检测数据变化"""
        try:
            if hasattr(self, 'histogram_data') and self.histogram_data is not None:
                # 使用数据的简单统计信息作为哈希
                data = self.histogram_data
                stats_str = f"{len(data)}_{data.min():.6f}_{data.max():.6f}_{data.mean():.6f}_{data.std():.6f}"
                return hash(stats_str)
            return None
        except:
            return None
        
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
                
                # 计算指定高斯组件的颜色 - 与cursor颜色保持一致
                fit_colors = ['red', 'blue', 'purple', 'orange', 'green', 'magenta', 'cyan', 'brown', 'olive', 'teal']
                color_idx = len(self.gaussian_fits) % len(fit_colors)
                fit_color = fit_colors[color_idx]
                
                # 将拟合曲线绘到图上，使用颜色循环 - 调细拟合曲线
                y_fit = gaussian(x_fit, *popt)
                line, = self.ax.plot(x_fit, y_fit, '-', linewidth=1.0, color=fit_color, zorder=15)
                
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
                fit_data = {
                    'popt': popt,
                    'x_range': (x_min, x_max),
                    'line': line,
                    'text': text_obj,
                    'color': fit_color
                }
                self.gaussian_fits.append(fit_data)
                
                # 添加到拟合信息面板（如果存在）
                if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                    fit_num = len(self.gaussian_fits)  # 现在长度已经包含了新的拟合
                    print(f"Adding fit to panel: {fit_num}, {amp:.2f}, {mu:.4f}, {sigma:.4f}")
                    self.parent_dialog.fit_info_panel.add_fit(fit_num, amp, mu, sigma, (x_min, x_max), fit_color)
                
                # 收集拟合信息字符串
                # 全部拟合信息
                self.update_fit_info_string()
                
                # 重新绘制
                self.draw()
                
                # 【新增】保存拟合结果到共享数据并立即同步到主视图
                self.save_current_fits()
                # 立即触发主视图subplot3的更新
                self.immediate_sync_to_main_view()
                
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
            # 【修复Bug1】先保存清空状态到共享数据
            if self.shared_fit_data is not None:
                self.shared_fit_data.clear_fits()
            
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
            
            # 重置高亮索引
            self.highlighted_fit_index = -1
            
            # 清除拟合信息面板
            if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                self.parent_dialog.fit_info_panel.clear_all_fits()
            
            # 【修复Bug2】立即同步清空状态到主视图
            self.immediate_sync_to_main_view()
            
            # 重绘
            self.draw()
            
        except Exception as e:
            print(f"Error clearing fits: {e}")
            import traceback
            traceback.print_exc()
    
    def delete_specific_fit(self, fit_index):
        """删除特定的拟合"""
        try:
            if not hasattr(self, 'gaussian_fits') or len(self.gaussian_fits) == 0:
                return False
            
            # 查找对应的拟合项（使用显示索引从1开始）
            target_index = -1
            for i, fit in enumerate(self.gaussian_fits):
                if (i + 1) == fit_index:  # 显示索引从1开始
                    target_index = i
                    break
            
            if target_index == -1:
                print(f"Could not find fit with index {fit_index}")
                return False
            
            fit = self.gaussian_fits[target_index]
            
            # 从图中移除元素
            if 'line' in fit and fit['line'] in self.ax.lines:
                fit['line'].remove()
            if 'text' in fit:
                fit['text'].remove()
            
            # 移除相关的区域高亮
            if hasattr(self, 'fit_regions') and target_index < len(self.fit_regions):
                _, _, region = self.fit_regions[target_index]
                if region in self.ax.patches:
                    region.remove()
                self.fit_regions.pop(target_index)
            
            # 从列表中移除
            self.gaussian_fits.pop(target_index)
            
            # 重新编号剩余的拟合和更新显示
            self._renumber_fits()
            
            # 更新拟合信息字符串
            self.update_fit_info_string()
            
            # 重置高亮索引
            if self.highlighted_fit_index >= len(self.gaussian_fits):
                self.highlighted_fit_index = -1
            
            # 【修复Bug1关键修复】先检查是否所有拟合都被删除了
            if len(self.gaussian_fits) == 0:
                # 如果所有拟合都被删除，直接清空共享数据
                if self.shared_fit_data is not None:
                    self.shared_fit_data.clear_fits()
                    print("Cleared shared fit data after deleting last fit")
            else:
                # 如果还有其他拟合，保存当前状态
                self.save_current_fits()
            
            # 【修复Bug2】立即同步到主视图
            self.immediate_sync_to_main_view()
            
            # 重新绘制
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error deleting specific fit: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # =================== Cursor 功能相关方法 ===================
    
    def get_cursor_info(self):
        """获取所有cursor的信息"""
        cursor_info = []
        try:
            if hasattr(self, 'cursors') and self.cursors:
                for cursor in self.cursors:
                    info = {
                        'id': cursor.get('id', 0),
                        'y_position': cursor.get('y_position', 0),
                        'color': cursor.get('color', 'red'),
                        'selected': cursor.get('selected', False)
                    }
                    cursor_info.append(info)
        except Exception as e:
            print(f"Error getting cursor info: {e}")
        return cursor_info
    
    def add_cursor(self, y_position=None, color=None):
        """添加一个cursor在Fig2和Fig3中"""
        try:
            # 如果没有指定y位置，默认使用中间位置
            if y_position is None:
                if hasattr(self, 'ax2') and len(self.ax2.get_ylim()) == 2:
                    y_min, y_max = self.ax2.get_ylim()
                    y_position = (y_min + y_max) / 2
                else:
                    y_position = 0  # 默认位置
            
            # 选择颜色 - 与拟合曲线颜色保持一致
            if color is None:
                # 使用与拟合曲线一致的颜色循环
                fit_colors = ['red', 'blue', 'purple', 'orange', 'green', 'magenta', 'cyan', 'brown', 'olive', 'teal']
                color = fit_colors[len(self.cursors) % len(fit_colors)]
            
            # 创建唯一ID
            cursor_id = self.cursor_counter
            self.cursor_counter += 1
            
            # 在Fig2中创建横向线
            line_ax2 = None
            if hasattr(self, 'ax2'):
                line_ax2 = self.ax2.axhline(y=y_position, color=color, 
                                          linestyle='--', linewidth=0.8, 
                                          alpha=0.6, zorder=20)
            
            # 在Fig3中创建横向线
            line_ax3 = None
            if hasattr(self, 'ax3'):
                line_ax3 = self.ax3.axhline(y=y_position, color=color, 
                                          linestyle='--', linewidth=0.8, 
                                          alpha=0.6, zorder=20)
            
            # 创建cursor对象
            cursor = {
                'id': cursor_id,
                'y_position': y_position,
                'color': color,
                'line_ax2': line_ax2,
                'line_ax3': line_ax3,
                'selected': False
            }
            
            # 添加到列表
            self.cursors.append(cursor)
            
            # 重新绘制
            self.draw()
            
            return cursor_id
            
        except Exception as e:
            print(f"Error adding cursor: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def remove_cursor(self, cursor_id):
        """删除指定ID的cursor（修复版）"""
        try:
            # 找到对应的cursor
            cursor_to_remove = None
            cursor_index = -1
            
            for i, cursor in enumerate(self.cursors):
                if cursor['id'] == cursor_id:
                    cursor_to_remove = cursor
                    cursor_index = i
                    break
            
            if cursor_to_remove is None:
                print(f"Cursor with ID {cursor_id} not found")
                return False
            
            print(f"Removing cursor with ID {cursor_id} at index {cursor_index}")
            
            # 从图中移除线条
            if cursor_to_remove.get('line_ax2') and cursor_to_remove['line_ax2'] in self.ax2.lines:
                cursor_to_remove['line_ax2'].remove()
            if cursor_to_remove.get('line_ax3') and cursor_to_remove['line_ax3'] in self.ax3.lines:
                cursor_to_remove['line_ax3'].remove()
            # 如果在histogram模式下，也要移除相应的线
            if cursor_to_remove.get('histogram_line'):
                try:
                    cursor_to_remove['histogram_line'].remove()
                except:
                    pass
            
            # 清除选中状态（在移除之前）
            if self.selected_cursor == cursor_to_remove:
                self.selected_cursor = None
            
            # 从列表中移除
            self.cursors.pop(cursor_index)
            
            # 不在这里调用重新编号，让PopupCursorManager来处理
            # 这样可以确保正确的顺序和状态管理
            
            print(f"Successfully removed cursor. Remaining cursors: {[c['id'] for c in self.cursors]}")
            
            # 使用限制频率的重绘
            self._throttled_draw()
            
            return True
            
        except Exception as e:
            print(f"Error removing cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _renumber_cursors(self):
        """重新编号所有cursor从1开始 - 修复版"""
        try:
            # 不按位置排序，而是按当前ID排序以保持相对顺序
            if not self.cursors:
                self.cursor_counter = 0
                return
                
            # 按当前ID排序保持相对顺序
            sorted_cursors = sorted(self.cursors, key=lambda c: c.get('id', 0))
            
            # 重新分配连续的ID，从1开始
            for i, cursor in enumerate(sorted_cursors):
                old_id = cursor.get('id')
                new_id = i + 1
                cursor['id'] = new_id
                
                # 如果选中的cursor的ID变了，更新选中状态
                if self.selected_cursor and self.selected_cursor.get('id') == old_id:
                    self.selected_cursor['id'] = new_id
            
            # 更新cursor列表
            self.cursors = sorted_cursors
            
            # 设置下一个可用的cursor ID
            self.cursor_counter = len(self.cursors)
            
            print(f"Renumbered cursors to: {[c['id'] for c in self.cursors]}")
            
        except Exception as e:
            print(f"Error renumbering cursors: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        try:
            # 移除所有线条
            for cursor in self.cursors:
                if cursor['line_ax2'] and cursor['line_ax2'] in self.ax2.lines:
                    cursor['line_ax2'].remove()
                if cursor['line_ax3'] and cursor['line_ax3'] in self.ax3.lines:
                    cursor['line_ax3'].remove()
            
            # 清空列表
            self.cursors.clear()
            self.selected_cursor = None
            
            # 重新绘制
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error clearing cursors: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_cursor_info(self):
        """获取所有cursor的信息"""
        cursor_info = []
        for cursor in self.cursors:
            # 确保selected状态正确反映
            is_selected = cursor.get('selected', False)
            # 双重检查：如果这是当前选中的cursor，确保selected为True
            if self.selected_cursor and cursor['id'] == self.selected_cursor.get('id'):
                is_selected = True
                cursor['selected'] = True  # 更新cursor对象中的状态
            
            info = {
                'id': cursor['id'],
                'y_position': cursor['y_position'],
                'color': cursor['color'],
                'selected': is_selected
            }
            cursor_info.append(info)
        return cursor_info
    
    def update_cursor_position(self, cursor_id, new_y):
        """更新cursor的位置并同步Fig2和Fig3"""
        try:
            # 找到对应的cursor
            cursor = None
            for c in self.cursors:
                if c['id'] == cursor_id:
                    cursor = c
                    break
            
            if cursor is None:
                return False
            
            # 更新y位置
            cursor['y_position'] = new_y
            
            # 更新Fig2中的线
            if cursor['line_ax2']:
                cursor['line_ax2'].set_ydata([new_y, new_y])
            
            # 更新Fig3中的线
            if cursor['line_ax3']:
                cursor['line_ax3'].set_ydata([new_y, new_y])
            
            return True
            
        except Exception as e:
            print(f"Error updating cursor position: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_cursor(self, cursor_id):
        """选中指定的cursor（视觉反馈）并发送信号 - 添加递归防护"""
        # 【修复点6】递归防护
        if self._updating_cursors:
            return True
            
        try:
            self._updating_cursors = True
            
            # 如果选中的是同一个cursor，不需要重复处理
            if self.selected_cursor and self.selected_cursor.get('id') == cursor_id:
                return True
            
            # 清除所有cursor的选中状态
            for cursor in self.cursors:
                cursor['selected'] = False
                # 恢复正常的线条样式
                if cursor.get('line_ax2'):
                    cursor['line_ax2'].set_linewidth(0.8)
                    cursor['line_ax2'].set_alpha(0.6)
                if cursor.get('line_ax3'):
                    cursor['line_ax3'].set_linewidth(0.8)
                    cursor['line_ax3'].set_alpha(0.6)
                # 如果在histogram模式下也要更新
                if cursor.get('histogram_line'):
                    cursor['histogram_line'].set_linewidth(0.8)
                    cursor['histogram_line'].set_alpha(0.6)
            
            # 设置新的选中cursor
            cursor_found = False
            if cursor_id is not None:
                for cursor in self.cursors:
                    if cursor['id'] == cursor_id:
                        cursor['selected'] = True
                        self.selected_cursor = cursor
                        cursor_found = True
                        
                        # 高亮线条样式
                        if cursor.get('line_ax2'):
                            cursor['line_ax2'].set_linewidth(1.5)
                            cursor['line_ax2'].set_alpha(0.9)
                        if cursor.get('line_ax3'):
                            cursor['line_ax3'].set_linewidth(1.5)
                            cursor['line_ax3'].set_alpha(0.9)
                        # 如果在histogram模式下也要更新
                        if cursor.get('histogram_line'):
                            cursor['histogram_line'].set_linewidth(1.5)
                            cursor['histogram_line'].set_alpha(0.9)
                        
                        # 发送cursor选中信号
                        self.cursor_selected.emit(cursor_id)
                        break
                        
                if not cursor_found:
                    print(f"Warning: Cursor {cursor_id} not found for selection")
                    self.selected_cursor = None
                    return False
            else:
                self.selected_cursor = None
                # 发送取消选中信号
                self.cursor_deselected.emit()
            
            # 重新绘制
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error selecting cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._updating_cursors = False
    
    def on_cursor_mouse_press(self, event):
        """鼠标按下事件处理"""
        try:
            # 只在Fig2和Fig3中处理cursor操作，或者在histogram模式下的主axis
            valid_axes = []
            if hasattr(self, 'ax2'):
                valid_axes.append(self.ax2)
            if hasattr(self, 'ax3'):
                valid_axes.append(self.ax3)
            if hasattr(self, 'ax') and getattr(self, 'is_histogram_mode', False):
                valid_axes.append(self.ax)
                
            if not (event.inaxes in valid_axes):
                return
            
            # 处理左键和右键点击
            if event.button == 1:  # 左键
                # 检查是否点击在cursor附近
                clicked_cursor = self._find_cursor_near_point(event.xdata, event.ydata, event.inaxes)
                
                if clicked_cursor:
                    # 选中并开始拖拽
                    self.select_cursor(clicked_cursor['id'])
                    self.dragging = True
                    self.drag_start_y = event.ydata
                    # 阻止事件继续传播给其他处理器
                    return True  # 返回true表示事件已处理
                else:
                    # 点击在空白区域，取消cursor选择
                    self.select_cursor(None)
                    
            elif event.button == 3:  # 右键
                # 右键点击添加新cursor
                self.add_cursor(y_position=event.ydata)
                return True  # 返回true表示事件已处理
        
        except Exception as e:
            print(f"Error in cursor mouse press: {e}")
            import traceback
            traceback.print_exc()
    
    def on_cursor_mouse_move(self, event):
        """鼠标移动事件处理"""
        try:
            # 只在拖拽状态下处理
            if not self.dragging or not self.selected_cursor:
                return
            
            # 只在Fig2和Fig3中处理
            if not (event.inaxes == self.ax2 or event.inaxes == self.ax3):
                return
            
            if event.ydata is not None:
                # 更新cursor位置
                self.update_cursor_position(self.selected_cursor['id'], event.ydata)
                # 使用限制频率的重绘以显示拖拽效果
                self._throttled_draw()
                # 阻止事件传播
                event.canvas.stop_event_loop = True
        
        except Exception as e:
            print(f"Error in cursor mouse move: {e}")
            import traceback
            traceback.print_exc()
    
    def on_cursor_mouse_release(self, event):
        """鼠标释放事件处理"""
        try:
            # 结束拖拽
            self.dragging = False
            self.drag_start_y = None
        
        except Exception as e:
            print(f"Error in cursor mouse release: {e}")
            import traceback
            traceback.print_exc()
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        try:
            # 只有在选中了cursor的情况下才处理键盘事件
            if self.selected_cursor is None:
                super().keyPressEvent(event)
                return
                
            # 处理删除键（MacBook同时支持Delete和Backspace）
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                cursor_id = self.selected_cursor['id']
                self.remove_cursor(cursor_id)
                event.accept()  # 标记事件已处理
                
            # 处理上下方向键微调位置
            elif event.key() == Qt.Key.Key_Up:
                cursor_id = self.selected_cursor['id']
                self._adjust_cursor_position_optimized(cursor_id, 0.01)  # 增大步长
                event.accept()
                
            elif event.key() == Qt.Key.Key_Down:
                cursor_id = self.selected_cursor['id']
                self._adjust_cursor_position_optimized(cursor_id, -0.01)  # 增大步长
                event.accept()
                
            else:
                super().keyPressEvent(event)
                
        except Exception as e:
            print(f"Error in keyPressEvent: {e}")
            import traceback
            traceback.print_exc()
            super().keyPressEvent(event)
    
    def _adjust_cursor_position_optimized(self, cursor_id, delta):
        """优化的cursor位置微调"""
        try:
            # 获取当前cursor信息
            cursor_info = self.get_cursor_info()
            current_position = None
            
            for info in cursor_info:
                if info['id'] == cursor_id:
                    current_position = info['y_position']
                    break
                    
            if current_position is not None:
                new_position = current_position + delta
                
                # 直接更新cursor位置，不立即重绘
                for cursor in self.cursors:
                    if cursor['id'] == cursor_id:
                        cursor['y_position'] = new_position
                        
                        # 更新Fig2中的线
                        if cursor['line_ax2']:
                            cursor['line_ax2'].set_ydata([new_position, new_position])
                        
                        # 更新Fig3中的线
                        if cursor['line_ax3']:
                            cursor['line_ax3'].set_ydata([new_position, new_position])
                        
                        break
                
                # 使用blit快速重绘
                self.draw_idle()
                    
        except Exception as e:
            print(f"Error adjusting cursor position: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_cursor_near_point(self, x, y, axes):
        """在指定的坐标附近查找cursor - 支持不同的axes类型"""
        try:
            if x is None or y is None:
                return None
            
            # 计算容差范围（基于轴范围的一小部分）
            if hasattr(axes, 'get_ylim'):
                y_min, y_max = axes.get_ylim()
                tolerance = (y_max - y_min) * 0.02  # 2%的容差
            else:
                tolerance = 0.1  # 默认容差
            
            # 查找最近的cursor
            closest_cursor = None
            min_distance = float('inf')
            
            for cursor in self.cursors:
                # 在histogram模式下，cursor是垂直线，需要比较x坐标
                if getattr(self, 'is_histogram_mode', False) and axes == getattr(self, 'ax', None):
                    distance = abs(cursor['y_position'] - x)  # 在histogram模式下，cursor的y_position对应x坐标
                else:
                    distance = abs(cursor['y_position'] - y)  # 正常模式下比较y坐标
                    
                if distance < tolerance and distance < min_distance:
                    min_distance = distance
                    closest_cursor = cursor
            
            return closest_cursor
            
        except Exception as e:
            print(f"Error finding cursor near point: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def refresh_cursors_after_plot_update(self):
        """在更新绘图后刷新cursor显示 - 添加递归防护"""
        # 【修复点5】递归防护
        if self._updating_cursors:
            return
            
        try:
            self._updating_cursors = True
            
            if not self.cursors:
                return
            
            # 重新绘制所有cursor
            for cursor in self.cursors:
                y_pos = cursor['y_position']
                color = cursor['color']
                
                # 重新在Fig2中创建线
                if hasattr(self, 'ax2'):
                    cursor['line_ax2'] = self.ax2.axhline(y=y_pos, color=color, 
                                                         linestyle='--', linewidth=0.8, 
                                                         alpha=0.6, zorder=20)
                
                # 重新在Fig3中创建线
                if hasattr(self, 'ax3'):
                    cursor['line_ax3'] = self.ax3.axhline(y=y_pos, color=color, 
                                                         linestyle='--', linewidth=0.8, 
                                                         alpha=0.6, zorder=20)
                
                # 如果是选中的cursor，恢复选中样式
                if cursor.get('selected', False):
                    if cursor['line_ax2']:
                        cursor['line_ax2'].set_linewidth(1.5)
                        cursor['line_ax2'].set_alpha(0.9)
                    if cursor['line_ax3']:
                        cursor['line_ax3'].set_linewidth(1.5)
                        cursor['line_ax3'].set_alpha(0.9)
                
        except Exception as e:
            print(f"Error refreshing cursors after plot update: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._updating_cursors = False
    
    def sync_cursor_data_real_time(self):
        """实时同步cursor数据 - 用于实时更新"""
        try:
            # 返回最新的cursor信息，但不重绘全部界面
            cursor_info = []
            for cursor in self.cursors:
                info = {
                    'id': cursor['id'],
                    'y_position': cursor['y_position'],
                    'color': cursor['color'],
                    'selected': cursor.get('selected', False)
                }
                cursor_info.append(info)
            return cursor_info
            
        except Exception as e:
            print(f"Error syncing cursor data: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_cursors_after_plot_update(self):
        """在绘图更新后刷新cursor显示"""
        try:
            if not hasattr(self, 'cursors') or not self.cursors:
                return
            
            # 在主视图模式下，cursor显示为水平线（在Fig2和Fig3中）
            for cursor in self.cursors:
                y_pos = cursor['y_position']
                color = cursor['color']
                
                # 在Fig2中创建横向线
                if hasattr(self, 'ax2'):
                    # 移除之前的线（如果存在）
                    if 'line_ax2' in cursor and cursor['line_ax2']:
                        try:
                            cursor['line_ax2'].remove()
                        except:
                            pass
                    
                    # 创建新的横向线
                    cursor['line_ax2'] = self.ax2.axhline(
                        y=y_pos, color=color, 
                        linestyle='--', linewidth=0.8, 
                        alpha=0.6, zorder=20
                    )
                
                # 在Fig3中创建横向线
                if hasattr(self, 'ax3'):
                    # 移除之前的线（如果存在）
                    if 'line_ax3' in cursor and cursor['line_ax3']:
                        try:
                            cursor['line_ax3'].remove()
                        except:
                            pass
                    
                    # 创建新的横向线
                    cursor['line_ax3'] = self.ax3.axhline(
                        y=y_pos, color=color, 
                        linestyle='--', linewidth=0.8, 
                        alpha=0.6, zorder=20
                    )
                
                # 如果是选中的cursor，加粗显示
                if cursor.get('selected', False):
                    if 'line_ax2' in cursor and cursor['line_ax2']:
                        cursor['line_ax2'].set_linewidth(1.5)
                        cursor['line_ax2'].set_alpha(0.9)
                    if 'line_ax3' in cursor and cursor['line_ax3']:
                        cursor['line_ax3'].set_linewidth(1.5)
                        cursor['line_ax3'].set_alpha(0.9)
                        
        except Exception as e:
            print(f"Error refreshing cursors after plot update: {e}")
            import traceback
            traceback.print_exc()
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新指定cursor的位置"""
        try:
            if not hasattr(self, 'cursors') or not self.cursors:
                return False
                
            # 找到对应的cursor
            cursor_to_update = None
            for cursor in self.cursors:
                if cursor['id'] == cursor_id:
                    cursor_to_update = cursor
                    break
            
            if cursor_to_update is None:
                print(f"Cursor with ID {cursor_id} not found")
                return False
            
            # 更新位置
            cursor_to_update['y_position'] = new_position
            
            # 更新显示
            if 'line_ax2' in cursor_to_update and cursor_to_update['line_ax2']:
                try:
                    cursor_to_update['line_ax2'].remove()
                except:
                    pass
                    
                if hasattr(self, 'ax2'):
                    cursor_to_update['line_ax2'] = self.ax2.axhline(
                        y=new_position, color=cursor_to_update['color'], 
                        linestyle='--', linewidth=0.8, 
                        alpha=0.6, zorder=20
                    )
            
            if 'line_ax3' in cursor_to_update and cursor_to_update['line_ax3']:
                try:
                    cursor_to_update['line_ax3'].remove()
                except:
                    pass
                    
                if hasattr(self, 'ax3'):
                    cursor_to_update['line_ax3'] = self.ax3.axhline(
                        y=new_position, color=cursor_to_update['color'], 
                        linestyle='--', linewidth=0.8, 
                        alpha=0.6, zorder=20
                    )
            
            # 如果在histogram模式下，也要更新
            if hasattr(self, 'is_histogram_mode') and self.is_histogram_mode:
                if 'histogram_line' in cursor_to_update and cursor_to_update['histogram_line']:
                    try:
                        cursor_to_update['histogram_line'].remove()
                    except:
                        pass
                        
                    if hasattr(self, 'ax'):
                        cursor_to_update['histogram_line'] = self.ax.axvline(
                            x=new_position, color=cursor_to_update['color'], 
                            linestyle='--', linewidth=0.8, 
                            alpha=0.6, zorder=20
                        )
            
            return True
            
        except Exception as e:
            print(f"Error updating cursor position: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_cursor(self, cursor_id):
        """选中指定的cursor"""
        try:
            if not hasattr(self, 'cursors'):
                return False
                
            # 清除所有cursor的选中状态
            for cursor in self.cursors:
                cursor['selected'] = False
                # 恢复正常显示
                if 'line_ax2' in cursor and cursor['line_ax2']:
                    cursor['line_ax2'].set_linewidth(0.8)
                    cursor['line_ax2'].set_alpha(0.6)
                if 'line_ax3' in cursor and cursor['line_ax3']:
                    cursor['line_ax3'].set_linewidth(0.8)
                    cursor['line_ax3'].set_alpha(0.6)
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    cursor['histogram_line'].set_linewidth(0.8)
                    cursor['histogram_line'].set_alpha(0.6)
            
            self.selected_cursor = None
            
            if cursor_id is not None:
                # 找到并选中指定的cursor
                for cursor in self.cursors:
                    if cursor['id'] == cursor_id:
                        cursor['selected'] = True
                        self.selected_cursor = cursor
                        
                        # 加粗显示选中的cursor
                        if 'line_ax2' in cursor and cursor['line_ax2']:
                            cursor['line_ax2'].set_linewidth(1.5)
                            cursor['line_ax2'].set_alpha(0.9)
                        if 'line_ax3' in cursor and cursor['line_ax3']:
                            cursor['line_ax3'].set_linewidth(1.5)
                            cursor['line_ax3'].set_alpha(0.9)
                        if 'histogram_line' in cursor and cursor['histogram_line']:
                            cursor['histogram_line'].set_linewidth(1.5)
                            cursor['histogram_line'].set_alpha(0.9)
                        
                        # 发送选中信号
                        if hasattr(self, 'cursor_selected'):
                            self.cursor_selected.emit(cursor_id)
                        
                        break
            
            return True
            
        except Exception as e:
            print(f"Error selecting cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        try:
            if not hasattr(self, 'cursors'):
                return True
                
            # 移除所有cursor的显示元素
            for cursor in self.cursors:
                if 'line_ax2' in cursor and cursor['line_ax2']:
                    try:
                        cursor['line_ax2'].remove()
                    except:
                        pass
                if 'line_ax3' in cursor and cursor['line_ax3']:
                    try:
                        cursor['line_ax3'].remove()
                    except:
                        pass
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    try:
                        cursor['histogram_line'].remove()
                    except:
                        pass
            
            # 清空列表
            self.cursors.clear()
            self.selected_cursor = None
            self.cursor_counter = 0
            
            # 重新绘制
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error clearing all cursors: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _renumber_fits(self):
        """重新编号拟合项目并更新显示"""
        try:
            # 先清除拟合信息面板
            if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                self.parent_dialog.fit_info_panel.clear_all_fits()
            
            # 重新添加所有拟合项
            for i, fit in enumerate(self.gaussian_fits):
                amp, mu, sigma = fit['popt']
                x_range = fit['x_range']
                color = fit['color']
                
                # 更新文本标签
                new_fit_num = i + 1
                if 'text' in fit:
                    fit['text'].set_text(f"G{new_fit_num}: μ={mu:.3f}, σ={sigma:.3f}")
                
                # 重新添加到拟合信息面板
                if hasattr(self, 'parent_dialog') and self.parent_dialog and hasattr(self.parent_dialog, 'fit_info_panel'):
                    self.parent_dialog.fit_info_panel.add_fit(new_fit_num, amp, mu, sigma, x_range, color)
        
        except Exception as e:
            print(f"Error in _renumber_fits: {e}")
            import traceback
            traceback.print_exc()
    
    def delete_multiple_fits(self, fit_indices):
        """批量删除多个拟合"""
        try:
            if not hasattr(self, 'gaussian_fits') or len(self.gaussian_fits) == 0:
                return 0
            
            deleted_count = 0
            # 从大到小排序的实际索引（数组索引）
            actual_indices = []
            for fit_index in fit_indices:
                for i, fit in enumerate(self.gaussian_fits):
                    if (i + 1) == fit_index:  # 显示索引转换为数组索引
                        actual_indices.append(i)
                        break
            
            # 按实际索引从大到小排序，避免删除时索引变化
            for actual_index in sorted(set(actual_indices), reverse=True):
                if actual_index < len(self.gaussian_fits):
                    fit = self.gaussian_fits[actual_index]
                    
                    # 从图中移除元素
                    if 'line' in fit and fit['line'] in self.ax.lines:
                        fit['line'].remove()
                    if 'text' in fit:
                        fit['text'].remove()
                    
                    # 移除相关的区域高亮
                    if hasattr(self, 'fit_regions') and actual_index < len(self.fit_regions):
                        _, _, region = self.fit_regions[actual_index]
                        if region in self.ax.patches:
                            region.remove()
                        self.fit_regions.pop(actual_index)
                    
                    # 从列表中移除
                    self.gaussian_fits.pop(actual_index)
                    deleted_count += 1
            
            if deleted_count > 0:
                # 重新编号剩余的拟合
                self._renumber_fits()
                
                # 更新拟合信息字符串
                self.update_fit_info_string()
                
                # 重置高亮索引
                if self.highlighted_fit_index >= len(self.gaussian_fits):
                    self.highlighted_fit_index = -1
                
                # 【修复Bug1关键修复】先检查是否所有拟合都被删除了
                if len(self.gaussian_fits) == 0:
                    # 如果所有拟合都被删除，直接清空共享数据
                    if self.shared_fit_data is not None:
                        self.shared_fit_data.clear_fits()
                        print("Cleared shared fit data after deleting all fits")
                else:
                    # 如果还有其他拟合，保存当前状态
                    self.save_current_fits()
                
                # 【修复Bug2】同步到主视图
                self.immediate_sync_to_main_view()
                
                # 重新绘制
                self.draw()
            
            return deleted_count
            
        except Exception as e:
            print(f"Error in delete_multiple_fits: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def update_specific_fit(self, fit_index, new_params):
        """更新特定拟合的参数"""
        try:
            if not hasattr(self, 'gaussian_fits'):
                return False
                
            # 查找对应索引的拟合
            for i, fit in enumerate(self.gaussian_fits):
                if (i + 1) == fit_index:  # 使用显示索引（从1开始）进行匹配
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
                    line, = self.ax.plot(x_fit, y_fit, '-', linewidth=1.5, color=color, zorder=15)
                    
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
                    
                    # 【修复Bug1&2】保存更新后的拟合结果到共享数据并同步到主视图
                    self.save_current_fits()
                    self.immediate_sync_to_main_view()
                    
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
            if not hasattr(self, 'gaussian_fits') or len(self.gaussian_fits) == 0:
                return False
            
            # 先恢复所有线条的正常粗细
            for fit in self.gaussian_fits:
                if 'line' in fit:
                    fit['line'].set_linewidth(1.5)
            
            # 处理取消所有选中的情况（fit_index为-1或无效值）
            if fit_index == -1:
                # 取消所有高亮，所有曲线保持相同粗细
                self.highlighted_fit_index = -1
                self.draw()
                return True
            
            # 查找对应索引的拟合
            actual_index = -1
            for i, fit in enumerate(self.gaussian_fits):
                if (i + 1) == fit_index:  # 使用显示索引（从1开始）进行匹配
                    # 高亮显示该拟合
                    if 'line' in fit:
                        fit['line'].set_linewidth(3.0)  # 增加线宽高亮显示
                    
                    # 记录当前高亮的索引
                    self.highlighted_fit_index = i
                    actual_index = i
                    break
            
            # 重新绘制
            if actual_index >= 0:
                self.draw()
                return True
            else:
                # 如果没有找到对应的拟合索引，取消所有高亮
                self.highlighted_fit_index = -1
                self.draw()
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
        
        # [核心修复] 当数据区域即将改变时，旧的拟合曲线就失效了。
        # 在执行任何重绘操作之前，先清除共享数据模型。
        if self.shared_fit_data and self.shared_fit_data.has_fits():
            print("[Fix] Clearing shared fit data from move_highlight")
            self.shared_fit_data.clear_fits()

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
        
        # 更新子图2和子图3 (此时它将读到已被清空的模型)
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
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        try:
            if not hasattr(self, 'cursors'):
                return True
            
            # 清除所有cursor的绘图元素
            for cursor in self.cursors[:]:
                # 清除ax2中的线
                if 'line_ax2' in cursor and cursor['line_ax2']:
                    try:
                        cursor['line_ax2'].remove()
                    except:
                        pass
                
                # 清除ax3中的线
                if 'line_ax3' in cursor and cursor['line_ax3']:
                    try:
                        cursor['line_ax3'].remove()
                    except:
                        pass
                
                # 清除直方图模式中的线
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    try:
                        cursor['histogram_line'].remove()
                    except:
                        pass
            
            # 清空列表
            self.cursors.clear()
            
            # 重置相关状态
            self.selected_cursor = None
            self.cursor_counter = 0
            
            # 重绘
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error clearing all cursors: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_cursor(self, cursor_id):
        """选中cursor"""
        try:
            if not hasattr(self, 'cursors'):
                return False
                
            # 先取消所有cursor的选中状态
            for cursor in self.cursors:
                cursor['selected'] = False
                # 恢复正常线宽
                for line_key in ['line_ax2', 'line_ax3', 'histogram_line']:
                    if line_key in cursor and cursor[line_key]:
                        cursor[line_key].set_linewidth(0.8)
                        cursor[line_key].set_alpha(0.6)
            
            # 设置选中的cursor
            if cursor_id is not None:
                for cursor in self.cursors:
                    if cursor['id'] == cursor_id:
                        cursor['selected'] = True
                        self.selected_cursor = cursor
                        # 高亮选中的cursor
                        for line_key in ['line_ax2', 'line_ax3', 'histogram_line']:
                            if line_key in cursor and cursor[line_key]:
                                cursor[line_key].set_linewidth(1.5)
                                cursor[line_key].set_alpha(0.9)
                        break
            else:
                self.selected_cursor = None
            
            # 重绘
            self.draw()
            
            return True
            
        except Exception as e:
            print(f"Error selecting cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新cursor位置"""
        try:
            if not hasattr(self, 'cursors'):
                return False
                
            for cursor in self.cursors:
                if cursor['id'] == cursor_id:
                    cursor['y_position'] = new_position
                    
                    # 更新ax2中的线
                    if 'line_ax2' in cursor and cursor['line_ax2']:
                        cursor['line_ax2'].set_ydata([new_position, new_position])
                    
                    # 更新ax3中的线
                    if 'line_ax3' in cursor and cursor['line_ax3']:
                        cursor['line_ax3'].set_ydata([new_position, new_position])
                    
                    # 更新直方图模式中的线
                    if 'histogram_line' in cursor and cursor['histogram_line']:
                        # 在直方图模式中，cursor是垂直线
                        cursor['histogram_line'].set_xdata([new_position, new_position])
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error updating cursor position: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_cursor_info(self):
        """获取所有cursor的信息"""
        try:
            if not hasattr(self, 'cursors'):
                return []
                
            cursor_info = []
            for cursor in self.cursors:
                info = {
                    'id': cursor['id'],
                    'y_position': cursor['y_position'],
                    'color': cursor['color'],
                    'selected': cursor.get('selected', False)
                }
                cursor_info.append(info)
            
            return cursor_info
            
        except Exception as e:
            print(f"Error getting cursor info: {e}")
            import traceback
            traceback.print_exc()
            return []
