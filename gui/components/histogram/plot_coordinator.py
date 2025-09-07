#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot Coordinator - 绘图协调器
组合和协调各个管理器，提供统一的接口
"""

import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt

from .base_plot import BasePlot
from .cursor_manager import CursorManager
from .fitting_manager import FittingManager
from .plot_utils import RecursionGuard, DataCleaner, AxisCalculator


class HistogramPlot(BasePlot):
    """直方图绘图协调器 - 新的主类"""
    
    # 定义信号
    cursor_deselected = pyqtSignal()
    cursor_selected = pyqtSignal(int)
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        super().__init__(parent, width, height, dpi)
        
        # 初始化防护机制
        self.guard = RecursionGuard()
        
        # 初始化管理器
        self.cursor_manager = CursorManager(self)
        self.fitting_manager = FittingManager(self)
        
        # 设置直方图模式标志
        self.is_histogram_mode = False
        self.histogram_data = None
        self.histogram_bins = 50
        
        # 连接管理器的信号
        self._connect_manager_signals()
        
        # 初始化ax3拟合线条跟踪
        self._ax3_fit_lines = []
    
    def _connect_manager_signals(self):
        """连接各管理器的信号 - 添加防护"""
        # 连接cursor管理器信号
        self.cursor_manager.cursor_deselected.connect(self._on_cursor_deselected)
        self.cursor_manager.cursor_selected.connect(self._on_cursor_selected)
        
        # 连接拟合管理器信号
        self.fitting_manager.region_selected.connect(self.region_selected)
    
    def _on_cursor_deselected(self):
        """处理cursor取消选中信号 - 防止递归"""
        if not self.guard.is_signal_emitting("cursor_deselected_forward"):
            self.guard.set_signal_emitting("cursor_deselected_forward", True)
            try:
                self.cursor_deselected.emit()
            finally:
                self.guard.set_signal_emitting("cursor_deselected_forward", False)
    
    def _on_cursor_selected(self, cursor_id):
        """处理cursor选中信号 - 防止递归"""
        if not self.guard.is_signal_emitting("cursor_selected_forward"):
            self.guard.set_signal_emitting("cursor_selected_forward", True)
            try:
                self.cursor_selected.emit(cursor_id)
            finally:
                self.guard.set_signal_emitting("cursor_selected_forward", False)
    
    def set_shared_fit_data(self, shared_fit_data):
        """设置共享的拟合数据引用"""
        self.shared_fit_data = shared_fit_data
        self.fitting_manager.set_shared_fit_data(shared_fit_data)
        print(f"Set shared fit data: {shared_fit_data}")
    
    # =================== Cursor 功能代理方法 ===================
    
    def add_cursor(self, y_position=None, color=None):
        """添加cursor"""
        cursor_id = self.cursor_manager.add_cursor(y_position, color)
        if cursor_id is not None and hasattr(self, 'cursors'):
            # 为了兼容性，同步到cursors属性
            self.cursors = self.cursor_manager.cursors
            self.cursor_counter = self.cursor_manager.cursor_counter
        return cursor_id
    
    def remove_cursor(self, cursor_id):
        """移除cursor"""
        success = self.cursor_manager.remove_cursor(cursor_id)
        if success and hasattr(self, 'cursors'):
            self.cursors = self.cursor_manager.cursors
            self.cursor_counter = self.cursor_manager.cursor_counter
        return success
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        success = self.cursor_manager.clear_all_cursors()
        if success and hasattr(self, 'cursors'):
            self.cursors = self.cursor_manager.cursors
            self.cursor_counter = self.cursor_manager.cursor_counter
        return success
    
    def select_cursor(self, cursor_id):
        """选择cursor"""
        success = self.cursor_manager.select_cursor(cursor_id)
        if success and hasattr(self, 'selected_cursor'):
            self.selected_cursor = self.cursor_manager.selected_cursor
        return success
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新cursor位置"""
        return self.cursor_manager.update_cursor_position(cursor_id, new_position)
    
    def get_cursor_info(self):
        """获取cursor信息"""
        return self.cursor_manager.get_cursor_info()
    
    def refresh_cursors_after_plot_update(self):
        """在plot更新后刷新cursor"""
        self.cursor_manager.refresh_cursors_after_plot_update()
    
    def refresh_cursors_for_histogram_mode(self):
        """在直方图模式下刷新cursor"""
        self.cursor_manager.refresh_cursors_for_histogram_mode()
    
    # =================== 拟合功能代理方法 ===================
    
    def clear_fits(self):
        """清除所有拟合"""
        self.fitting_manager.clear_fits()
    
    def delete_specific_fit(self, fit_index):
        """删除特定拟合"""
        return self.fitting_manager.delete_specific_fit(fit_index)
    
    def save_current_fits(self):
        """保存当前拟合"""
        self.fitting_manager.save_current_fits()
    
    def restore_fits_from_shared_data(self):
        """从共享数据恢复拟合"""
        return self.fitting_manager.restore_fits_from_shared_data()
    
    def toggle_fit_labels(self, visible):
        """切换拟合标签可见性"""
        self.fitting_manager.toggle_fit_labels(visible)
    
    # =================== 直方图模式方法 ===================
    
    def plot_subplot3_histogram(self, data, bins=50, log_x=False, log_y=False, show_kde=False, file_name=""):
        """为subplot3绘制直方图（直方图标签页模式）"""
        try:
            # 清理数据
            cleaned_data = self.data_cleaner.clean_data(data)
            if cleaned_data is None or len(cleaned_data) == 0:
                print("Warning: No valid data for subplot3 histogram")
                return
            
            # 设置直方图模式
            self.is_histogram_mode = True
            self.histogram_data = cleaned_data
            self.histogram_bins = bins
            
            # 清除当前figure并创建新的subplot
            self.fig.clear()
            self.ax = self.fig.add_subplot(111)
            
            # 绘制直方图
            self.hist_counts, self.hist_bin_edges, _ = self.ax.hist(
                cleaned_data, bins=bins, alpha=0.7, density=False
            )
            
            # 计算bin中心点
            self.hist_bin_centers = (self.hist_bin_edges[:-1] + self.hist_bin_edges[1:]) / 2
            
            # 设置标题和标签
            title = "Histogram of Highlighted Region"
            if file_name:
                title = f"{file_name} - {title}"
            self.ax.set_title(title, fontsize=12)
            
            # 添加使用提示
            msg = "Click and drag to select regions for Gaussian fitting"
            self.ax.annotate(msg, xy=(0.98, 0.02), xycoords='figure fraction', 
                        ha='right', va='bottom', fontsize=9, color='navy',
                        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
            
            self.ax.set_xlabel("Amplitude", fontsize=10)
            self.ax.set_ylabel("Count", fontsize=10)
            
            # 设置对数刻度
            if log_x:
                try:
                    self.ax.set_xscale('log')
                except:
                    print("Cannot set X-axis to log scale")
            
            if log_y:
                if self._check_log_scale_validity():
                    try:
                        self.ax.set_yscale('log')
                    except:
                        print("Cannot set Y-axis to log scale")
                        self.ax.set_yscale('linear')
                else:
                    print("Y-axis log scale disabled: histogram contains zero counts")
                    self.ax.set_yscale('linear')
            
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
            
            # 添加网格线
            self.ax.grid(True, linestyle='--', alpha=0.7)
            
            # 设置拟合管理器
            self.fitting_manager.setup_for_histogram_mode()
            
            # 刷新cursor显示
            if hasattr(self.cursor_manager, 'cursors') and self.cursor_manager.cursors:
                self.refresh_cursors_for_histogram_mode()
            
            # 调整布局
            self.fig.tight_layout(pad=1.0)
            
            # 绘制
            self.guard.throttled_draw(self)
            
        except Exception as e:
            print(f"Error plotting subplot3 histogram: {e}")
            import traceback
            traceback.print_exc()
    
    def update_highlighted_plots(self):
        """更新高亮区域和直方图 - 增强版，支持拟合同步"""
        if self.data is None:
            return

        # 先清空拟合数据（如果数据区域变化）
        if self.shared_fit_data and self.shared_fit_data.has_fits():
            print("[Fix] Clearing shared fit data from update_highlighted_plots")
            self.shared_fit_data.clear_fits()

        # 调用父类方法更新基础绘图
        super().update_highlighted_plots()
        
        # 刷新cursor显示
        if hasattr(self.cursor_manager, 'cursors') and self.cursor_manager.cursors:
            self.refresh_cursors_after_plot_update()

        # 处理主视图subplot3中的拟合显示
        self._update_ax3_fit_display()
    
    def _update_ax3_fit_display(self):
        """更新ax3中的拟合曲线显示"""
        highlighted_data = None
        
        # 确保 _ax3_fit_lines 已初始化
        if not hasattr(self, '_ax3_fit_lines'):
            self._ax3_fit_lines = []
        
        try:
            # 清除ax3中的旧拟合线条
            if self._ax3_fit_lines:
                for line in self._ax3_fit_lines[:]:
                    try:
                        if line and line in self.ax3.lines:
                            line.remove()
                    except:
                        pass
                self._ax3_fit_lines.clear()
            
            # 获取高亮数据
            highlighted_data = -self.data[self.highlight_min:self.highlight_max] if self.invert_data else self.data[self.highlight_min:self.highlight_max]
            highlighted_data = self.data_cleaner.clean_data(highlighted_data)
            
            # 如果有共享拟合数据，在ax3中显示
            if (highlighted_data is not None and 
                hasattr(self, 'ax3') and 
                self.shared_fit_data is not None and 
                self.shared_fit_data.has_fits()):
                
                # 获取拟合数据
                fits, regions = self.shared_fit_data.get_fits()
                
                # 在ax3中绘制拟合曲线
                for fit_data in fits:
                    if not fit_data or 'popt' not in fit_data:
                        continue
                        
                    popt = fit_data['popt']
                    x_range = fit_data['x_range']
                    color = fit_data['color']
                    
                    # 检查范围是否有重叠
                    data_min, data_max = highlighted_data.min(), highlighted_data.max()
                    data_range = data_max - data_min
                    tolerance = max(0.1 * data_range, 0.001)
                    
                    has_overlap = (x_range[1] > data_min - tolerance and x_range[0] < data_max + tolerance)
                    
                    if has_overlap:
                        # 高斯函数
                        def gaussian(x, amp, mu, sigma):
                            return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
                        
                        # 创建拟合曲线数据
                        x_fit = np.linspace(x_range[0], x_range[1], 150)
                        y_fit = gaussian(x_fit, *popt)
                        
                        # 绘制曲线（注意直方图是horizontal，所以x/y对应count/amplitude）
                        line, = self.ax3.plot(y_fit, x_fit, '-', linewidth=1.0, color=color, zorder=15)
                        self._ax3_fit_lines.append(line)
                        
                        print(f"Applied fit to subplot3: color={color}, range={x_range}")
                
                # 确保轴范围能显示所有拟合曲线
                if self._ax3_fit_lines:
                    current_ylim = self.ax3.get_ylim()
                    all_fit_ranges = [fit_data['x_range'] for fit_data in fits if fit_data and 'x_range' in fit_data]
                    if all_fit_ranges:
                        fit_min = min(r[0] for r in all_fit_ranges)
                        fit_max = max(r[1] for r in all_fit_ranges)
                        new_ymin = min(current_ylim[0], fit_min)
                        new_ymax = max(current_ylim[1], fit_max)
                        if new_ymin != current_ylim[0] or new_ymax != current_ylim[1]:
                            self.ax3.set_ylim(new_ymin, new_ymax)
                            print(f"Extended ax3 y-axis range to [{new_ymin:.4f}, {new_ymax:.4f}] to show all fits")
                
                print(f"Applied {len(fits)} fits to subplot3 in main view, displayed {len(self._ax3_fit_lines)} lines")
                
        except Exception as e:
            print(f"Error applying fits to subplot3 in main view: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_data_hash(self):
        """计算数据哈希值用于检测数据变化"""
        if hasattr(self, 'histogram_data') and self.histogram_data is not None:
            from .plot_utils import DataHasher
            return DataHasher.calculate_data_hash(self.histogram_data)
        return None
    
    # =================== 额外的绘图方法 ===================
    
    def move_highlight(self, position_percent):
        """移动高亮区域位置"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 先清空拟合数据（数据区域变化）
        if self.shared_fit_data and self.shared_fit_data.has_fits():
            print("[Fix] Clearing shared fit data from move_highlight")
            self.shared_fit_data.clear_fits()
        
        self._validate_highlight_indices()
        
        # 计算当前高亮区域大小
        current_size = self.highlight_max - self.highlight_min
        
        # 计算新的起始位置
        max_start_pos = len(self.data) - current_size
        new_start = int(position_percent * max_start_pos / 100)
        new_start = max(0, min(new_start, max_start_pos))
        
        # 设置新的高亮区域
        self.highlight_min = new_start
        self.highlight_max = new_start + current_size
        
        # 确保不超出数据范围
        if self.highlight_max > len(self.data):
            self.highlight_max = len(self.data)
            self.highlight_min = self.highlight_max - current_size
        
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
        self.guard.throttled_draw(self)
    
    def immediate_sync_to_main_view(self):
        """立即同步拟合结果到主视图的subplot3"""
        if hasattr(self.fitting_manager, 'immediate_sync_to_main_view'):
            self.fitting_manager.immediate_sync_to_main_view()
    
    # =================== 兼容性方法 ===================
    
    @property
    def cursors(self):
        """获取cursors列表 - 兼容性属性"""
        return self.cursor_manager.cursors if hasattr(self.cursor_manager, 'cursors') else []
    
    @cursors.setter
    def cursors(self, value):
        """设置cursors列表 - 兼容性属性"""
        if hasattr(self.cursor_manager, 'cursors'):
            self.cursor_manager.cursors = value
    
    @property
    def cursor_counter(self):
        """获取cursor计数器 - 兼容性属性"""
        return self.cursor_manager.cursor_counter if hasattr(self.cursor_manager, 'cursor_counter') else 0
    
    @cursor_counter.setter
    def cursor_counter(self, value):
        """设置cursor计数器 - 兼容性属性"""
        if hasattr(self.cursor_manager, 'cursor_counter'):
            self.cursor_manager.cursor_counter = value
    
    @property
    def selected_cursor(self):
        """获取选中的cursor - 兼容性属性"""
        return self.cursor_manager.selected_cursor if hasattr(self.cursor_manager, 'selected_cursor') else None
    
    @selected_cursor.setter
    def selected_cursor(self, value):
        """设置选中的cursor - 兼容性属性"""
        if hasattr(self.cursor_manager, 'selected_cursor'):
            self.cursor_manager.selected_cursor = value
    
    @property
    def gaussian_fits(self):
        """获取拟合结果 - 兼容性属性"""
        return self.fitting_manager.gaussian_fits if hasattr(self.fitting_manager, 'gaussian_fits') else []
    
    @property
    def fit_info_str(self):
        """获取拟合信息字符串 - 兼容性属性"""
        return self.fitting_manager.fit_info_str if hasattr(self.fitting_manager, 'fit_info_str') else "No fits yet"
