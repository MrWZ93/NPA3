import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector, Slider
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                            QGroupBox, QSplitter, QRadioButton, QListWidget, QListWidgetItem,
                            QButtonGroup, QMessageBox, QTableWidget, QTableWidgetItem, 
                            QAbstractItemView, QHeaderView, QDialog, QFormLayout,
                            QMenu, QToolButton, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QColor, QFont, QAction, QIcon
import time

class ManualSpikeSelector(QWidget):
    """手动峰值选择和操作界面"""
    
    # 信号
    peak_added = pyqtSignal(dict)  # 添加了新的峰值
    peak_deleted = pyqtSignal(int)  # 删除了峰值，参数为峰值ID
    peak_updated = pyqtSignal(int, dict)  # 更新了峰值，参数为峰值ID和新的峰值数据
    
    def __init__(self, parent=None):
        super(ManualSpikeSelector, self).__init__(parent)
        
        # 初始数据
        self.plot_canvas = None
        self.manual_spike_selection = None  # 当前选择的区域
        self.manual_spikes = []  # 已标记的手动峰值列表
        self.span_selector = None  # SpanSelector对象
        self.final_span_selector = None  # 用于subplot3的SpanSelector对象
        self.slider = None  # 滑块对象
        self.manual_spike_count = 0  # 手动标记的峰值计数
        
        # 初始化图表引用
        self.manual_fig = None
        self.trace_ax = None
        self.zoomed_ax = None
        self.spike_ax = None
        
        # 初始化游标对象
        self.left_cursor = None
        self.right_cursor = None
        self.amp_cursor = None
        
        # 初始化分区状态
        self.current_section = 0
        self.current_subsection = 0
        
        # 初始化滑块位置
        self.slider_pos = 0.5  # 初始位置在中间
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建左右分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ==================== 左侧：控制面板 ====================
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 1. 手动选择控件分组
        selection_group = QGroupBox("Manual Selection Controls")
        selection_layout = QVBoxLayout(selection_group)
        
        # 1.1 模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Selection Mode:"))
        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItems(["Span Select", "Click Peak"])
        mode_layout.addWidget(self.selection_mode_combo)
        
        # 1.2 振幅模式选择
        amp_layout = QHBoxLayout()
        amp_layout.addWidget(QLabel("Amplitude Mode:"))
        self.amplitude_mode_combo = QComboBox()
        self.amplitude_mode_combo.addItems(["Maximum", "Average", "Median"])
        amp_layout.addWidget(self.amplitude_mode_combo)
        
        # 1.3 基线校正
        baseline_layout = QVBoxLayout()
        baseline_header = QHBoxLayout()
        self.baseline_correction_check = QCheckBox("Apply Baseline Correction")
        baseline_header.addWidget(self.baseline_correction_check)
        
        baseline_window_layout = QHBoxLayout()
        baseline_window_layout.addWidget(QLabel("Baseline Window (samples):"))
        self.baseline_window_spin = QSpinBox()
        self.baseline_window_spin.setRange(1, 1000)
        self.baseline_window_spin.setValue(20)
        baseline_window_layout.addWidget(self.baseline_window_spin)
        
        baseline_layout.addLayout(baseline_header)
        baseline_layout.addLayout(baseline_window_layout)
        
        # 1.4 添加峰值按钮
        self.add_spike_button = QPushButton("Add Selected as Peak")
        self.add_spike_button.setEnabled(False)
        self.add_spike_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px;")
        
        # 1.5 添加到选择控件分组布局
        selection_layout.addLayout(mode_layout)
        selection_layout.addLayout(amp_layout)
        selection_layout.addLayout(baseline_layout)
        selection_layout.addWidget(self.add_spike_button)
        
        # 2. 峰值列表分组
        peak_list_group = QGroupBox("Manual Peaks")
        peak_list_layout = QVBoxLayout(peak_list_group)
        
        # 2.1 峰值操作按钮
        peaks_btn_layout = QHBoxLayout()
        self.clear_peaks_btn = QPushButton("Clear All")
        self.clear_peaks_btn.setStyleSheet("color: red;")
        self.export_peaks_btn = QPushButton("Export Peaks")
        self.export_peaks_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        peaks_btn_layout.addWidget(self.clear_peaks_btn)
        peaks_btn_layout.addWidget(self.export_peaks_btn)
        
        # 2.2 峰值计数标签
        self.peak_count_label = QLabel("No manual peaks")
        
        # 2.3 添加到峰值列表分组布局
        peak_list_layout.addLayout(peaks_btn_layout)
        peak_list_layout.addWidget(self.peak_count_label)
        
        # 3. 分区导航分组
        navigation_group = QGroupBox("Navigation")
        navigation_layout = QVBoxLayout(navigation_group)
        
        # 滑块控制组
        slider_control_group = QGroupBox("Slider Control")
        slider_layout = QVBoxLayout(slider_control_group)
        
        # 添加滑块窗口大小控制
        window_size_layout = QHBoxLayout()
        window_size_layout.addWidget(QLabel("Window Size (%):"))
        self.window_size_spin = QSpinBox()
        self.window_size_spin.setRange(1, 50)
        self.window_size_spin.setValue(10)     # 默认窗口大小为10%
        self.window_size_spin.setToolTip("Set the window size as percentage of total trace")
        window_size_layout.addWidget(self.window_size_spin)
        
        slider_layout.addLayout(window_size_layout)
        
        # 添加滑块步进控制
        step_size_layout = QHBoxLayout()
        step_size_layout.addWidget(QLabel("Step Size (%):"))
        self.step_size_spin = QSpinBox()
        self.step_size_spin.setRange(1, 20)
        self.step_size_spin.setValue(5)     # 默认步进为5%
        self.step_size_spin.setToolTip("Set step size for slider movement buttons")
        step_size_layout.addWidget(self.step_size_spin)
        
        slider_layout.addLayout(step_size_layout)
        
        # 添加滑块控制按钮
        slider_buttons_layout = QHBoxLayout()
        self.slider_left_btn = QPushButton("← Move Left")
        self.slider_right_btn = QPushButton("Move Right →")
        slider_buttons_layout.addWidget(self.slider_left_btn)
        slider_buttons_layout.addWidget(self.slider_right_btn)
        
        slider_layout.addLayout(slider_buttons_layout)
        
        # 状态标签
        self.slider_info_label = QLabel("Slider position: 50%")
        slider_layout.addWidget(self.slider_info_label)
        
        # 4. 状态标签
        self.selection_status_label = QLabel("No area selected")
        self.selection_status_label.setStyleSheet("font-style: italic; color: gray;")
        
        # 5. Spikes 列表组
        spikes_list_group = QGroupBox("Spikes List")
        spikes_list_layout = QVBoxLayout(spikes_list_group)
        
        # 5.1 创建表格控件显示spikes列表
        self.spikes_table = QTableWidget()
        self.spikes_table.setColumnCount(5)
        self.spikes_table.setHorizontalHeaderLabels(["ID", "Time (s)", "Amplitude (nA)", "Duration (ms)", "Actions"])
        self.spikes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.spikes_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.spikes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # 设置列宽
        header = self.spikes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 时间列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 振幅列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 持续时间列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 操作列
        
        # 5.2 添加排序功能
        self.spikes_table.setSortingEnabled(True)
        
        spikes_list_layout.addWidget(self.spikes_table)
        
        # 5.3 创建排序控件
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Sort by:"))
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["ID", "Time", "Amplitude", "Duration"])
        sort_layout.addWidget(self.sort_combo)
        
        self.sort_order_check = QCheckBox("Descending")
        sort_layout.addWidget(self.sort_order_check)
        
        sort_layout.addStretch(1)
        
        spikes_list_layout.addLayout(sort_layout)
        
        # 6. 添加所有分组和控件到左侧控制面板
        control_layout.addWidget(selection_group)
        control_layout.addWidget(peak_list_group)
        control_layout.addWidget(slider_control_group)  # 添加滑块控制组
        control_layout.addWidget(self.selection_status_label)
        control_layout.addWidget(spikes_list_group)
        
        # ==================== 右侧：绘图区域 ====================
        self.plot_container = QWidget()
        self.plot_container.setMinimumWidth(600)
        plot_layout = QVBoxLayout(self.plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        
        # ==================== 将左右区域添加到分割器 ====================
        main_splitter.addWidget(control_widget)
        main_splitter.addWidget(self.plot_container)
        
        # 设置分割器初始比例
        main_splitter.setSizes([350, 650])
        
        # 添加到主布局
        layout.addWidget(main_splitter)
    
    def set_plot_canvas(self, plot_canvas):
        """设置主绘图画布引用"""
        self.plot_canvas = plot_canvas
        
        # 保存对图形的引用
        if hasattr(plot_canvas, 'fig'):
            self.manual_fig = plot_canvas.fig
            print("Manual figure reference set")
        else:
            print("Warning: plot_canvas has no fig attribute")
        
        # 连接峰值数据更新信号
        if self.plot_canvas:
            try:
                # 先断开任何现有连接以避免重复连接
                try:
                    self.plot_canvas.peak_data_changed.disconnect(self.on_peak_data_changed)
                except Exception:
                    pass # 如果没有连接则忽略
                
                # 连接信号
                self.plot_canvas.peak_data_changed.connect(self.on_peak_data_changed)
            except Exception as e:
                print(f"Warning: Could not connect canvas signals: {e}")
        
        # 将画布添加到容器
        if hasattr(self, 'plot_container') and self.plot_canvas:
            # 清除现有内容
            layout = self.plot_container.layout()
            while layout and layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            
            # 添加画布和它的工具栏
            if hasattr(self.plot_canvas, 'toolbar') and self.plot_canvas.toolbar:
                layout.addWidget(self.plot_canvas.toolbar)
            layout.addWidget(self.plot_canvas)
        
        # 显式输出调试信息，确认图形引用
        print(f"plot_canvas: {plot_canvas}")
        print(f"manual_fig: {self.manual_fig if hasattr(self, 'manual_fig') else 'None'}")
        
        # 更新手动选择图表
        try:
            self.update_manual_plot()
        except Exception as e:
            print(f"Error updating manual plot: {e}")
            import traceback
            traceback.print_exc()
    
    def on_peak_data_changed(self, peak_id, peak_data):
        """处理峰值数据更新（由游标操作触发）"""
        # 更新手动选择图表上显示的峰值
        self.update_manual_plot()
    
    def update_manual_plot(self, preserve_selection=False, preserve_view=False, saved_view=None):
        """更新手动选择的绘图
        
        参数:
        preserve_selection: 是否保留当前选择的区域
        preserve_view: 是否保留当前视图范围
        saved_view: 预先保存的视图状态
        """
        if not hasattr(self, 'plot_canvas') or self.plot_canvas is None or self.plot_canvas.current_channel_data is None:
            return
        
        # 保存当前选择，以便后续恢复
        current_selection = self.manual_spike_selection if preserve_selection else None
        
        # 保存当前视图范围，如果未提供已保存的视图
        if preserve_view and saved_view is None and hasattr(self, 'spike_ax') and self.spike_ax is not None:
            saved_view = {
                'xlim': self.spike_ax.get_xlim(),
                'ylim': self.spike_ax.get_ylim()
            }
        
        # 确保必要的UI元素存在
        required_attributes = ['selection_status_label', 'slider_info_label']
        for attr in required_attributes:
            if not hasattr(self, attr):
                print(f"Warning: Missing UI element {attr}, creating placeholder")
                setattr(self, attr, QLabel(self))
        
        try:
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 清除原有图形
            self.manual_fig = self.plot_canvas.fig  # 确保使用正确的引用
            self.manual_fig.clear()
            
            # 创建子图
            grid = self.manual_fig.add_gridspec(3, 1, height_ratios=[2, 2, 1])
            axes = [self.manual_fig.add_subplot(grid[i]) for i in range(3)]
            
            # 保存关键轴的引用
            self.trace_ax = axes[0]     # 主轨迹视图 (带滑块)
            self.zoomed_ax = axes[1]    # 放大视图 (用于选择spike)
            self.spike_ax = axes[2]     # 单峰值视图 (用于最终选择)
            
            # 子图样式设置
            for ax in axes:
                ax.grid(True, linestyle='--', alpha=0.7)
                ax.set_xlabel("Time (s)", fontsize=9)
                ax.set_ylabel("Current (nA)", fontsize=9)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
            
            # 第一个子图主轴标题 - 显示滑块位置
            self.trace_ax.set_title(f"Full Trace with Slider (Position: {self.slider_pos:.1%})", 
                                fontsize=10, fontweight='bold')
            
            # 绘制整个轨迹
            self.trace_ax.plot(time_axis, data)
            
            # 绘制已标记的手动峰值
            for spike in self.manual_spikes:
                if 'index' in spike:
                    peak_idx = spike['index']
                    # 检查是否是最近添加的峰值，如果是则使用不同颜色高亮显示
                    if hasattr(self, 'last_added_peak_id') and spike.get('id') == self.last_added_peak_id:
                        self.trace_ax.plot(time_axis[peak_idx], data[peak_idx], 
                                        'ro', markersize=8, alpha=0.7)
                    else:
                        self.trace_ax.plot(time_axis[peak_idx], data[peak_idx], 
                                        'go', markersize=8, alpha=0.7)
            
            # 计算滑块窗口大小
            window_size = self.window_size_spin.value() / 100.0  # 将百分比转换为小数
            
            # 计算滑块控制的数据窗口范围
            total_time = time_axis[-1] - time_axis[0]
            window_width = total_time * window_size
            
            # 计算滑块位置对应的时间范围
            max_slider_pos = 1.0 - window_size  # 滑块最大位置
            adjusted_slider_pos = min(self.slider_pos, max_slider_pos)  # 确保不超出范围
            
            window_start_time = time_axis[0] + adjusted_slider_pos * total_time
            window_end_time = window_start_time + window_width
            
            # 确保时间范围在有效范围内
            window_start_time = max(time_axis[0], min(window_start_time, time_axis[-1] - window_width))
            window_end_time = min(time_axis[-1], window_start_time + window_width)
            
            # 找到对应的索引范围
            start_idx = np.abs(time_axis - window_start_time).argmin()
            end_idx = np.abs(time_axis - window_end_time).argmin()
            
            # 在trace_ax中高亮显示当前窗口
            self.trace_ax.axvspan(window_start_time, window_end_time, alpha=0.2, color='green')
            
            # 创建并添加滑块
            rect = self.manual_fig.add_axes([0.15, 0.93, 0.7, 0.02])  # 位置和大小
            self.slider = Slider(
                ax=rect,
                label='Position',
                valmin=0,
                valmax=max_slider_pos,
                valinit=adjusted_slider_pos,
                valstep=0.01
            )
            
            # 连接滑块值变化事件
            self.slider.on_changed(self.on_slider_changed)
            
            # 绘制放大视图 (滑块选择的区域)
            self.zoomed_ax.plot(time_axis[start_idx:end_idx+1], data[start_idx:end_idx+1])
            
            # 在zoomed_ax中标记当前窗口中的峰值
            for spike in self.manual_spikes:
                if 'index' in spike:
                    peak_idx = spike['index']
                    peak_time = spike.get('time', time_axis[peak_idx])
                    
                    # 检查峰值是否在当前窗口中
                    if window_start_time <= peak_time <= window_end_time:
                        # 检查是否是最近添加的峰值，如果是则使用不同颜色高亮显示
                        if hasattr(self, 'last_added_peak_id') and spike.get('id') == self.last_added_peak_id:
                            self.zoomed_ax.plot(time_axis[peak_idx], data[peak_idx], 
                                            'ro', markersize=8, alpha=0.7)
                        else:
                            self.zoomed_ax.plot(time_axis[peak_idx], data[peak_idx], 
                                            'go', markersize=8, alpha=0.7)
            
            self.zoomed_ax.set_title(f"Zoomed View - Select Peak (Window: {window_start_time:.2f}s - {window_end_time:.2f}s)", 
                            fontsize=10, fontweight='bold')
            
            # 第三个子图 - 单个峰值视图
            self.spike_ax.set_title("Selected Peak - Use Span to Refine Selection", 
                            fontsize=10, fontweight='bold')
            
            # 如果有选中的峰值，则在spike_ax中显示
            if hasattr(self, 'current_manual_spike_data') and self.current_manual_spike_data:
                peak_idx = self.current_manual_spike_data.get('index', 0)
                if peak_idx is not None and peak_idx < len(time_axis) and peak_idx < len(data):
                    # ===== 修改这部分代码以保持显示一致性 =====
                    # 使用用户选择的完整区域而不是只显示峰值周围的一小段
                    start_time = self.current_manual_spike_data.get('start_time')
                    end_time = self.current_manual_spike_data.get('end_time')
                    
                    if start_time is not None and end_time is not None:
                        # 使用用户选择的区域
                        display_start_idx = np.abs(time_axis - start_time).argmin()
                        display_end_idx = np.abs(time_axis - end_time).argmin()
                    else:
                        # 如果没有用户选择的区域，就用默认的峰值周围区域
                        display_width = window_width * 0.2
                        peak_time = self.current_manual_spike_data.get('time', time_axis[peak_idx])
                        display_start = max(time_axis[0], peak_time - display_width/2)
                        display_end = min(time_axis[-1], peak_time + display_width/2)
                        display_start_idx = np.abs(time_axis - display_start).argmin()
                        display_end_idx = np.abs(time_axis - display_end).argmin()
                    
                    # 绘制选中区域的数据
                    self.spike_ax.plot(time_axis[display_start_idx:display_end_idx+1], 
                                    data[display_start_idx:display_end_idx+1])
                    
                    # 标记峰值位置
                    self.spike_ax.plot(time_axis[peak_idx], data[peak_idx], 'go', ms=8)
                    
                    # 显示当前选择的区域
                    if start_time is not None and end_time is not None:
                        self.spike_ax.axvspan(start_time, end_time, alpha=0.2, color='blue')
                        # 设置x轴范围为用户选择的区域
                        self.spike_ax.set_xlim(start_time, end_time)
                    
                    # 更新标题显示峰值信息
                    amplitude = self.current_manual_spike_data.get('amplitude', 0)
                    duration_ms = self.current_manual_spike_data.get('duration', 0) * 1000
                    self.spike_ax.set_title(
                        f"Selected Peak at {time_axis[peak_idx]:.4f}s, Amp={amplitude:.2f}nA, Dur={duration_ms:.2f}ms",
                        fontsize=10, fontweight='bold'
                    )
            
            # 调整布局
            self.manual_fig.tight_layout()
            
            # 设置选择工具
            self.enable_manual_selection_mode()
            
            # 如果需要，恢复之前保存的视图范围
            if preserve_view and saved_view is not None and hasattr(self, 'spike_ax') and self.spike_ax is not None:
                self.spike_ax.set_xlim(saved_view['xlim'])
                self.spike_ax.set_ylim(saved_view['ylim'])
            
            # 重绘
            self.plot_canvas.draw()
            
            # 恢复之前的选择
            if preserve_selection and current_selection is not None:
                self.manual_spike_selection = current_selection
                
        except Exception as e:
            print(f"Error in update_manual_plot: {e}")
            import traceback
            traceback.print_exc()
    
    def on_slider_changed(self, val):
        """处理滑块值变化"""
        self.slider_pos = val
        self.slider_info_label.setText(f"Slider position: {val:.1%}")
        self.update_manual_plot(preserve_selection=True)
    
    def move_slider_left(self):
        """向左移动滑块"""
        step_size = self.step_size_spin.value() / 100.0  # 将百分比转换为小数
        new_pos = max(0, self.slider_pos - step_size)
        self.slider_pos = new_pos
        
        # 更新滑块界面值 (如果存在)
        if hasattr(self, 'slider') and self.slider:
            self.slider.set_val(new_pos)
        else:
            # 如果滑块不存在，直接更新绘图
            self.slider_info_label.setText(f"Slider position: {new_pos:.1%}")
            self.update_manual_plot(preserve_selection=True)
    
    def move_slider_right(self):
        """向右移动滑块"""
        step_size = self.step_size_spin.value() / 100.0  # 将百分比转换为小数
        window_size = self.window_size_spin.value() / 100.0  # 将百分比转换为小数
        max_pos = max(0, 1.0 - window_size)  # 确保窗口不超出数据范围
        
        new_pos = min(max_pos, self.slider_pos + step_size)
        self.slider_pos = new_pos
        
        # 更新滑块界面值 (如果存在)
        if hasattr(self, 'slider') and self.slider:
            self.slider.set_val(new_pos)
        else:
            # 如果滑块不存在，直接更新绘图
            self.slider_info_label.setText(f"Slider position: {new_pos:.1%}")
            self.update_manual_plot(preserve_selection=True)
    
    # 修复后的enable_manual_selection_mode方法
    def enable_manual_selection_mode(self):
        """根据选择模式启用相应的选择工具"""
        # 清除现有的SpanSelector
        if self.span_selector is not None:
            self.span_selector.disconnect_events()
            self.span_selector = None
            
        if self.final_span_selector is not None:
            self.final_span_selector.disconnect_events()
            self.final_span_selector = None
        
        # 获取当前选择模式
        mode = self.selection_mode_combo.currentText()
        
        # 始终在第三个子图 (spike_ax) 上添加最终选择的span selector
        if hasattr(self, 'spike_ax') and self.spike_ax is not None:
            self.final_span_selector = SpanSelector(
                self.spike_ax,
                self.on_final_span_select,
                'horizontal',
                useblit=True,
                props=dict(alpha=0.3, facecolor='red'),
                interactive=True,
                drag_from_anywhere=True
            )
            
            # 添加双击事件监听 - 安全地断开可能的旧连接
            try:
                # 只有在确定canvas.manager存在并且有key_press_handler_id属性时才尝试断开
                if (hasattr(self.spike_ax.figure, 'canvas') and 
                    hasattr(self.spike_ax.figure.canvas, 'manager') and 
                    self.spike_ax.figure.canvas.manager is not None and
                    hasattr(self.spike_ax.figure.canvas.manager, 'key_press_handler_id')):
                    self.spike_ax.figure.canvas.mpl_disconnect(self.spike_ax.figure.canvas.manager.key_press_handler_id)
            except Exception as e:
                # 安全地处理任何断开连接时可能出现的错误
                print(f"注意：断开键盘处理程序时出错: {e}")
                
            # 断开之前可能存在的连接（防止重复连接）
            if hasattr(self, 'dblclick_cid') and self.dblclick_cid is not None:
                try:
                    self.spike_ax.figure.canvas.mpl_disconnect(self.dblclick_cid)
                except Exception:
                    pass
                
            if hasattr(self, 'key_cid') and self.key_cid is not None:
                try:
                    self.spike_ax.figure.canvas.mpl_disconnect(self.key_cid)
                except Exception:
                    pass
                    
            # 添加新的连接
            self.dblclick_cid = self.spike_ax.figure.canvas.mpl_connect('button_press_event', self.on_spike_ax_click)
            self.key_cid = self.spike_ax.figure.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # 根据选择模式，在第二个子图 (zoomed_ax) 上添加不同的选择工具
        if mode == "Span Select" and hasattr(self, 'zoomed_ax') and self.zoomed_ax is not None:
            # 在第二个子图上创建跨度选择器
            self.span_selector = SpanSelector(
                self.zoomed_ax,
                self.on_manual_span_select,
                'horizontal',
                useblit=True,
                props=dict(alpha=0.3, facecolor='blue'),
                interactive=True,
                drag_from_anywhere=True
            )
        elif mode == "Click Peak" and hasattr(self, 'zoomed_ax') and self.zoomed_ax is not None:
            # 在第二个子图上启用点击选择
            self.zoomed_ax.figure.canvas.mpl_connect(
                'button_press_event', self.on_spike_click)
            
    def on_spike_ax_click(self, event):
        """处理第三个子图上的点击事件 - 双击时添加spike"""
        if event.inaxes != self.spike_ax:
            return
            
        # 检查是否是双击（matplotlib的事件中双击被视为两次快速的单击）
        # 所以我们需要跟踪点击时间和位置
        current_time = time.time()
        
        # 初始化上次点击的时间和位置（如果还没有）
        if not hasattr(self, 'last_click_time'):
            self.last_click_time = 0
        if not hasattr(self, 'last_click_pos'):
            self.last_click_pos = (0, 0)
        
        # 计算时间差和位置差
        time_diff = current_time - self.last_click_time
        pos_diff = ((event.xdata - self.last_click_pos[0])**2 + 
                    (event.ydata - self.last_click_pos[1])**2)**0.5
        
        # 如果时间差小于0.5秒且位置接近，则视为双击
        if time_diff < 0.5 and pos_diff < 0.1:  # 位置差阈值可以根据需要调整
            # 执行添加峰值的操作
            if hasattr(self, 'current_manual_spike_data') and self.current_manual_spike_data:
                self.add_manual_peak()
                # 显示临时消息提示用户已添加
                self.show_temp_message("Spike added by double-click!")
        
        # 更新上次点击的时间和位置
        self.last_click_time = current_time
        self.last_click_pos = (event.xdata, event.ydata)

    def on_key_press(self, event):
        """处理键盘事件 - 按下Enter键时添加spike"""
        # 检查是否按下了Enter键
        if event.key == 'enter':
            # 检查是否有当前选择的峰值数据
            if hasattr(self, 'current_manual_spike_data') and self.current_manual_spike_data:
                self.add_manual_peak()
                # 显示临时消息提示用户已添加
                self.show_temp_message("Spike added with Enter key!")

    def show_temp_message(self, message, duration=2.0):
        """在图表上显示临时消息"""
        if not hasattr(self, 'spike_ax') or self.spike_ax is None:
            return
            
        # 保存当前视图范围
        xlim = self.spike_ax.get_xlim()
        ylim = self.spike_ax.get_ylim()
        
        # 计算消息位置（图表中心偏上）
        x_pos = sum(xlim) / 2
        y_pos = ylim[0] + (ylim[1] - ylim[0]) * 0.9
        
        # 创建文本对象
        text = self.spike_ax.text(
            x_pos, y_pos, message,
            horizontalalignment='center',
            verticalalignment='center',
            fontsize=12,
            color='white',
            bbox=dict(boxstyle="round,pad=0.5", fc="green", alpha=0.7)
        )
        
        # 重绘图表显示消息
        if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
            self.plot_canvas.draw_idle()
        
        # 设置定时器在指定时间后隐藏消息而不是移除
        def hide_message():
            # 使用 set_visible 代替 remove 避免 NotImplementedError
            text.set_visible(False)
            if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                self.plot_canvas.draw_idle()
        
        # 使用Qt定时器
        timer = QTimer(self)
        timer.timeout.connect(hide_message)
        timer.setSingleShot(True)
        timer.start(int(duration * 1000))  # 转换为毫秒
    
    def on_selection_mode_changed(self, index):
        """处理选择模式变化"""
        self.enable_manual_selection_mode()
    
    def on_manual_span_select(self, xmin, xmax):
        """处理第二个子图中的区域选择事件"""
        try:
            # 保存当前的zoomed_ax视图状态
            if hasattr(self, 'zoomed_ax') and self.zoomed_ax is not None:
                saved_xlim = self.zoomed_ax.get_xlim()
                saved_ylim = self.zoomed_ax.get_ylim()
            
            # 计算选择区域的持续时间
            duration_ms = (xmax - xmin) * 1000
            
            # 更新状态标签
            self.selection_status_label.setText(
                f"Selected area: {xmin:.4f}s - {xmax:.4f}s (Duration: {duration_ms:.2f} ms)")
            
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 在时间轴中找到选择的起始和结束索引
            start_idx = np.abs(time_axis - xmin).argmin()
            end_idx = np.abs(time_axis - xmax).argmin()
            
            # 获取选中区域的数据
            selection_data = data[start_idx:end_idx+1]
            
            # 计算基线校正值
            baseline_value = 0
            if self.baseline_correction_check.isChecked():
                baseline_window = self.baseline_window_spin.value()
                baseline_start = max(0, start_idx - baseline_window)
                baseline_data = data[baseline_start:start_idx]
                
                if len(baseline_data) > 0:
                    baseline_value = np.mean(baseline_data)
            
            # 根据振幅模式计算峰值振幅
            amp_mode = self.amplitude_mode_combo.currentText()
            
            if amp_mode == "Maximum":
                # 找到选区内的最大绝对值
                abs_max_idx = np.argmax(np.abs(selection_data))
                peak_idx = start_idx + abs_max_idx
                amplitude = selection_data[abs_max_idx] - baseline_value
            elif amp_mode == "Average":
                # 使用平均值
                amplitude = np.mean(selection_data) - baseline_value
                peak_idx = start_idx + len(selection_data) // 2
            else:  # 中值
                amplitude = np.median(selection_data) - baseline_value
                peak_idx = start_idx + len(selection_data) // 2
            
            # 保存当前峰值数据
            self.current_manual_spike_data = {
                'index': peak_idx,
                'time': time_axis[peak_idx],
                'amplitude': amplitude,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'start_time': xmin,
                'end_time': xmax,
                'duration': xmax - xmin,
                'manual': True
            }
            
            # 在zoomed_ax中高亮显示选择的区域
            for collection in self.zoomed_ax.collections:
                if hasattr(collection, '_is_selection'):
                    collection.remove()
            
            span = self.zoomed_ax.axvspan(xmin, xmax, alpha=0.3, color='blue')
            span._is_selection = True
            
            # 标记峰值位置
            for line in self.zoomed_ax.lines:
                if hasattr(line, '_is_peak_marker'):
                    line.remove()
            
            marker = self.zoomed_ax.plot(time_axis[peak_idx], data[peak_idx], 'ro', ms=8)[0]
            marker._is_peak_marker = True
            
            # 更新第三个子图，显示选中的峰值
            self.update_peak_display()
            
            # 启用添加按钮
            self.add_spike_button.setEnabled(True)
            
            # 恢复zoomed_ax的视图范围
            if hasattr(self, 'zoomed_ax') and self.zoomed_ax is not None:
                self.zoomed_ax.set_xlim(saved_xlim)
                self.zoomed_ax.set_ylim(saved_ylim)
                
                # 仅重绘必要的部分
                if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                    self.plot_canvas.draw_idle()
            
        except Exception as e:
            import traceback
            print(f"Error in manual span selection: {e}")
            print(traceback.format_exc())

    def on_spike_click(self, event):
        """处理第二个子图中的点击事件来选择峰值"""
        # 检查点击是否在zoomed_ax上
        if event.inaxes != self.zoomed_ax:
            return
        
        try:
            # 保存当前视图范围
            saved_xlim = self.zoomed_ax.get_xlim()
            saved_ylim = self.zoomed_ax.get_ylim()
            
            # 获取点击位置
            x_click = event.xdata
            
            # 向点击位置左右扩展一定范围作为选择区域
            view_width = saved_xlim[1] - saved_xlim[0]
            selection_width = view_width * 0.05  # 取当前视图宽度的5%作为选择宽度
            
            xmin = x_click - selection_width/2
            xmax = x_click + selection_width/2
            
            # 处理与span选择相同的逻辑
            self.on_manual_span_select(xmin, xmax)
            
        except Exception as e:
            import traceback
            print(f"Error in spike click selection: {e}")
            print(traceback.format_exc())
    
    def on_final_span_select(self, xmin, xmax):
        """处理第三个子图中的最终span选择"""
        try:
            if not hasattr(self, 'current_manual_spike_data') or not self.current_manual_spike_data:
                return
                
            # 保存当前视图范围
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                saved_xlim = self.spike_ax.get_xlim()
                saved_ylim = self.spike_ax.get_ylim()
            
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 在时间轴中找到选择的起始和结束索引
            start_idx = np.abs(time_axis - xmin).argmin()
            end_idx = np.abs(time_axis - xmax).argmin()
            
            # 获取选中区域的数据
            selection_data = data[start_idx:end_idx+1]
            
            # 计算基线校正值
            baseline_value = 0
            if self.baseline_correction_check.isChecked():
                baseline_window = self.baseline_window_spin.value()
                baseline_start = max(0, start_idx - baseline_window)
                baseline_data = data[baseline_start:start_idx]
                
                if len(baseline_data) > 0:
                    baseline_value = np.mean(baseline_data)
            
            # 根据振幅模式计算峰值振幅
            amp_mode = self.amplitude_mode_combo.currentText()
            
            if amp_mode == "Maximum":
                # 找到选区内的最大绝对值
                if len(selection_data) > 0:
                    abs_max_idx = np.argmax(np.abs(selection_data))
                    peak_idx = start_idx + abs_max_idx
                    amplitude = selection_data[abs_max_idx] - baseline_value
                else:
                    # 使用原始峰值数据
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
            elif amp_mode == "Average":
                # 使用平均值
                if len(selection_data) > 0:
                    amplitude = np.mean(selection_data) - baseline_value
                    peak_idx = start_idx + len(selection_data) // 2
                else:
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
            else:  # 中值
                if len(selection_data) > 0:
                    amplitude = np.median(selection_data) - baseline_value
                    peak_idx = start_idx + len(selection_data) // 2
                else:
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
            
            # 计算选择区域的持续时间
            duration_ms = (xmax - xmin) * 1000
            
            # 更新状态标签
            self.selection_status_label.setText(
                f"Final selection: {xmin:.4f}s - {xmax:.4f}s (Duration: {duration_ms:.2f} ms)")
            
            # 更新当前峰值数据的细节
            self.current_manual_spike_data.update({
                'start_idx': start_idx,
                'end_idx': end_idx,
                'start_time': xmin,
                'end_time': xmax,
                'duration': xmax - xmin,
                'index': peak_idx,
                'time': time_axis[peak_idx],
                'amplitude': amplitude
            })
            
            # 在第三个子图中显示最终选择的区域
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                # 清除之前的区域标记
                for collection in self.spike_ax.collections:
                    if hasattr(collection, '_is_final_selection'):
                        collection.remove()
                
                # 添加新的区域标记
                span = self.spike_ax.axvspan(xmin, xmax, alpha=0.3, color='red')
                span._is_final_selection = True
                
                # 更新标题显示选择信息
                self.spike_ax.set_title(
                    f"Final Selection: {xmin:.4f}s - {xmax:.4f}s, Amp={amplitude:.2f}nA",
                    fontsize=10, fontweight='bold'
                )
                
                # 恢复视图范围
                self.spike_ax.set_xlim(saved_xlim)
                self.spike_ax.set_ylim(saved_ylim)
                
                # 仅重绘必要的部分
                if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                    self.plot_canvas.draw_idle()
            
            # 启用添加按钮
            self.add_spike_button.setEnabled(True)
            
        except Exception as e:
            import traceback
            print(f"Error in final span selection: {e}")
            print(traceback.format_exc())
    
    def update_peak_display(self):
        """更新第三个子图中选中峰值的显示"""
        try:
            if not hasattr(self, 'current_manual_spike_data') or not self.current_manual_spike_data:
                return
                
            if not hasattr(self, 'spike_ax') or self.spike_ax is None:
                return
                
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 获取用户在subplot2中选择的区域
            start_time = self.current_manual_spike_data.get('start_time')
            end_time = self.current_manual_spike_data.get('end_time')
            start_idx = self.current_manual_spike_data.get('start_idx')
            end_idx = self.current_manual_spike_data.get('end_idx')
            peak_idx = self.current_manual_spike_data.get('index')
            peak_time = self.current_manual_spike_data.get('time')
            amplitude = self.current_manual_spike_data.get('amplitude')
            
            if start_time is None or end_time is None or start_idx is None or end_idx is None:
                return
            
            # 清除现有内容
            self.spike_ax.clear()
            
            # 设置网格和轴标签
            self.spike_ax.grid(True, linestyle='--', alpha=0.7)
            self.spike_ax.set_xlabel("Time (s)", fontsize=9)
            self.spike_ax.set_ylabel("Current (nA)", fontsize=9)
            
            # 只绘制精确选择的区域数据
            selection_data = data[start_idx:end_idx+1]
            selection_time = time_axis[start_idx:end_idx+1]
            
            # 绘制所选区域的数据
            self.spike_ax.plot(selection_time, selection_data)
            
            # 标记峰值位置
            self.spike_ax.plot(peak_time, data[peak_idx], 'go', ms=8)
            
            # 更新标题显示峰值信息
            duration_ms = (end_time - start_time) * 1000
            self.spike_ax.set_title(
                f"Selected Peak: {start_time:.4f}s - {end_time:.4f}s, Amp={amplitude:.2f}nA, Dur={duration_ms:.2f}ms",
                fontsize=10, fontweight='bold'
            )
            
            # 设置精确的显示范围
            self.spike_ax.set_xlim(start_time, end_time)
            
            # 重绘
            if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                self.plot_canvas.draw()
                
        except Exception as e:
            import traceback
            print(f"Error updating peak display: {e}")
            print(traceback.format_exc())
    
    def add_manual_peak(self):
        """添加手动标记的峰值"""
        if not hasattr(self, 'current_manual_spike_data') or self.current_manual_spike_data is None:
            QMessageBox.warning(self, "Warning", "No peak data to add")
            return
        
        try:
            # 保存当前的视图状态
            saved_view = None
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                saved_view = {
                    'xlim': self.spike_ax.get_xlim(),
                    'ylim': self.spike_ax.get_ylim()
                }
                
            # 给峰值添加ID
            self.manual_spike_count += 1
            peak_data = self.current_manual_spike_data.copy()
            peak_data['id'] = self.manual_spike_count
            
            # 添加到峰值列表
            self.manual_spikes.append(peak_data)
            
            # 更新计数标签
            self.peak_count_label.setText(f"Manual peaks: {len(self.manual_spikes)}")
            
            # 更新spikes表格
            self.update_spikes_table()
            
            # 重置状态
            self.selection_status_label.setText(f"Added spike #{self.manual_spike_count}")
            
            # 标记最后添加的峰值ID，用于高亮显示
            self.last_added_peak_id = self.manual_spike_count
            
            # 更新绘图
            self.update_manual_plot(preserve_view=True, saved_view=saved_view)
            
            # 发送峰值添加信号
            self.peak_added.emit(peak_data)
            
        except Exception as e:
            import traceback
            print(f"Error adding manual peak: {e}")
            print(traceback.format_exc())
    
    def clear_manual_peaks(self):
        """清除所有手动标记的峰值"""
        if not self.manual_spikes:
            return
            
        reply = QMessageBox.question(
            self, 
            "Confirm Clear", 
            f"Are you sure you want to clear all {len(self.manual_spikes)} manual peaks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.manual_spikes = []
            self.manual_spike_count = 0
            self.peak_count_label.setText("No manual peaks")
            self.selection_status_label.setText("All manual peaks cleared")
            
            # 更新绘图
            self.update_manual_plot()
            
            # 更新表格
            self.update_spikes_table()
    
    def export_manual_peaks(self):
        """将峰值数据导出到文件"""
        if not self.manual_spikes:
            QMessageBox.warning(self, "Warning", "No peaks to export")
            return
            
        # 让用户选择保存位置和格式
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Peaks Data",
            "",
            "CSV Files (*.csv);;Excel Files (*.xlsx);;Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # 根据文件扩展名决定导出格式
            _, ext = os.path.splitext(file_path)
            
            # 准备导出数据
            headers = ['ID', 'Time (s)', 'Amplitude (nA)', 'Duration (ms)', 'Start Time', 'End Time']
            data = []
            
            for spike in self.manual_spikes:
                row = [
                    spike.get('id', ''),
                    spike.get('time', 0),
                    spike.get('amplitude', 0),
                    spike.get('duration', 0) * 1000,  # 转为毫秒
                    spike.get('start_time', 0),
                    spike.get('end_time', 0)
                ]
                data.append(row)
                
            if ext.lower() == '.csv':
                # 导出为CSV
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(data)
                    
            elif ext.lower() == '.xlsx':
                # 导出为Excel
                try:
                    import pandas as pd
                    df = pd.DataFrame(data, columns=headers)
                    df.to_excel(file_path, index=False)
                except ImportError:
                    QMessageBox.warning(self, "Warning", "Excel export requires pandas. Using CSV instead.")
                    with open(file_path + '.csv', 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                        writer.writerows(data)
                        
            else:
                # 导出为文本文件
                with open(file_path, 'w') as f:
                    f.write('\t'.join(headers) + '\n')
                    for row in data:
                        f.write('\t'.join(map(str, row)) + '\n')
                        
            QMessageBox.information(
                self,
                "Export Successful",
                f"Exported {len(data)} peaks to {file_path}"
            )
            
            # 更新状态
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage(
                    f"Exported {len(data)} peaks to file: {os.path.basename(file_path)}"
                )
            
        except Exception as e:
            import traceback
            print(f"Error exporting peaks to file: {e}")
            print(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export peaks: {str(e)}"
            )

    def update_spikes_table(self):
        """更新spikes表格显示"""
        try:
            # 断开排序信号以避免刷新表格时触发排序
            self.spikes_table.setSortingEnabled(False)
            
            # 获取当前行数
            current_rows = self.spikes_table.rowCount()
            required_rows = len(self.manual_spikes)
            
            # 调整行数
            if current_rows < required_rows:
                # 添加行
                for i in range(current_rows, required_rows):
                    self.spikes_table.insertRow(i)
            elif current_rows > required_rows:
                # 删除多余行
                for i in range(current_rows - 1, required_rows - 1, -1):
                    self.spikes_table.removeRow(i)
            
            # 填充或更新表格数据
            for row, spike in enumerate(self.manual_spikes):
                # ID列
                id_item = QTableWidgetItem(str(spike.get('id', row + 1)))
                self.spikes_table.setItem(row, 0, id_item)
                
                # 时间列 (秒)
                time_item = QTableWidgetItem(f"{spike.get('time', 0):.4f}")
                self.spikes_table.setItem(row, 1, time_item)
                
                # 振幅列 (nA)
                amp_item = QTableWidgetItem(f"{spike.get('amplitude', 0):.4f}")
                self.spikes_table.setItem(row, 2, amp_item)
                
                # 持续时间列 (转为毫秒)
                duration_ms = spike.get('duration', 0) * 1000  # 秒转为毫秒
                duration_item = QTableWidgetItem(f"{duration_ms:.2f}")
                self.spikes_table.setItem(row, 3, duration_item)
                
                # 操作列 (按钮)
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(2, 2, 2, 2)
                action_layout.setSpacing(2)
                
                # 编辑按钮 - 增加宽度以修复文本显示不全问题
                edit_btn = QPushButton("Edit")
                edit_btn.setFixedSize(60, 22)  # 增加宽度从50到60
                edit_btn.setStyleSheet("background-color: #2196F3; color: white;")
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_spike(r))
                
                # 删除按钮 - 增加宽度以修复文本显示不全问题
                delete_btn = QPushButton("Del")
                delete_btn.setFixedSize(50, 22)  # 增加宽度从40到50
                delete_btn.setStyleSheet("background-color: #F44336; color: white;")
                delete_btn.clicked.connect(lambda checked, r=row: self.delete_spike(r))
                
                # 跳转按钮
                goto_btn = QPushButton("→")
                goto_btn.setFixedSize(30, 22)  # 保持不变，因为只是一个箭头
                goto_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                goto_btn.clicked.connect(lambda checked, r=row: self.goto_spike(r))
                
                action_layout.addWidget(edit_btn)
                action_layout.addWidget(delete_btn)
                action_layout.addWidget(goto_btn)
                action_layout.addStretch()
                
                self.spikes_table.setCellWidget(row, 4, action_widget)
                
            # 恢复排序功能
            self.spikes_table.setSortingEnabled(True)
            
            # 如果表格中有数据，选择第一行
            if required_rows > 0:
                self.spikes_table.selectRow(0)
                
        except Exception as e:
            import traceback
            print(f"Error updating spikes table: {e}")
            print(traceback.format_exc())
    
    def edit_spike(self, row):
        """编辑指定行的spike"""
        try:
            spike_data = self.manual_spikes[row]
            
            # 创建并显示编辑对话框
            dialog = SpikeEditDialog(spike_data, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 获取编辑后的数据
                edited_data = dialog.get_edited_data()
                
                # 更新峰值数据
                self.manual_spikes[row] = edited_data
                
                # 更新表格和绘图
                self.update_spikes_table()
                self.update_manual_plot()
                
                # 发送峰值更新信号
                self.peak_updated.emit(spike_data.get('id', row + 1), edited_data)
                
        except Exception as e:
            import traceback
            print(f"Error editing spike: {e}")
            print(traceback.format_exc())
    
    def delete_spike(self, row):
        """删除指定行的spike"""
        try:
            spike_data = self.manual_spikes[row]
            spike_id = spike_data.get('id', row + 1)
            
            # 弹出确认对话框 - 修改为英文
            reply = QMessageBox.question(
                self, 
                "Confirm Delete", 
                f"Are you sure you want to delete spike #{spike_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 记录ID用于发送信号
                deleted_id = spike_data.get('id', row + 1)
                
                # 从列表中移除
                self.manual_spikes.pop(row)
                
                # 更新表格和绘图
                self.update_spikes_table()
                self.update_manual_plot()
                
                # 更新计数标签
                self.peak_count_label.setText(f"Manual peaks: {len(self.manual_spikes)}")
                
                # 发送峰值删除信号
                self.peak_deleted.emit(deleted_id)
                
        except Exception as e:
            import traceback
            print(f"Error deleting spike: {e}")
            print(traceback.format_exc())
    
    def goto_spike(self, row):
        """导航到指定行的spike"""
        try:
            spike_data = self.manual_spikes[row]
            
            # 获取spike的时间
            peak_time = spike_data.get('time', 0)
            
            # 获取数据长度
            if not hasattr(self, 'plot_canvas') or self.plot_canvas is None:
                return
                
            time_axis = self.plot_canvas.time_axis
            
            if time_axis is None:
                return
            
            # 计算新的滑块位置以使峰值在窗口中居中
            window_size = self.window_size_spin.value() / 100.0  # 将百分比转换为小数
            total_time = time_axis[-1] - time_axis[0]
            
            # 确保峰值在窗口的中心
            new_slider_pos = (peak_time - time_axis[0]) / total_time - window_size / 2
            
            # 确保位置在有效范围内
            max_slider_pos = 1.0 - window_size
            self.slider_pos = max(0, min(new_slider_pos, max_slider_pos))
            
            # 更新滑块位置
            if hasattr(self, 'slider') and self.slider:
                self.slider.set_val(self.slider_pos)
            else:
                # 如果滑块不存在，直接更新信息和绘图
                self.slider_info_label.setText(f"Slider position: {self.slider_pos:.1%}")
                self.update_manual_plot()
            
            # 设置当前选中的峰值数据
            self.current_manual_spike_data = spike_data.copy()
            
            # 更新峰值显示
            self.update_peak_display()
            
            # 高亮显示该行
            self.spikes_table.selectRow(row)
            
            # 通知用户
            self.selection_status_label.setText(f"Navigated to spike #{spike_data.get('id', row + 1)}")
            
        except Exception as e:
            import traceback
            print(f"Error navigating to spike: {e}")
            print(traceback.format_exc())
    
    def apply_sort(self):
        """应用当前的排序设置"""
        sort_by = self.sort_combo.currentText()
        descending = self.sort_order_check.isChecked()
        
        # 根据选择的字段排序
        if sort_by == "ID":
            self.manual_spikes.sort(key=lambda x: x.get('id', 0), 
                                  reverse=descending)
        elif sort_by == "Time":
            self.manual_spikes.sort(key=lambda x: x.get('time', 0), 
                                  reverse=descending)
        elif sort_by == "Amplitude":
            self.manual_spikes.sort(key=lambda x: abs(x.get('amplitude', 0)), 
                                  reverse=descending)
        elif sort_by == "Duration":
            self.manual_spikes.sort(key=lambda x: x.get('duration', 0), 
                                  reverse=descending)
        
        # 更新表格显示
        self.update_spikes_table()
    
    def on_table_header_clicked(self, index):
        """处理表头点击事件，实现排序"""
        # 更新排序组合框
        if index == 0:
            self.sort_combo.setCurrentText("ID")
        elif index == 1:
            self.sort_combo.setCurrentText("Time")
        elif index == 2:
            self.sort_combo.setCurrentText("Amplitude")
        elif index == 3:
            self.sort_combo.setCurrentText("Duration")
        
        # 应用排序
        self.apply_sort()
    
    def on_table_selection_changed(self):
        """处理表格选择变化，高亮显示选中的spike"""
        selected_rows = self.spikes_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        
        # 确保行索引有效
        if row < 0 or row >= len(self.manual_spikes):
            return
            
        # 获取选中的spike数据
        spike_data = self.manual_spikes[row]
        
        # 在绘图上高亮显示该spike
        if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
            if self.trace_ax is not None and hasattr(self.plot_canvas, 'time_axis'):
                # 清除现有高亮标记
                for artist in self.trace_ax.get_children():
                    if hasattr(artist, '_is_highlight') and artist._is_highlight:
                        artist.remove()
                
                # 添加新高亮标记
                peak_idx = spike_data.get('index', 0)
                time_axis = self.plot_canvas.time_axis
                data = self.plot_canvas.current_channel_data
                
                if peak_idx < len(time_axis) and peak_idx < len(data):
                    highlight = self.trace_ax.plot(time_axis[peak_idx], data[peak_idx], 
                                                 'ro', markersize=10, alpha=0.7)[0]
                    highlight._is_highlight = True
                    
                    # 更新绘图
                    self.plot_canvas.draw()
                    
                    # 同时设置当前选中的峰值数据，以便在第三个子图中显示
                    self.current_manual_spike_data = spike_data.copy()
                    self.update_peak_display()

    def connect_signals(self):
        """连接信号"""
        # 添加峰值按钮
        if hasattr(self, 'add_spike_button'):
            self.add_spike_button.clicked.connect(self.add_manual_peak)
        
        # 峰值操作按钮
        if hasattr(self, 'clear_peaks_btn'):
            self.clear_peaks_btn.clicked.connect(self.clear_manual_peaks)
        if hasattr(self, 'export_peaks_btn'):
            self.export_peaks_btn.clicked.connect(self.export_manual_peaks)
        
        # 滑块控制按钮
        if hasattr(self, 'slider_left_btn'):
            self.slider_left_btn.clicked.connect(self.move_slider_left)
        if hasattr(self, 'slider_right_btn'):
            self.slider_right_btn.clicked.connect(self.move_slider_right)
        
        # 模式选择
        if hasattr(self, 'selection_mode_combo'):
            self.selection_mode_combo.currentIndexChanged.connect(self.on_selection_mode_changed)
        
        # 振幅模式和基线校正
        if hasattr(self, 'amplitude_mode_combo'):
            self.amplitude_mode_combo.currentIndexChanged.connect(lambda: self.update_peak_properties() if hasattr(self, 'current_manual_spike_data') else None)
        if hasattr(self, 'baseline_correction_check'):
            self.baseline_correction_check.stateChanged.connect(lambda: self.update_peak_properties() if hasattr(self, 'current_manual_spike_data') else None)
        if hasattr(self, 'baseline_window_spin'):
            self.baseline_window_spin.valueChanged.connect(lambda: self.update_peak_properties() if hasattr(self, 'current_manual_spike_data') else None)
        
        # 窗口大小设置
        if hasattr(self, 'window_size_spin'):
            self.window_size_spin.valueChanged.connect(lambda: self.update_manual_plot(preserve_selection=True))
        
        # 表格头部点击
        if hasattr(self, 'spikes_table'):
            self.spikes_table.horizontalHeader().sectionClicked.connect(self.on_table_header_clicked)
            
        # 排序控件
        if hasattr(self, 'sort_combo') and hasattr(self, 'sort_order_check'):
            self.sort_combo.currentIndexChanged.connect(self.apply_sort)
            self.sort_order_check.stateChanged.connect(self.apply_sort)
            
        # 表格行选择
        if hasattr(self, 'spikes_table'):
            self.spikes_table.itemSelectionChanged.connect(self.on_table_selection_changed)
    
    def update_peak_properties(self):
        """根据当前设置更新峰值属性"""
        if not hasattr(self, 'current_manual_spike_data') or not self.current_manual_spike_data:
            return
            
        # 更新峰值显示
        self.update_peak_display()


class SpikeEditDialog(QDialog):
    """用于编辑峰值参数的对话框"""
    
    def __init__(self, spike_data, parent=None):
        super(SpikeEditDialog, self).__init__(parent)
        self.spike_data = spike_data.copy()  # 创建副本避免直接修改
        self.setup_ui()
        
    def setup_ui(self):
        """设置对话框UI"""
        self.setWindowTitle("Edit Spike Parameters")  # 修改为英文标题
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        # 表单布局，用于编辑参数
        form_layout = QFormLayout()
        
        # 振幅编辑
        self.amplitude_spin = QDoubleSpinBox()
        self.amplitude_spin.setRange(-1000, 1000)
        self.amplitude_spin.setDecimals(4)
        self.amplitude_spin.setValue(self.spike_data.get('amplitude', 0))
        form_layout.addRow("Amplitude (nA):", self.amplitude_spin)  # 修改为英文标签
        
        # 持续时间编辑
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 1000)
        self.duration_spin.setDecimals(4)
        self.duration_spin.setValue(self.spike_data.get('duration', 0) * 1000)  # 转为毫秒
        form_layout.addRow("Duration (ms):", self.duration_spin)  # 修改为英文标签
        
        # 开始时间编辑
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setRange(0, 1000)
        self.start_time_spin.setDecimals(4)
        self.start_time_spin.setValue(self.spike_data.get('start_time', 0))
        form_layout.addRow("Start Time (s):", self.start_time_spin)  # 修改为英文标签
        
        # 结束时间编辑（只读，根据开始时间和持续时间自动计算）
        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setRange(0, 1000)
        self.end_time_spin.setDecimals(4)
        self.end_time_spin.setValue(self.spike_data.get('end_time', 0))
        self.end_time_spin.setReadOnly(True)
        form_layout.addRow("End Time (s):", self.end_time_spin)  # 修改为英文标签
        
        # 连接信号以更新结束时间
        self.start_time_spin.valueChanged.connect(self.update_end_time)
        self.duration_spin.valueChanged.connect(self.update_end_time)
        
        layout.addLayout(form_layout)
        
        # 添加确认和取消按钮
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")  # 修改为英文按钮文本
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("Cancel")  # 修改为英文按钮文本
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
    
    def update_end_time(self):
        """根据开始时间和持续时间更新结束时间"""
        start_time = self.start_time_spin.value()
        duration = self.duration_spin.value() / 1000  # 毫秒转为秒
        self.end_time_spin.setValue(start_time + duration)
    
    def get_edited_data(self):
        """获取编辑后的数据"""
        self.spike_data['amplitude'] = self.amplitude_spin.value()
        self.spike_data['duration'] = self.duration_spin.value() / 1000  # 毫秒转为秒
        self.spike_data['start_time'] = self.start_time_spin.value()
        self.spike_data['end_time'] = self.end_time_spin.value()
        
        return self.spike_data