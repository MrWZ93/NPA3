#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spikes Plot Module - 峰值数据绘图模块
用于绘制峰值数据的绘图组件
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtCore import pyqtSignal

# 导入自定义样式
from gui.styles import PLOT_STYLE, PLOT_COLORS, COLORS


class SpikesDataPlot(FigureCanvas):
    """用于绘制峰值数据的绘图组件"""
    
    # 添加信号用于通知峰值数据更新
    peak_data_changed = pyqtSignal(int, dict)  # 参数：峰值 ID 和更新后的数据
    
    def __init__(self, parent=None, width=8, height=3, dpi=100):
        # 首先创建图形
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        
        # 初始化画布
        super(SpikesDataPlot, self).__init__(self.fig)
        self.setParent(parent)
        
        # 设置图表样式
        for key, value in PLOT_STYLE.items():
            plt.rcParams[key] = value
        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=PLOT_COLORS)
        self.fig.patch.set_facecolor(COLORS["card"])
        
        # 创建两个轴：一个用于整个trace，一个用于当前选择的spike
        self.grid = self.fig.add_gridspec(2, 1, height_ratios=[2, 1])
        self.ax_trace = self.fig.add_subplot(self.grid[0])
        self.ax_peak = self.fig.add_subplot(self.grid[1])
        
        # 初始数据
        self.data = None
        self.time_axis = None
        self.sampling_rate = 1000.0  # 默认采样率
        self.peaks_indices = []      # 峰值索引
        self.peaks_data = {}         # 峰值数据
        self.current_peak_idx = -1   # 当前选择的峰值索引
        self.current_channel_data = None  # 当前通道数据
        
        # 初始化游标
        self.cursor_start = None  # 左游标
        self.cursor_end = None    # 右游标
        self.cursor_amp = None    # 上下游标
        self.cursor_start_label = None  # 左游标标签
        self.cursor_end_label = None    # 右游标标签
        self.cursor_amp_label = None    # 上下游标标签
        self.cursor_active = False # 游标是否激活
        self.dragging_cursor = None # 正在拖拽的游标
        
        # 美化设置
        self.ax_trace.set_title("I-t Trace", fontsize=10, fontweight='bold')
        self.ax_trace.set_xlabel("Time (s)", fontsize=9)
        self.ax_trace.set_ylabel("Current (nA)", fontsize=9)
        self.ax_trace.grid(True, linestyle='--', alpha=0.7)
        
        self.ax_peak.set_title("Selected Peak", fontsize=10, fontweight='bold')
        self.ax_peak.set_xlabel("Time (s)", fontsize=9)
        self.ax_peak.set_ylabel("Current (nA)", fontsize=9)
        self.ax_peak.grid(True, linestyle='--', alpha=0.7)
        
        # 连接鼠标事件
        self.mpl_connect('button_press_event', self.on_mouse_press)
        self.mpl_connect('button_release_event', self.on_mouse_release)
        self.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        self.fig.tight_layout(pad=2.0)
    
    def create_cursor_for_mode(self, peak_data, mode=None):
        """根据选择的模式创建游标
        
        Args:
            peak_data: 峰值数据字典
            mode: 游标模式字符串，优先级高于单选按钮状态
            
        注意: 这个方法已被弃用，请使用create_cursors方法代替。
        此方法的设计问题是只创建一个游标，而非全部游标。
        """
        # 为了兼容性，直接调用新方法
        print("Redirecting to create_cursors method...")
        self.create_cursors(peak_data)
        
        # 根据模式设置当前拖拽游标
        if mode:
            # 从传入的模式字符串确定类型
            mode_lower = mode.lower()
            if 'start' in mode_lower:
                self.dragging_cursor = 'start'
            elif 'end' in mode_lower:
                self.dragging_cursor = 'end'
            elif 'amp' in mode_lower or 'amplitude' in mode_lower:
                self.dragging_cursor = 'amp'
        else:
            # 从单选按钮状态确定
            if hasattr(self, 'start_cursor_radio') and self.start_cursor_radio.isChecked():
                self.dragging_cursor = 'start'
            elif hasattr(self, 'end_cursor_radio') and self.end_cursor_radio.isChecked():
                self.dragging_cursor = 'end'
            elif hasattr(self, 'amp_cursor_radio') and self.amp_cursor_radio.isChecked():
                self.dragging_cursor = 'amp'
    
    def plot_data(self, data, sampling_rate=None, time_offset=0.0):
        """绘制数据
        
        Args:
            data: 数据
            sampling_rate: 采样率
            time_offset: 时间偏移（秒），用于显示全局时间
        """
        self.data = data
        if sampling_rate is not None:
            self.sampling_rate = sampling_rate
        
        # 生成时间轴（带偏移）
        if self.current_channel_data is not None:
            # 使用当前选中的通道数据
            data_length = len(self.current_channel_data)
            self.time_axis = np.arange(data_length) / self.sampling_rate + time_offset
        elif isinstance(data, dict):
            # 如果是字典类型（多通道数据），找到第一个可用通道
            channel_data = next(iter(data.values()))
            self.time_axis = np.arange(len(channel_data)) / self.sampling_rate + time_offset
            # 如果当前通道数据未设置，使用第一个通道
            if self.current_channel_data is None:
                self.current_channel_data = channel_data
        elif isinstance(data, np.ndarray):
            if data.ndim == 1:
                # 单通道数据
                self.time_axis = np.arange(len(data)) / self.sampling_rate + time_offset
                if self.current_channel_data is None:
                    self.current_channel_data = data
            elif data.ndim == 2 and data.shape[1] > 0:
                # 多通道数据（二维数组）
                self.time_axis = np.arange(data.shape[0]) / self.sampling_rate + time_offset
                if self.current_channel_data is None:
                    self.current_channel_data = data[:, 0]  # 使用第一列
        else:
            # 其他情况
            if self.current_channel_data is None:
                if isinstance(data, np.ndarray):
                    self.time_axis = np.arange(len(data)) / self.sampling_rate + time_offset
                    self.current_channel_data = data
                else:
                    self.time_axis = None
                    self.current_channel_data = None
                    return
        
        # 清空之前的图表
        self.ax_trace.clear()
        self.ax_peak.clear()
        
        # 绘制整个trace
        if self.current_channel_data is not None and self.time_axis is not None:
            self.ax_trace.plot(self.time_axis, self.current_channel_data, linewidth=0.5)
            
            # 设置轴标题和样式
            self.ax_trace.set_title("I-t Trace", fontsize=10, fontweight='bold')
            self.ax_trace.set_xlabel("Time (s)", fontsize=9)
            self.ax_trace.set_ylabel("Current (nA)", fontsize=9)
            self.ax_trace.grid(True, linestyle='--', alpha=0.7)
            
            # 美化
            self.ax_trace.spines['top'].set_visible(False)
            self.ax_trace.spines['right'].set_visible(False)
            self.ax_peak.spines['top'].set_visible(False)
            self.ax_peak.spines['right'].set_visible(False)
            
            self.fig.tight_layout(pad=2.0)
            self.draw()
    
    def plot_peaks(self, peaks_indices, color='red', marker='o'):
        """标记峰值点在trace上"""
        if self.current_channel_data is None or len(peaks_indices) == 0:
            return
        
        # 清除之前的峰值标记
        for line in self.ax_trace.lines[1:]:
            line.remove()
        
        # 绘制峰值点
        self.ax_trace.plot(self.time_axis[peaks_indices], self.current_channel_data[peaks_indices], 
                          color=color, marker=marker, linestyle='none')
        
        # 存储峰值索引
        self.peaks_indices = peaks_indices
        
        # 计算并存储每个峰值的数据
        self.peaks_data = {}
        for i, peak_idx in enumerate(peaks_indices):
            self.peaks_data[i] = {
                'index': peak_idx,
                'time': self.time_axis[peak_idx],
                'amplitude': self.current_channel_data[peak_idx],
                # 持续时间和其他属性将在后续处理中添加
            }
        
        self.draw()
    
    def set_peak_duration(self, peak_id, start_idx, end_idx):
        """设置峰值的持续时间"""
        if peak_id in self.peaks_data:
            self.peaks_data[peak_id]['start_idx'] = start_idx
            self.peaks_data[peak_id]['end_idx'] = end_idx
            self.peaks_data[peak_id]['start_time'] = self.time_axis[start_idx]
            self.peaks_data[peak_id]['end_time'] = self.time_axis[end_idx]
            self.peaks_data[peak_id]['duration'] = self.time_axis[end_idx] - self.time_axis[start_idx]
    
    def highlight_peak(self, peak_id):
        """高亮显示选中的峰值并在下方图表中显示放大后的视图"""
        try:
            self.current_peak_idx = peak_id
            
            # 获取峰值数据
            if peak_id not in self.peaks_data:
                print(f"Peak ID {peak_id} not found in peaks_data")
                return
            
            peak_data = self.peaks_data[peak_id]
            peak_idx = peak_data['index']
            
            # 在trace上高亮
            self.ax_trace.clear()
            self.ax_trace.plot(self.time_axis, self.current_channel_data)
            self.ax_trace.plot(self.time_axis[self.peaks_indices], self.current_channel_data[self.peaks_indices], 
                            color='red', marker='o', linestyle='none')
            
            # 突出显示当前选中的峰值
            self.ax_trace.plot(self.time_axis[peak_idx], self.current_channel_data[peak_idx], 
                            color='green', marker='*', markersize=10)
            
            # 如果有持续时间信息，显示持续时间范围
            if 'start_idx' in peak_data and 'end_idx' in peak_data:
                start_idx = peak_data['start_idx']
                end_idx = peak_data['end_idx']
                
                # 突出显示峰值区间
                self.ax_trace.axvspan(self.time_axis[start_idx], self.time_axis[end_idx], 
                                    alpha=0.2, color='green')
            
            # 在下方显示放大的峰值
            self.ax_peak.clear()
            
            # 安全清除游标和标签
            self._clear_cursors()
            
            # 确定要显示的窗口范围（前后多显示一些点）
            window = 50  # 峰值前后各显示的点数
            start = max(0, peak_idx - window)
            end = min(len(self.current_channel_data), peak_idx + window)
            
            # 如果有持续时间信息，调整显示窗口以包含整个峰值
            if 'start_idx' in peak_data and 'end_idx' in peak_data:
                start = max(0, peak_data['start_idx'] - window // 2)
                end = min(len(self.current_channel_data), peak_data['end_idx'] + window // 2)
            
            # 绘制放大的峰值
            self.ax_peak.plot(self.time_axis[start:end], self.current_channel_data[start:end])
            self.ax_peak.plot(self.time_axis[peak_idx], self.current_channel_data[peak_idx], 
                            color='green', marker='*', markersize=10)
            
            # 如果有持续时间信息，显示持续时间范围
            if 'start_idx' in peak_data and 'end_idx' in peak_data:
                self.ax_peak.axvspan(self.time_axis[peak_data['start_idx']], 
                                    self.time_axis[peak_data['end_idx']], 
                                    alpha=0.2, color='green')
                
                # 创建游标
                try:
                    self.create_cursors(peak_data)
                except Exception as e:
                    import traceback
                    print(f"Error creating cursors: {e}")
                    print(traceback.format_exc())
            
            # 美化设置
            self.ax_trace.set_title("I-t Trace", fontsize=10, fontweight='bold')
            self.ax_trace.set_xlabel("Time (s)", fontsize=9)
            self.ax_trace.set_ylabel("Current (nA)", fontsize=9)
            self.ax_trace.grid(True, linestyle='--', alpha=0.7)
            self.ax_trace.spines['top'].set_visible(False)
            self.ax_trace.spines['right'].set_visible(False)
            
            peak_info = f"Peak {peak_id+1}: {peak_data['amplitude']:.2f} nA"
            if 'duration' in peak_data:
                peak_info += f", Duration: {peak_data['duration']*1000:.2f} ms"
            
            self.ax_peak.set_title(peak_info, fontsize=10, fontweight='bold')
            self.ax_peak.set_xlabel("Time (s)", fontsize=9)
            self.ax_peak.set_ylabel("Current (nA)", fontsize=9)
            self.ax_peak.grid(True, linestyle='--', alpha=0.7)
            self.ax_peak.spines['top'].set_visible(False)
            self.ax_peak.spines['right'].set_visible(False)
            
            # 添加游标操作提示，不保存引用，避免移除问题
            self.ax_peak.text(0.5, 0.02, "Drag colored lines to adjust peak properties", 
                            transform=self.ax_peak.transAxes,
                            ha='center', va='bottom', fontsize=8, color='gray',
                            bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7))
                            
            # 缓存背景用于后续快速绘制
            try:
                # 确保在绘制后再缓存背景
                self.fig.canvas.draw()
                self._background = self.fig.canvas.copy_from_bbox(self.ax_peak.bbox)
            except Exception as e:
                print(f"Warning: Could not cache background: {e}")
                self._background = None
            
            self.cursor_active = True
            self.fig.tight_layout(pad=2.0)
            
        except Exception as e:
            import traceback
            print(f"Error in highlight_peak: {e}")
            print(traceback.format_exc())
        
    def _clear_cursors(self):
        """安全清除所有游标元素"""
        # 清除游标线
        for cursor in [self.cursor_start, self.cursor_end, self.cursor_amp]:
            if cursor and cursor in self.ax_peak.lines:
                try:
                    cursor.remove()
                except ValueError:
                    pass
        self.cursor_start = None
        self.cursor_end = None
        self.cursor_amp = None
        
        # 清除标签
        for label in [self.cursor_start_label, self.cursor_end_label, self.cursor_amp_label]:
            if label and label in self.ax_peak.texts:
                try:
                    label.remove()
                except ValueError:
                    pass
        self.cursor_start_label = None
        self.cursor_end_label = None
        self.cursor_amp_label = None
        
        # 清除提示文字
        if hasattr(self, '_instruction_text') and self._instruction_text:
            try:
                # 首先尝试从texts集合中移除
                if self._instruction_text in self.ax_peak.texts:
                    self.ax_peak.texts.remove(self._instruction_text)
                else:
                    # 如果找不到，尝试设置为不可见
                    self._instruction_text.set_visible(False)
            except (ValueError, NotImplementedError, AttributeError) as e:
                print(f"Warning: Could not remove instruction text: {e}")
                # 尝试备用方法
                try:
                    self._instruction_text.set_visible(False)
                except:
                    pass
        self._instruction_text = None
    
    def create_cursors(self, peak_data):
        """创建三个游标：左(开始)、右(结束)和上下(振幅)"""
        try:
            self._clear_cursors()  # 先清除旧游标
            
            # 获取当前视图范围
            y_min, y_max = self.ax_peak.get_ylim()
            x_min, x_max = self.ax_peak.get_xlim()
            
            # 确保关键数据存在
            required_keys = ['start_time', 'end_time', 'amplitude']
            for key in required_keys:
                if key not in peak_data:
                    print(f"Warning: Missing key '{key}' in peak_data")
                    return
            
            # 创建左游标
            self.cursor_start = self.ax_peak.axvline(
                peak_data['start_time'], 
                color='red', 
                linewidth=2.5, 
                alpha=0.8,
                picker=5,  # 增大选取半径
                zorder=100
            )
            
            # 创建右游标
            self.cursor_end = self.ax_peak.axvline(
                peak_data['end_time'], 
                color='blue',
                linewidth=2.5,
                alpha=0.8,
                picker=5,
                zorder=100
            )
            
            # 创建振幅游标
            self.cursor_amp = self.ax_peak.axhline(
                peak_data['amplitude'],
                color='green',
                linewidth=2.5,
                alpha=0.8,
                picker=5,
                zorder=100
            )
            
            # 添加动态标签
            self.cursor_start_label = self.ax_peak.text(
                peak_data['start_time'], 
                y_min + (y_max - y_min) * 0.1,
                f"Start: {peak_data['start_time']:.3f}s",
                color='red', 
                fontweight='bold', 
                ha='center', 
                va='bottom',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='red', pad=2),
                zorder=101
            )
            
            self.cursor_end_label = self.ax_peak.text(
                peak_data['end_time'],
                y_min + (y_max - y_min) * 0.1,
                f"End: {peak_data['end_time']:.3f}s",
                color='blue',
                fontweight='bold',
                ha='center',
                va='bottom',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='blue', pad=2),
                zorder=101
            )
            
            self.cursor_amp_label = self.ax_peak.text(
                x_min + (x_max - x_min) * 0.05, 
                peak_data['amplitude'],
                f"Amp: {peak_data['amplitude']:.3f}",
                color='green',
                fontweight='bold',
                ha='left',
                va='center',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='green', pad=2),
                zorder=101
            )
            
            # 添加提示文字 - 不保存引用以避免清除问题
            self.ax_peak.text(
                0.5, 0.02, 
                "Click and drag colored lines to adjust peak properties",
                transform=self.ax_peak.transAxes, 
                ha='center', 
                va='bottom',
                fontsize=8, 
                color='gray',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7),
                zorder=99
            )
                
            self.cursor_active = True
            
            # 预缓存背景
            try:
                self.fig.canvas.draw_idle()
                self._background = self.fig.canvas.copy_from_bbox(self.ax_peak.bbox)
            except Exception as e:
                print(f"Warning: Could not cache background: {e}")
                self._background = None
            
        except Exception as e:
            import traceback
            print(f"Error creating cursors: {e}")
            print(traceback.format_exc())
            self.cursor_active = False
    
    def on_mouse_press(self, event):
        """改进的鼠标按下处理"""
        if not self.cursor_active or event.inaxes != self.ax_peak:
            return
        
        # 转换坐标到数据坐标系
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        
        # 动态计算点击范围（基于当前视图比例）
        x_range = self.ax_peak.get_xlim()
        y_range = self.ax_peak.get_ylim()
        hitbox_x = (x_range[1] - x_range[0]) * 0.01  # 1%的x范围
        hitbox_y = (y_range[1] - y_range[0]) * 0.01  # 1%的y范围
        
        # 检查最近游标
        min_dist = float('inf')
        selected_cursor = None
        
        # 检查垂直游标（start/end）
        for cursor_name, cursor in [('start', self.cursor_start), ('end', self.cursor_end)]:
            if cursor and cursor.get_visible():
                try:
                    lx = cursor.get_xdata()[0]
                    distance = abs(x - lx)
                    if distance < hitbox_x and distance < min_dist:
                        min_dist = distance
                        selected_cursor = cursor_name
                except (IndexError, AttributeError):
                    pass
        
        # 检查水平游标（amp）
        if self.cursor_amp and self.cursor_amp.get_visible():
            try:
                ly = self.cursor_amp.get_ydata()[0]
                distance = abs(y - ly)
                if distance < hitbox_y and distance < min_dist:
                    selected_cursor = 'amp'
            except (IndexError, AttributeError):
                pass
        
        if selected_cursor:
            self.dragging_cursor = selected_cursor
            self._drag_start_pos = (x, y)
            # 存储原始值，确保其存在
            self._original_values = {}
            try:
                if self.cursor_start and self.cursor_start.get_visible():
                    self._original_values['start'] = self.cursor_start.get_xdata()[0]
                if self.cursor_end and self.cursor_end.get_visible():
                    self._original_values['end'] = self.cursor_end.get_xdata()[0]
                if self.cursor_amp and self.cursor_amp.get_visible():
                    self._original_values['amp'] = self.cursor_amp.get_ydata()[0]
            except (IndexError, AttributeError) as e:
                print(f"Error capturing original cursor values: {e}")
                self._original_values = {}
                self.dragging_cursor = None
                return
            
            # 初始化背景缓存
            try:
                self._background = self.fig.canvas.copy_from_bbox(self.ax_peak.bbox)
            except Exception as e:
                print(f"Warning: Could not cache background: {e}")
                self._background = None

    def on_mouse_move(self, event):
        """优化性能的鼠标移动处理"""
        if not hasattr(self, 'dragging_cursor') or not self.dragging_cursor:
            return
        
        try:
            # 获取鼠标位置，如果鼠标移出图表则使用最后位置
            x = event.xdata if event.xdata is not None else self._drag_start_pos[0]
            y = event.ydata if event.ydata is not None else self._drag_start_pos[1]
            
            # 获取当前视图限制
            x_min, x_max = self.ax_peak.get_xlim()
            y_min, y_max = self.ax_peak.get_ylim()
            
            # 确保_original_values字典存在必要的键
            if not hasattr(self, '_original_values') or not self._original_values:
                self._original_values = {}
                if self.cursor_start:
                    try:
                        self._original_values['start'] = self.cursor_start.get_xdata()[0]
                    except:
                        self._original_values['start'] = x_min
                else:
                    self._original_values['start'] = x_min
                    
                if self.cursor_end:
                    try:
                        self._original_values['end'] = self.cursor_end.get_xdata()[0]
                    except:
                        self._original_values['end'] = x_max
                else:
                    self._original_values['end'] = x_max
            
            # 限制移动范围并更新游标位置
            if self.dragging_cursor == 'start':
                if 'end' not in self._original_values:
                    # 如果没有结束点记录，使用当前视图的最大值
                    self._original_values['end'] = x_max
                
                new_x = min(max(x_min, x), self._original_values.get('end', x_max))
                
                if self.cursor_start:
                    self.cursor_start.set_xdata([new_x, new_x])
                    
                if self.cursor_start_label:
                    self.cursor_start_label.set_position((new_x, y_min + (y_max - y_min)*0.1))
                    self.cursor_start_label.set_text(f"Start: {new_x:.3f}s")
                    
            elif self.dragging_cursor == 'end':
                if 'start' not in self._original_values:
                    # 如果没有起始点记录，使用当前视图的最小值
                    self._original_values['start'] = x_min
                    
                new_x = max(min(x_max, x), self._original_values.get('start', x_min))
                
                if self.cursor_end:
                    self.cursor_end.set_xdata([new_x, new_x])
                    
                if self.cursor_end_label:
                    self.cursor_end_label.set_position((new_x, y_min + (y_max - y_min)*0.1))
                    self.cursor_end_label.set_text(f"End: {new_x:.3f}s")
                    
            elif self.dragging_cursor == 'amp':
                new_y = min(max(y_min, y), y_max)
                
                if self.cursor_amp:
                    self.cursor_amp.set_ydata([new_y, new_y])
                    
                if self.cursor_amp_label:
                    self.cursor_amp_label.set_position((x_min + (x_max - x_min)*0.05, new_y))
                    self.cursor_amp_label.set_text(f"Amp: {new_y:.3f}")
            
            # 强制重绘以显示更新 - 使用更可靠的方法
            self.fig.canvas.draw_idle()
            
        except Exception as e:
            import traceback
            print(f"Error in mouse movement: {e}")
            print(traceback.format_exc())

    def on_mouse_release(self, event):
        """处理鼠标释放事件，停止拖拽并更新峰值数据"""
        try:
            if self.dragging_cursor and self.current_peak_idx >= 0 and self.current_peak_idx in self.peaks_data:
                # 从游标位置更新峰值数据
                print(f"Updating peak data from cursor {self.dragging_cursor}")
                self.update_peak_data_from_cursors()
                
                # 发送更新信号
                self.peak_data_changed.emit(self.current_peak_idx, self.peaks_data[self.current_peak_idx])
                print("Peak data updated and signal emitted")
            
            # 强制重绘整个图形以确保一致性
            self.fig.canvas.draw()
            
        except Exception as e:
            import traceback
            print(f"Error in mouse release: {e}")
            print(traceback.format_exc())
        finally:
            # 确保拖拽状态被重置
            self.dragging_cursor = None
            # 清除临时存储的数据
            if hasattr(self, '_drag_start_pos'):
                self._drag_start_pos = None

    def on_draw(self, event):
        """缓存背景用于快速刷新"""
        self._background = self.fig.canvas.copy_from_bbox(self.ax_peak.bbox)
    
    def update_peak_data_from_cursors(self):
        """根据游标位置更新峰值数据"""
        try:
            print("Entering update_peak_data_from_cursors")
            if self.current_peak_idx not in self.peaks_data:
                print(f"Peak ID {self.current_peak_idx} not found in peaks_data")
                return
            
            # 获取当前峰值数据
            peak_data = self.peaks_data[self.current_peak_idx]
            
            # 检查游标数据
            if self.dragging_cursor == 'start':
                print("Processing start cursor update")
                if hasattr(self, 'cursor_start') and self.cursor_start:
                    # 获取当前左游标时间
                    start_time = self.cursor_start.get_xdata()[0]
                    print(f"New start time: {start_time:.3f}")
                    
                    # 寻找最接近的索引
                    start_idx = np.abs(self.time_axis - start_time).argmin()
                    print(f"New start index: {start_idx}")
                    
                    # 更新峰值数据
                    peak_data['start_idx'] = start_idx
                    peak_data['start_time'] = self.time_axis[start_idx]
                else:
                    print("Start cursor not available")
            
            elif self.dragging_cursor == 'end':
                print("Processing end cursor update")
                if hasattr(self, 'cursor_end') and self.cursor_end:
                    # 获取当前右游标时间
                    end_time = self.cursor_end.get_xdata()[0]
                    print(f"New end time: {end_time:.3f}")
                    
                    # 寻找最接近的索引
                    end_idx = np.abs(self.time_axis - end_time).argmin()
                    print(f"New end index: {end_idx}")
                    
                    # 更新峰值数据
                    peak_data['end_idx'] = end_idx
                    peak_data['end_time'] = self.time_axis[end_idx]
                else:
                    print("End cursor not available")
            
            elif self.dragging_cursor == 'amp':
                print("Processing amplitude cursor update")
                if hasattr(self, 'cursor_amp') and self.cursor_amp:
                    # 获取当前振幅游标高度
                    new_amplitude = self.cursor_amp.get_ydata()[0]
                    print(f"New amplitude: {new_amplitude:.3f}")
                    
                    # 更新峰值振幅
                    peak_data['amplitude'] = new_amplitude
                else:
                    print("Amplitude cursor not available")
            
            # 修正持续时间
            if 'start_idx' in peak_data and 'end_idx' in peak_data:
                duration = self.time_axis[peak_data['end_idx']] - self.time_axis[peak_data['start_idx']]
                peak_data['duration'] = duration
                print(f"Updated duration: {duration*1000:.2f} ms")
            
            # 峰值数据已更新
            self.peaks_data[self.current_peak_idx] = peak_data
            print("Peak data successfully updated")
            
            # 更新UI反馈 - 更新峰值标题
            if hasattr(self, 'ax_peak'):
                peak_info = f"Peak {self.current_peak_idx+1}: {peak_data['amplitude']:.2f} nA"
                if 'duration' in peak_data:
                    peak_info += f", Duration: {peak_data['duration']*1000:.2f} ms"
                self.ax_peak.set_title(peak_info, fontsize=10, fontweight='bold')
        
        except Exception as e:
            import traceback
            print(f"Error updating peak data from cursors: {e}")
            print(traceback.format_exc())
    
    def get_peaks_data(self):
        """获取所有峰值数据"""
        return self.peaks_data
