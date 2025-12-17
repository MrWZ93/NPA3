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
                            QLineEdit, QDialogButtonBox,  # Added QLineEdit and QDialogButtonBox
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
        
        # 初始化pop-out窗口引用
        self.spikes_list_window = None
        
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
        
        # 1.6 初始化分组数据
        self.spike_groups = ["Default"]
        
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
        self.amplitude_mode_combo.addItems(["Maximum", "Minimum", "Average", "Median"])
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
        
        
        # 滑块控制组 - 改为更紧凑的垂直布局
        slider_control_group = QGroupBox("Slider Control")
        slider_layout = QVBoxLayout(slider_control_group)
        
        # 窗口大小控制 - 改为垂直布局
        window_size_layout = QVBoxLayout()
        window_size_layout.addWidget(QLabel("Window Size (%)"))
        self.window_size_spin = QSpinBox()
        self.window_size_spin.setRange(1, 50)
        self.window_size_spin.setValue(10)
        self.window_size_spin.setToolTip("Set the window size as percentage of total trace")
        window_size_layout.addWidget(self.window_size_spin)
        
        # 步进大小控制 - 改为垂直布局
        step_size_layout = QVBoxLayout()
        step_size_layout.addWidget(QLabel("Step Size (%)"))
        self.step_size_spin = QSpinBox()
        self.step_size_spin.setRange(1, 20)
        self.step_size_spin.setValue(5)
        self.step_size_spin.setToolTip("Set step size for slider movement buttons")
        step_size_layout.addWidget(self.step_size_spin)
        
        # 参数控制放在一行
        params_layout = QHBoxLayout()
        params_layout.addLayout(window_size_layout)
        params_layout.addLayout(step_size_layout)
        slider_layout.addLayout(params_layout)
        
        # 滑块控制按钮 - 改回横向排列
        slider_buttons_layout = QHBoxLayout()
        self.slider_left_btn = QPushButton("← Left")
        self.slider_left_btn.setMinimumWidth(120)  # 增加按钮宽度
        self.slider_right_btn = QPushButton("Right →")
        self.slider_right_btn.setMinimumWidth(120)  # 增加按钮宽度
        slider_buttons_layout.addWidget(self.slider_left_btn)
        slider_buttons_layout.addWidget(self.slider_right_btn)
        slider_layout.addLayout(slider_buttons_layout)
        

        # 5. Spikes 列表组
        spikes_list_group = QGroupBox("Spikes List")
        spikes_list_layout = QVBoxLayout(spikes_list_group)
        
        # 5.0 Pop Out 按钮
        popout_btn_layout = QHBoxLayout()
        popout_btn_layout.addStretch()
        self.popout_list_btn = QPushButton("List")
        self.popout_list_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        self.popout_list_btn.clicked.connect(self.open_spikes_list_window)
        
        # 5.1 Manage Groups 按钮
        self.manage_groups_btn = QPushButton("Groups")
        self.manage_groups_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.manage_groups_btn.clicked.connect(self.manage_groups)
        
        popout_btn_layout.addWidget(self.manage_groups_btn)
        popout_btn_layout.addWidget(self.popout_list_btn)
        spikes_list_layout.addLayout(popout_btn_layout)
        
        # 5.2 Spikes 表格
        self.spikes_table = QTableWidget()
        self.spikes_table.setColumnCount(6)  # 增加 Group 列
        self.spikes_table.setHorizontalHeaderLabels(["ID", "Time (s)", "Amplitude (nA)", "Duration (ms)", "Group", "Actions"])
        self.spikes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.spikes_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.spikes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # 设置列宽
        header = self.spikes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 时间列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 振幅列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 持续时间列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Group列
        
        # 操作列设置为固定宽度，确保按钮不重叠
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.spikes_table.setColumnWidth(5, 200)  # Actions列 - 增加到200px确保按钮不重叠
        
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

        control_layout.addWidget(spikes_list_group)
        
        # ==================== 右侧：绘图区域 ====================
        self.plot_container = QWidget()
        self.plot_container.setMinimumWidth(600)
        plot_layout = QVBoxLayout(self.plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        
        # ==================== 将左右区域添加到分割器 ====================
        main_splitter.addWidget(control_widget)
        main_splitter.addWidget(self.plot_container)
        
        # 设置分割器初始比例 (减小左侧控制面板宽度，给绘图区域更多空间)
        main_splitter.setSizes([200, 800])  # 从 250 减小到 200
        main_splitter.setStretchFactor(0, 0)  # 控制面板不伸缩
        main_splitter.setStretchFactor(1, 1)  # 绘图区域可伸缩
        
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
    
    
    def _find_detector_dialog(self):
        """找到顶级的 SpikesDetectorDialog"""
        dialog_parent = self.parent()
        while dialog_parent is not None:
            if hasattr(dialog_parent, 'segmentation_enabled') and hasattr(dialog_parent, 'segment_manager'):
                return dialog_parent
            dialog_parent = dialog_parent.parent() if hasattr(dialog_parent, 'parent') else None
        return self  # 如果找不到，返回 self
    
    def manage_groups(self):
        """打开组管理对话框"""
        # 使用顶级对话框作为 parent
        parent_dialog = self._find_detector_dialog()
        dialog = GroupManagerDialog(self.spike_groups, parent_dialog)
        if dialog.exec():
            # 更新组列表
            self.spike_groups = dialog.get_groups()
            # 刷新表格以更新下拉框选项
            self.update_spikes_table()
            
    def on_spike_group_changed(self, row, group_name):
        """处理Spike组变更"""
        if 0 <= row < len(self.manual_spikes):
            self.manual_spikes[row]['group'] = group_name
    
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
        
        # 确保必要的UI元素存在（移除了slider_info_label检查）
        required_attributes = []
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
            
            # 创建子图 - 修改高度比例为 1:2:1.5
            grid = self.manual_fig.add_gridspec(3, 1, height_ratios=[1, 2, 1.5])
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
            self.trace_ax.plot(time_axis, data, linewidth=0.5)
            self.trace_ax.set_xlim(time_axis[0], time_axis[-1])  # 消除左右空隙
            
            # 绘制已标记的手动峰值 - 只显示当前时间范围内的峰值
            current_time_start = time_axis[0]
            current_time_end = time_axis[-1]
            
            for spike in self.manual_spikes:
                if 'index' in spike and 'time' in spike:
                    spike_time = spike['time']
                    # 只绘制在当前时间范围内的 spike
                    if current_time_start <= spike_time <= current_time_end:
                        # 找到在当前数据中对应的索引
                        spike_idx_in_current = np.abs(time_axis - spike_time).argmin()
                        
                        # 检查是否是最近添加的峰值，如果是则使用不同颜色高亮显示
                        if hasattr(self, 'last_added_peak_id') and spike.get('id') == self.last_added_peak_id:
                            self.trace_ax.plot(time_axis[spike_idx_in_current], data[spike_idx_in_current], 
                                            'ro', markersize=8, alpha=0.7)
                        else:
                            self.trace_ax.plot(time_axis[spike_idx_in_current], data[spike_idx_in_current], 
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
            
            # 在trace_ax上用好看的绿色标记当前窗口位置
            self.trace_ax.axvspan(
                window_start_time, 
                window_end_time, 
                facecolor='#4CAF50',  # Material Design 绿色，更现代好看
                alpha=0.2,
                edgecolor='#388E3C',  # 深一点的绿色边缘
                linewidth=1.5
            )
            
            # 绘制放大视图 (滑块选择的区域)
            self.zoomed_ax.plot(time_axis[start_idx:end_idx+1], data[start_idx:end_idx+1], linewidth=0.5)
            self.zoomed_ax.set_xlim(window_start_time, window_end_time)  # 消除左右空隙
            
            # 在zoomed_ax中标记当前窗口中的峰值，并用浅绿色高亮已保存的spikes区域
            for spike in self.manual_spikes:
                if 'index' in spike:
                    peak_idx = spike['index']
                    peak_time = spike.get('time', time_axis[peak_idx])
                    
                    # 检查峰值是否在当前窗口中
                    if window_start_time <= peak_time <= window_end_time:
                        # 添加浅绿色背景高亮已保存的spike区域
                        spike_start_time = spike.get('start_time', peak_time - 0.001)
                        spike_end_time = spike.get('end_time', peak_time + 0.001)
                        
                        # 确保高亮区域在当前窗口范围内
                        spike_start_time = max(window_start_time, spike_start_time)
                        spike_end_time = min(window_end_time, spike_end_time)
                        
                        # 添加浅绿色高亮 - 调得稍微深一点，便于看清
                        saved_highlight = self.zoomed_ax.axvspan(spike_start_time, spike_end_time, 
                                                                alpha=0.12, color='lightgreen')  # alpha从0.05调到0.12，稍微深一点
                        saved_highlight._is_saved_spike = True  # 标记为已保存的spike
                        
                        # 标记峰值点
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
            
            # 如果有选中的峰值数据，则调用update_peak_display
            if hasattr(self, 'current_manual_spike_data') and self.current_manual_spike_data:
                # 单独调用update_peak_display方法更新figure3
                self.update_peak_display()
            else:
                # 如果没有选中的峰值数据，则显示提示信息
                self.spike_ax.text(0.5, 0.5, "Select a region in the Zoomed View above",
                        horizontalalignment='center',
                        verticalalignment='center',
                        transform=self.spike_ax.transAxes,
                        fontsize=10, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))
            
            # 调整布局
            self.manual_fig.tight_layout()
            
            # ==================== 创建并对齐滑块 ====================
            # 在tight_layout之后获取trace_ax的实际位置
            pos = self.trace_ax.get_position()
            
            # 使用trace_ax的宽度和水平位置来创建滑块
            # 调整：宽度缩短一点 (85%) 并居中，高度再高一点以避免挡住标题
            # 点击subplot1即可跳转到该位置（不再需要拖动相关的标志）
            
            # 断开旧的事件连接（如果存在）
            if hasattr(self, '_drag_press_cid'):
                self.manual_fig.canvas.mpl_disconnect(self._drag_press_cid)
            if hasattr(self, '_drag_release_cid'):
                self.manual_fig.canvas.mpl_disconnect(self._drag_release_cid)
            if hasattr(self, '_drag_motion_cid'):
                self.manual_fig.canvas.mpl_disconnect(self._drag_motion_cid)
            
            # 连接鼠标事件并保存连接ID（只需要press事件）
            self._drag_press_cid = self.manual_fig.canvas.mpl_connect('button_press_event', self.on_highlight_press)
            
            
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
    
    def on_highlight_press(self, event):
        """点击subplot1时，将绿色highlight的中心移动到点击位置"""
        # 检查必要的属性是否存在
        if not hasattr(self, 'trace_ax'):
            return
        
        if event.inaxes != self.trace_ax or event.button != 1:
            return
        
        if event.xdata is None:
            return
        
        # 获取数据范围
        if not hasattr(self, 'plot_canvas') or self.plot_canvas is None:
            return
            
        time_axis = self.plot_canvas.time_axis
        if time_axis is None or len(time_axis) == 0:
            return
        
        total_time = time_axis[-1] - time_axis[0]
        window_size = self.window_size_spin.value() / 100.0
        
        # 计算点击位置对应的slider_pos
        # 使点击位置成为窗口的中心
        click_time = event.xdata
        window_center_pos = (click_time - time_axis[0]) / total_time
        
        # 调整为窗口左边界的位置
        new_pos = window_center_pos - window_size / 2.0
        new_pos = max(0.0, min(1.0 - window_size, new_pos))
        
        self.slider_pos = new_pos
        
        # 更新显示
        self.update_manual_plot(preserve_selection=True)
    
    def on_highlight_release(self, event):
        """不再需要release处理"""
        pass
    
    def on_highlight_drag(self, event):
        """不再需要drag处理"""
        pass
    
    def on_slider_changed_old(self, val):
        """处理滑块值变化"""
        # 保存之前的值
        old_val = self.slider_pos
        
        # 更新值
        self.slider_pos = val
        
        # 保存figure3的当前状态
        figure3_data = None
        if hasattr(self, 'current_manual_spike_data') and self.current_manual_spike_data:
            figure3_data = self.current_manual_spike_data.copy()
        
        # 更新绘图
        self.update_manual_plot(preserve_selection=True)
        
        # 还原figure3的状态
        if figure3_data is not None:
            self.current_manual_spike_data = figure3_data
            # 重新绘制figure3
            self.update_peak_display()
    
    def move_slider_left(self):
        """向左移动highlight"""
        step_size = self.step_size_spin.value() / 100.0  # 将百分比转换为小数
        new_pos = max(0, self.slider_pos - step_size)
        self.slider_pos = new_pos
        self.update_manual_plot(preserve_selection=True)
    
    def move_slider_right(self):
        """向右移动highlight"""
        step_size = self.step_size_spin.value() / 100.0  # 将百分比转换为小数
        new_pos = min(1, self.slider_pos + step_size)
        self.slider_pos = new_pos
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
                props=dict(alpha=0.05, facecolor='red', zorder=0),  # 调浅，从0.3改为0.05，添加zorder=0
                interactive=True,
                drag_from_anywhere=True
            )
            
            # 添加右键点击事件处理：右键点击选中的区域即可保存
            if hasattr(self, '_spike_ax_right_click_cid'):
                try:
                    self.spike_ax.figure.canvas.mpl_disconnect(self._spike_ax_right_click_cid)
                except Exception:
                    pass
            self._spike_ax_right_click_cid = self.spike_ax.figure.canvas.mpl_connect(
                'button_press_event', 
                self.on_spike_ax_right_click
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
                props=dict(alpha=0.05, facecolor='blue', zorder=0),  # alpha降到0.05，zorder=0让其在数据下面
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
            
            # 在zoomed_ax上绘制选择区域的蓝色高亮
            # 关键修复：必须先清除所有旧的临时选择高亮（蓝色）
            # 但保留已保存spikes的浅绿色高亮
            
            # 收集所有需要移除的集合 (collections)
            collections_to_remove = []
            for collection in list(self.zoomed_ax.collections):  # 使用list()创建副本
                # 移除临时选择区域，保留已保存的spike高亮
                if hasattr(collection, '_is_selection'):
                    collections_to_remove.append(collection)
            
            # 收集所有需要移除的补丁 (patches) - axvspan创建的是Polygon，属于Patch
            patches_to_remove = []
            for patch in list(self.zoomed_ax.patches):
                if hasattr(patch, '_is_selection'):
                    patches_to_remove.append(patch)
            
            # 移除收集到的集合
            for collection in collections_to_remove:
                try:
                    collection.remove()
                except ValueError:
                    pass
            
            # 移除收集到的补丁
            for patch in patches_to_remove:
                try:
                    patch.remove()
                except ValueError:
                    pass
            
            # 添加新的临时选择高亮区域（蓝色）
            span = self.zoomed_ax.axvspan(
                xmin, xmax,
                alpha=0.05,  # 调得很浅，从0.3改为0.05
                color='blue',
                zorder=0  # 放在数据线下面
            )
            span._is_selection = True  # 标记为临时选择
            
            # 计算选择区域的持续时间
            duration_ms = (xmax - xmin) * 1000
            
            
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 在时间轴中找到选择的起始和结束索引
            start_idx = np.abs(time_axis - xmin).argmin()
            end_idx = np.abs(time_axis - xmax).argmin()
            
            # 获取选中区域的数据
            selection_data = data[start_idx:end_idx+1]
            
            # 计算基线校正值（左右两边点的平均值）
            # 当baseline correction启用时，使用左侧窗口数据
            # 当未启用时，使用选区左右边界点的平均值作为baseline
            baseline_value = 0
            if self.baseline_correction_check.isChecked():
                baseline_window = self.baseline_window_spin.value()
                baseline_start = max(0, start_idx - baseline_window)
                baseline_data = data[baseline_start:start_idx]
                
                if len(baseline_data) > 0:
                    baseline_value = np.mean(baseline_data)
            else:
                # 计算左右边界点的平均值作为baseline
                left_value = data[start_idx] if start_idx < len(data) else 0
                right_value = data[min(end_idx, len(data)-1)] if end_idx < len(data) else 0
                baseline_value = (left_value + right_value) / 2.0
            
            # 根据振幅模式计算峰值振幅
            amp_mode = self.amplitude_mode_combo.currentText()
            
            if amp_mode == "Maximum":
                # 找到选区内的最大值（正峰值）
                max_idx = np.argmax(selection_data)
                peak_idx = start_idx + max_idx
                amplitude = selection_data[max_idx] - baseline_value
            elif amp_mode == "Minimum":
                # 找到选区内的最小值（负峰值）
                min_idx = np.argmin(selection_data)
                peak_idx = start_idx + min_idx
                amplitude = selection_data[min_idx] - baseline_value
            elif amp_mode == "Average":
                # 使用平均值
                amplitude = np.mean(selection_data) - baseline_value
                peak_idx = start_idx + len(selection_data) // 2
            else:  # 中值
                amplitude = np.median(selection_data) - baseline_value
                peak_idx = start_idx + len(selection_data) // 2
            
            # 计算归一化振幅 (amplitude / baseline * 100%)
            normalized_amplitude = (amplitude / baseline_value * 100.0) if baseline_value != 0 else 0
            
            # 保存当前峰值数据
            self.current_manual_spike_data = {
                'index': peak_idx,
                'time': time_axis[peak_idx],
                'amplitude': amplitude,
                'baseline': baseline_value,
                'normalized_amplitude': normalized_amplitude,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'start_time': xmin,
                'end_time': xmax,
                'duration': xmax - xmin,
                'manual': True,
                # 清除之前的最终选择
                'final_start_time': None,
                'final_end_time': None,
                'final_start_idx': None,
                'final_end_idx': None,
                'final_duration': None
            }
            
            # ==================== 修复高亮管理 ====================
            # 在zoomed_ax中高亮显示选择的区域
            # 关键修复：必须先清除所有旧的临时选择高亮（蓝色）
            # 但保留已保存spikes的浅绿色高亮
            
            # 收集所有需要移除的集合 (collections)
            collections_to_remove = []
            for collection in list(self.zoomed_ax.collections):  # 使用list()创建副本
                # 移除临时选择区域，保留已保存的spike高亮
                if hasattr(collection, '_is_selection'):
                    collections_to_remove.append(collection)
            
            # 收集所有需要移除的补丁 (patches) - axvspan创建的是Polygon，属于Patch
            patches_to_remove = []
            for patch in list(self.zoomed_ax.patches):
                if hasattr(patch, '_is_selection'):
                    patches_to_remove.append(patch)
            
            # 移除收集到的集合
            for collection in collections_to_remove:
                try:
                    collection.remove()
                except ValueError:
                    pass
            
            # 移除收集到的补丁
            for patch in patches_to_remove:
                try:
                    patch.remove()
                except ValueError:
                    pass
            
            # 添加新的临时选择高亮区域（蓝色）
            span = self.zoomed_ax.axvspan(xmin, xmax, alpha=0.05, color='blue', zorder=0)  # 调浅从0.3改为0.05
            span._is_selection = True  # 标记为临时选择
            
            # ==================== 清除旧的峰值标记 ====================
            # 标记峰值位置 - 移除旧的临时峰值标记
            lines_to_remove = []
            for line in list(self.zoomed_ax.lines):  # 使用list()创建副本
                if hasattr(line, '_is_peak_marker'):
                    lines_to_remove.append(line)
            
            for line in lines_to_remove:
                try:
                    line.remove()
                except ValueError:
                    pass
            
            # 添加新的峰值标记（红色圆点）
            marker = self.zoomed_ax.plot(time_axis[peak_idx], data[peak_idx], 'ro', ms=8)[0]
            marker._is_peak_marker = True  # 标记为临时峰值标记
            
            # 更新第三个子图，显示选中的峰值
            self.update_peak_display()
            
            # 启用添加按钮
            self.add_spike_button.setEnabled(True)
            
            # 恢复zoomed_ax的视图范围
            if hasattr(self, 'zoomed_ax') and self.zoomed_ax is not None:
                self.zoomed_ax.set_xlim(saved_xlim)
                self.zoomed_ax.set_ylim(saved_ylim)
                
                # 强制立即重绘canvas以确保高亮区域正确显示
        # 这对于清除旧的高亮区域非常重要
                if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                    # 使用draw()而不是draw_idle()以确保立即刷新
                    self.plot_canvas.draw()
                    # 刷新画布以确保所有变更都被应用
                    self.plot_canvas.flush_events()
            
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
            
            # 获取当前figure3的视图范围
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                current_xlim = self.spike_ax.get_xlim()
                current_ylim = self.spike_ax.get_ylim()
            
            # 确保选择是有效的
            if xmin >= xmax:
                print(f"Warning: Invalid span selection: xmin={xmin}, xmax={xmax}")
                return
                
            # 获取当前数据和时间轴
            data = self.plot_canvas.current_channel_data
            time_axis = self.plot_canvas.time_axis
            
            # 获取当前figure3显示的时间范围
            start_time = self.current_manual_spike_data.get('start_time')
            end_time = self.current_manual_spike_data.get('end_time')
            
            # 确保选择在显示范围内
            xmin = max(start_time, xmin)
            xmax = min(end_time, xmax)
            
            # 在时间轴中找到选择的起始和结束索引
            start_idx = np.abs(time_axis - xmin).argmin()
            end_idx = np.abs(time_axis - xmax).argmin()
            
            # 获取选中区域的数据
            selection_data = data[start_idx:end_idx+1]
            
            # 计算基线校正值（左右两边点的平均值）
            baseline_value = 0
            if self.baseline_correction_check.isChecked():
                baseline_window = self.baseline_window_spin.value()
                baseline_start = max(0, start_idx - baseline_window)
                baseline_data = data[baseline_start:start_idx]
                
                if len(baseline_data) > 0:
                    baseline_value = np.mean(baseline_data)
            else:
                # 计算左右边界点的平均值作为baseline
                left_value = data[start_idx] if start_idx < len(data) else 0
                right_value = data[min(end_idx, len(data)-1)] if end_idx < len(data) else 0
                baseline_value = (left_value + right_value) / 2.0
            
            # 根据振幅模式计算峰值振幅
            amp_mode = self.amplitude_mode_combo.currentText()
            
            if amp_mode == "Maximum":
                # 找到选区内的最大值（正峰值）
                if len(selection_data) > 0:
                    max_idx = np.argmax(selection_data)
                    peak_idx = start_idx + max_idx
                    amplitude = selection_data[max_idx] - baseline_value
                else:
                    # 使用原始峰值数据
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
                    baseline_value = self.current_manual_spike_data.get('baseline', 0)
            elif amp_mode == "Minimum":
                # 找到选区内的最小值（负峰值）
                if len(selection_data) > 0:
                    min_idx = np.argmin(selection_data)
                    peak_idx = start_idx + min_idx
                    amplitude = selection_data[min_idx] - baseline_value
                else:
                    # 使用原始峰值数据
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
                    baseline_value = self.current_manual_spike_data.get('baseline', 0)
            elif amp_mode == "Average":
                # 使用平均值
                if len(selection_data) > 0:
                    amplitude = np.mean(selection_data) - baseline_value
                    peak_idx = start_idx + len(selection_data) // 2
                else:
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
                    baseline_value = self.current_manual_spike_data.get('baseline', 0)
            else:  # 中值
                if len(selection_data) > 0:
                    amplitude = np.median(selection_data) - baseline_value
                    peak_idx = start_idx + len(selection_data) // 2
                else:
                    peak_idx = self.current_manual_spike_data.get('index')
                    amplitude = self.current_manual_spike_data.get('amplitude')
                    baseline_value = self.current_manual_spike_data.get('baseline', 0)
            
            # 计算归一化振幅 (amplitude / baseline * 100%)
            normalized_amplitude = (amplitude / baseline_value * 100.0) if baseline_value != 0 else 0
            
            # 计算选择区域的持续时间
            duration_ms = (xmax - xmin) * 1000
            

            
            # 备份当前选择的数据
            current_data = self.current_manual_spike_data.copy()
            
            # 更新当前峰值数据的细节
            self.current_manual_spike_data.update({
                'final_start_idx': start_idx,
                'final_end_idx': end_idx,
                'final_start_time': xmin,
                'final_end_time': xmax,
                'final_duration': xmax - xmin,
                'index': peak_idx,
                'time': time_axis[peak_idx],
                'amplitude': amplitude,
                'baseline': baseline_value,
                'normalized_amplitude': normalized_amplitude
            })
            
            # 在第三个子图中显示最终选择的区域
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                # 清除之前的区域标记
                for collection in self.spike_ax.collections:
                    if hasattr(collection, '_is_final_selection'):
                        collection.remove()
                
                # 保存当前的状态
                self._in_final_selection = True
                
                # 调用update_peak_display更新显示
                self.update_peak_display()
                
                # 重置状态
                self._in_final_selection = False
                
                # 恢复视图范围
                if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                    self.spike_ax.set_xlim(current_xlim)
                    self.spike_ax.set_ylim(current_ylim)
                    
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
                
            # 确保索引在有效范围内
            if start_idx >= len(data) or end_idx >= len(data) or start_idx < 0 or end_idx < 0:
                print(f"Warning: Invalid index range [{start_idx}:{end_idx}] for data length {len(data)}")
                return
                
            # 确保start_idx <= end_idx
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
                
            # 清除现有内容
            self.spike_ax.clear()
            
            # 设置网格和轴标签
            self.spike_ax.grid(True, linestyle='--', alpha=0.7)
            self.spike_ax.set_xlabel("Time (s)", fontsize=9)
            self.spike_ax.set_ylabel("Current (nA)", fontsize=9)
            
            # 获取选择区域的数据
            selection_data = data[start_idx:end_idx+1]
            selection_time = time_axis[start_idx:end_idx+1]
            
            # 检查数据是否为空
            if len(selection_data) == 0 or len(selection_time) == 0:
                print("Warning: No data to display in peak_display")
                # 设置一个默认的空白视图
                self.spike_ax.set_title("No data to display", fontsize=10, fontweight='bold')
                return
                
            # 绘制所选区域的数据
            self.spike_ax.plot(selection_time, selection_data, linewidth=0.5)
            
            # 显示已标记的峰值
            for spike in self.manual_spikes:
                if 'index' in spike and 'time' in spike:
                    spike_time = spike.get('time')
                    spike_index = spike.get('index')
                    
                    # 检查峰值是否在当前显示范围内
                    if start_time <= spike_time <= end_time and spike_index < len(data):
                        # 使用绿色标记已添加的峰值
                        self.spike_ax.plot(spike_time, data[spike_index], 'go', ms=6, alpha=0.7)
            
            # 高亮显示用户在figure3中选择的区域（如果有）
            final_start_time = self.current_manual_spike_data.get('final_start_time')
            final_end_time = self.current_manual_spike_data.get('final_end_time')
            
            if final_start_time is not None and final_end_time is not None:
                # 确保final_start_time和final_end_time在显示范围内
                if (min(selection_time) <= final_start_time <= max(selection_time) or 
                    min(selection_time) <= final_end_time <= max(selection_time) or
                    (final_start_time <= min(selection_time) and final_end_time >= max(selection_time))):
                    
                    # 高亮显示用户在figure3中选择的区域
                    highlight_start = max(min(selection_time), final_start_time)
                    highlight_end = min(max(selection_time), final_end_time)
                    self.spike_ax.axvspan(
                        highlight_start,
                        highlight_end,
                        alpha=0.05,  # 调浅，从0.3改为0.05
                        color='red',
                        zorder=0  # 放在数据下面
                    )
            
            # 不在trace_ax上绘制蓝色highlight（用户不需要）
            # 只保留绿色的当前窗口位置标记（在update_manual_plot中绘制）
            
            # 设置鼠标悬停时的光标样式提示可点击
            def on_hover(event):
                if event.inaxes == self.trace_ax:
                    event.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    event.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            
            # 断开旧的hover连接（如果存在）
            if hasattr(self, '_hover_cid'):
                self.manual_fig.canvas.mpl_disconnect(self._hover_cid)
            self._hover_cid = self.manual_fig.canvas.mpl_connect('motion_notify_event', on_hover)
            # 标记当前选择的峰值位置（用红色标记当前选择的峰值）
            if peak_idx is not None and peak_idx < len(data):
                if min(selection_time) <= peak_time <= max(selection_time):
                    self.spike_ax.plot(peak_time, data[peak_idx], 'ro', ms=8)
            
            # 更新标题显示峰值信息
            duration_ms = (end_time - start_time) * 1000
            # 如果有最终选择，则在标题中同时显示初始和最终选择信息
            if final_start_time is not None and final_end_time is not None:
                final_duration_ms = (final_end_time - final_start_time) * 1000
                self.spike_ax.set_title(
                    f"Selected Peak: {start_time:.4f}s - {end_time:.4f}s, Final: {final_start_time:.4f}s - {final_end_time:.4f}s, Amp={amplitude:.2f}nA",
                    fontsize=9, fontweight='bold'
                )
            else:
                self.spike_ax.set_title(
                    f"Selected Peak: {start_time:.4f}s - {end_time:.4f}s, Amp={amplitude:.2f}nA, Dur={duration_ms:.2f}ms",
                    fontsize=10, fontweight='bold'
                )
            
            # 设置显示范围为用户选择的区域
            # 添加验证以避免 start_time == end_time 的警告
            if abs(end_time - start_time) > 1e-9:  # 确保有有效范围
                self.spike_ax.set_xlim(start_time, end_time)
            else:
                # 如果范围太小，使用一个小的默认范围
                margin = 0.001  # 1ms 的边距
                self.spike_ax.set_xlim(start_time - margin, end_time + margin)
            
            # 自动调整Y轴范围以显示完整数据
            self.spike_ax.margins(y=0.1)
            
            # 重绘
            if hasattr(self, 'plot_canvas') and self.plot_canvas is not None:
                self.plot_canvas.draw()
                
        except Exception as e:
            import traceback
            print(f"Error updating peak display: {e}")
            traceback.print_exc()
    
    def on_spike_ax_right_click(self, event):
        """处理subplot3上的右键点击事件 - 右键点击选中区域即可保存"""
        # 只处理右键点击
        if event.button != 3:  # 3是右键
            return
        
        # 检查是否点击在spike_ax上
        if event.inaxes != self.spike_ax:
            return
        
        # 检查是否有当前选中的数据
        if not hasattr(self, 'current_manual_spike_data') or not self.current_manual_spike_data:
            return
        
        # 检查是否有最终选择的区域
        final_start = self.current_manual_spike_data.get('final_start_time')
        final_end = self.current_manual_spike_data.get('final_end_time')
        
        if final_start is None or final_end is None:
            return
        
        # 检查右键点击位置是否在选中区域内
        if event.xdata is not None and final_start <= event.xdata <= final_end:
            # 在选中区域内右键点击
            # 检查有多少个 groups
            num_groups = len(self.spike_groups)
            
            if num_groups == 1:
                # 只有一个 group，直接添加
                self.add_manual_peak()
            else:
                # 有多个 groups，显示选择菜单
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu {
                        background-color: white;
                        border: 1px solid #cccccc;
                    }
                    QMenu::item {
                        padding: 5px 25px 5px 10px;
                    }
                    QMenu::item:selected {
                        background-color: #0078d7;
                        color: white;
                    }
                """)
                
                # 为每个 group 添加菜单项
                for group_name in self.spike_groups:
                    action = menu.addAction(f"Add to {group_name}")
                    action.setData(group_name)
                
                # 在鼠标位置显示菜单
                action = menu.exec(self.spike_ax.figure.canvas.mapToGlobal(
                    self.spike_ax.figure.canvas.mapFromParent(
                        self.spike_ax.figure.canvas.parentWidget().mapFromGlobal(
                            self.spike_ax.figure.canvas.cursor().pos()
                        )
                    )
                ))
                
                # 如果用户选择了某个 group
                if action:
                    selected_group = action.data()
                    # 设置当前数据的 group
                    self.current_manual_spike_data['group'] = selected_group
                    # 添加 spike
                    self.add_manual_peak()
    
    def add_manual_peak(self):
        """添加手动标记的峰值"""
        if not hasattr(self, 'current_manual_spike_data') or self.current_manual_spike_data is None:
            QMessageBox.warning(self, "Warning", "No peak data to add")
            return
        
        try:
            # 保存当前的视图状态
            current_xlim = None
            current_ylim = None
            if hasattr(self, 'spike_ax') and self.spike_ax is not None:
                current_xlim = self.spike_ax.get_xlim()
                current_ylim = self.spike_ax.get_ylim()
            
            # 创建峰值数据的副本进行修改
            peak_data = self.current_manual_spike_data.copy()
            
            # 获取最终选择的数据
            final_start_time = peak_data.get('final_start_time')
            final_end_time = peak_data.get('final_end_time')
            
            # 如果有最终选择，则使用最终选择的数据
            if final_start_time is not None and final_end_time is not None:
                # 使用最终选择的数据更新峰值
                peak_data['start_time'] = final_start_time
                peak_data['end_time'] = final_end_time
                peak_data['duration'] = final_end_time - final_start_time
                peak_data['start_idx'] = peak_data.get('final_start_idx')
                peak_data['end_idx'] = peak_data.get('final_end_idx')
                
            # 给峰值添加ID
            self.manual_spike_count += 1
            peak_data['id'] = self.manual_spike_count
            
            # 添加默认组
            if 'group' not in peak_data:
                peak_data['group'] = 'Default'
            
            # 添加到峰值列表
            self.manual_spikes.append(peak_data)
            
            # 更新计数标签
            self.peak_count_label.setText(f"Manual peaks: {len(self.manual_spikes)}")
            
            # 更新spikes表格
            self.update_spikes_table()
            

            
            # 标记最后添加的峰值ID，用于高亮显示
            self.last_added_peak_id = self.manual_spike_count
            
            # 保存当前选择，以便能够恢复figure3的显示
            current_data = self.current_manual_spike_data.copy()
            
            # 设置标志以避免递归和初始化问题
            self._adding_peak = True
            
            # 清除临时的蓝色选择高亮（因为已经添加到列表中了）
            # 这将防止蓝色高亮累积
            # 1. 清除collections
            collections_to_remove = []
            for collection in list(self.zoomed_ax.collections):
                if hasattr(collection, '_is_selection'):
                    collections_to_remove.append(collection)
            for collection in collections_to_remove:
                try:
                    collection.remove()
                except (ValueError, AttributeError):
                    pass
            
            # 2. 清除patches (axvspan创建的对象)
            patches_to_remove = []
            for patch in list(self.zoomed_ax.patches):
                if hasattr(patch, '_is_selection'):
                    patches_to_remove.append(patch)
            for patch in patches_to_remove:
                try:
                    patch.remove()
                except (ValueError, AttributeError):
                    pass
            
            # 更新绘图（不传递无效参数）
            self.update_manual_plot(preserve_selection=True)
            
            # 恢复figure3的显示
            self.current_manual_spike_data = current_data
            
            # 恢复视图状态
            if current_xlim is not None and current_ylim is not None and hasattr(self, 'spike_ax') and self.spike_ax is not None:
                self.spike_ax.set_xlim(current_xlim)
                self.spike_ax.set_ylim(current_ylim)
            
            # 手动调用update_peak_display来更新figure3
            # 这会保持figure3的数据显示不变
            self.update_peak_display()
            
            # 重置标志
            self._adding_peak = False
            
            # 发送峰值添加信号
            self.peak_added.emit(peak_data)
            
            # 显示临时消息
            self.show_temp_message("Peak added successfully!")
            
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

            
            # 更新绘图
            self.update_manual_plot()
            
            # 更新表格
            self.update_spikes_table()

    def export_manual_peaks(self):
        """将峰值数据导出到文件夹（包含统计数据、波形数据和图表）"""
        if not self.manual_spikes:
            QMessageBox.warning(self, "Warning", "No peaks to export")
            return
        
        # 获取数据文件路径作为默认路径
        default_dir = ""
        if hasattr(self, 'plot_canvas') and self.plot_canvas:
            if hasattr(self.plot_canvas, 'file_path') and self.plot_canvas.file_path:
                default_dir = os.path.dirname(self.plot_canvas.file_path)
        
        # 让用户选择保存文件夹
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Export Folder",
            default_dir if default_dir else "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not folder_path:
            return
            
        try:
            import csv
            import os
            
            # 创建导出文件夹（peaks_export_TIMESTAMP）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_folder = os.path.join(folder_path, f"peaks_export_{timestamp}")
            os.makedirs(export_folder, exist_ok=True)
            
            # 创建子文件夹
            plots_folder = os.path.join(export_folder, "spike_plots")
            os.makedirs(plots_folder, exist_ok=True)
            
            statistics_folder = os.path.join(export_folder, "statistics_plots")
            os.makedirs(statistics_folder, exist_ok=True)
            
            # 1. 导出Spike统计信息到CSV
            stats_file = os.path.join(export_folder, "peaks_statistics.csv")
            headers = ['ID', 'Time (s)', 'Amplitude (nA)', 'Baseline (nA)', 'Normalized Amplitude (%)', 'Duration (ms)', 'Start Time', 'End Time', 'Group']
            data = []
            
            for spike in self.manual_spikes:
                row = [
                    spike.get('id', ''),
                    spike.get('time', 0),
                    spike.get('amplitude', 0),
                    spike.get('baseline', 0),
                    spike.get('normalized_amplitude', 0),
                    spike.get('duration', 0) * 1000,  # 转为毫秒
                    spike.get('start_time', 0),
                    spike.get('end_time', 0),
                    spike.get('group', 'Default')
                ]
                data.append(row)
                
            with open(stats_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)
            
            # 2. 按组分组spikes
            grouped_spikes = {}
            if self.plot_canvas and self.plot_canvas.current_channel_data is not None:
                for spike in self.manual_spikes:
                    group = spike.get('group', 'Default')
                    if group not in grouped_spikes:
                        grouped_spikes[group] = []
                    grouped_spikes[group].append(spike)
                
                data_obj = self.plot_canvas.current_channel_data
                time_axis = self.plot_canvas.time_axis
                sampling_rate = self.plot_canvas.sampling_rate
                
                # 3. 导出每个 group 的 waveform 数据到 CSV
                for group_name, group_spikes in grouped_spikes.items():
                    if not group_spikes:
                        continue
                    
                    # 为每个组创建 CSV 文件
                    group_csv = os.path.join(export_folder, f"{group_name}_waveforms.csv")
                    
                    # 准备该组的数据
                    max_length = 0
                    spike_waveforms = []
                    spike_ids = []
                    
                    # 收集所有波形数据
                    for spike in group_spikes:
                        spike_id = spike.get('id', 'unknown')
                        start_idx = spike.get('start_idx')
                        end_idx = spike.get('end_idx')
                        
                        if start_idx is not None and end_idx is not None:
                            waveform = data_obj[start_idx:end_idx+1]
                            spike_waveforms.append(waveform)
                            spike_ids.append(spike_id)
                            max_length = max(max_length, len(waveform))
                    
                    # 写入 CSV 文件
                    with open(group_csv, 'w', newline='') as f:
                        writer = csv.writer(f)
                        
                        # 写入 header
                        header_row = ['Sample_Index']
                        for spike_id in spike_ids:
                            header_row.append(f'Spike_{spike_id}')
                        writer.writerow(header_row)
                        
                        # 按行写入数据
                        for sample_idx in range(max_length):
                            row = [sample_idx]
                            for waveform in spike_waveforms:
                                if sample_idx < len(waveform):
                                    row.append(waveform[sample_idx])
                                else:
                                    row.append('')  # 空值填充
                            writer.writerow(row)
                
                # 4. 为每个 group 创建 spike_plots 子文件夹并生成图表
                for spike in self.manual_spikes:
                    spike_id = spike.get('id', 'unknown')
                    spike_group = spike.get('group', 'Default')
                    start_idx = spike.get('start_idx')
                    end_idx = spike.get('end_idx')
                    
                    if start_idx is not None and end_idx is not None:
                        # 为该 group 创建子文件夹
                        group_plot_folder = os.path.join(plots_folder, spike_group)
                        os.makedirs(group_plot_folder, exist_ok=True)
                        
                        waveform = data_obj[start_idx:end_idx+1]
                        spike_time = time_axis[start_idx:end_idx+1] if time_axis is not None else np.arange(len(waveform))
                        
                        # 生成单个spike的图表（添加 Group 信息）
                        fig, ax = plt.subplots(figsize=(8, 4))
                        ax.plot(spike_time, waveform, linewidth=1.5, color='blue')
                        ax.set_xlabel('Time (s)')
                        ax.set_ylabel('Amplitude (nA)')
                        ax.set_title(f"Spike {spike_id} ({spike_group}) - Amplitude: {spike.get('amplitude', 0):.2f} nA, Duration: {spike.get('duration', 0)*1000:.2f} ms")
                        ax.grid(True, alpha=0.3)
                        
                        spike_plot_path = os.path.join(group_plot_folder, f"spike_{spike_id}.png")
                        fig.savefig(spike_plot_path, dpi=150, bbox_inches='tight')
                        plt.close(fig)
                
                # 5. 为每个组生成统计图表
                for group_name, group_spikes in grouped_spikes.items():
                    if not group_spikes:
                        continue
                    
                    # 创建统计图（overlaid spikes 和 scatter plot）
                    fig = Figure(figsize=(12, 5))
                    
                    # 4.1 绘制 Overlaid Spikes
                    ax1 = fig.add_subplot(1, 2, 1)
                    ax1.set_title(f"{group_name} - Overlaid Spikes ({len(group_spikes)} spikes)")
                    ax1.set_xlabel("Time (ms)")
                    ax1.set_ylabel("Amplitude (nA)")
                    
                    for spike in group_spikes:
                        start_idx = spike.get('start_idx')
                        end_idx = spike.get('end_idx')
                        
                        if start_idx is None or end_idx is None:
                            continue
                        
                        waveform = data_obj[start_idx:end_idx+1]
                        duration_samples = len(waveform)
                        time_ms = np.arange(duration_samples) / (sampling_rate / 1000.0) if sampling_rate else np.arange(duration_samples)
                        
                        ax1.plot(time_ms, waveform, alpha=0.5, linewidth=0.8)
                    
                    ax1.grid(True, alpha=0.3)
                    
                    # 4.2 绘制 Scatter Plot with Histograms
                    from matplotlib.gridspec import GridSpec
                    
                    # 提取duration和amplitude数据
                    durations = []
                    amplitudes = []
                    for spike in group_spikes:
                        dur = spike.get('duration', 0) * 1000  # 转为毫秒
                        amp = spike.get('amplitude', 0)
                        durations.append(dur)
                        amplitudes.append(amp)
                    
                    # 创建gridspec布局用于scatter plot
                    ax2 = fig.add_subplot(1, 2, 2)
                    pos = ax2.get_position()
                    ax2.remove()
                    
                    gs = GridSpec(3, 3, 
                                 left=pos.x0, right=pos.x0 + pos.width,
                                 bottom=pos.y0, top=pos.y0 + pos.height,
                                 height_ratios=[0.2, 0.02, 1],
                                 width_ratios=[1, 0.02, 0.2],
                                 hspace=0, wspace=0,
                                 figure=fig)
                    
                    # 散点图
                    ax_scatter = fig.add_subplot(gs[2, 0])
                    ax_scatter.scatter(durations, amplitudes, alpha=0.6, s=30, edgecolors='black', linewidth=0.5)
                    ax_scatter.set_xlabel("Duration (ms)")
                    ax_scatter.set_ylabel("Amplitude (nA)")
                    ax_scatter.set_title(f"{group_name} - Duration vs Amplitude")
                    ax_scatter.grid(True, alpha=0.3)
                    
                    # 上方直方图
                    ax_top = fig.add_subplot(gs[0, 0], sharex=ax_scatter)
                    ax_top.hist(durations, bins=15, alpha=0.7, edgecolor='black')
                    ax_top.set_ylabel("Count", fontsize=9)
                    ax_top.tick_params(axis='x', labelbottom=False)
                    ax_top.tick_params(axis='y', labelsize=8)
                    
                    # 右方直方图
                    ax_right = fig.add_subplot(gs[2, 2], sharey=ax_scatter)
                    ax_right.hist(amplitudes, bins=15, orientation='horizontal', alpha=0.7, edgecolor='black')
                    ax_right.set_xlabel("Count", fontsize=9)
                    ax_right.tick_params(axis='y', labelleft=False)
                    ax_right.tick_params(axis='x', labelsize=8)
                    
                    fig.subplots_adjust(left=0.08, right=0.95, top=0.92, bottom=0.1, wspace=0.35)
                    
                    # 保存统计图
                    stats_plot_path = os.path.join(statistics_folder, f"{group_name}_statistics.png")
                    fig.savefig(stats_plot_path, dpi=150, bbox_inches='tight')
                    plt.close(fig)
                
                # 6. 生成 Full Trace 图表（subplot1）并标记所有 spikes
                full_trace_folder = os.path.join(export_folder, "full_trace_plots")
                os.makedirs(full_trace_folder, exist_ok=True)
                
                # 检查是否有 segmentation（向上查找真正的 SpikesDetectorDialog）
                has_segments = False
                num_segments = 1
                segment_manager = None
                
                # 向上遍历父对象，找到 SpikesDetectorDialog
                dialog_parent = self.parent()
                while dialog_parent is not None:
                    # 检查是否是 SpikesDetectorDialog（通过检查是否有 segmentation_enabled 属性）
                    if hasattr(dialog_parent, 'segmentation_enabled') and hasattr(dialog_parent, 'segment_manager'):
                        print(f"DEBUG: Found SpikesDetectorDialog: {type(dialog_parent)}")
                        if dialog_parent.segmentation_enabled and dialog_parent.segment_manager is not None:
                            has_segments = True
                            num_segments = dialog_parent.segment_manager.num_segments
                            segment_manager = dialog_parent.segment_manager
                            print(f"DEBUG: Segmentation enabled with {num_segments} segments")
                        break
                    # 继续向上查找
                    dialog_parent = dialog_parent.parent() if hasattr(dialog_parent, 'parent') else None
                
                print(f"DEBUG: has_segments result: {has_segments}")
                print(f"DEBUG: num_segments: {num_segments}")
                
                if has_segments:
                    # 有 segmentation，只为包含 spikes 的 segments 生成图
                    print(f"DEBUG: Total segments: {num_segments}")
                    print(f"DEBUG: Total spikes to export: {len(self.manual_spikes)}")
                    
                    # 找出所有包含 spikes 的 segment 索引
                    segments_with_spikes = set()
                    for spike in self.manual_spikes:
                        spike_time = spike.get('time', 0)
                        print(f"DEBUG: Spike ID {spike.get('id')} at time {spike_time}")
                        
                        # 确定这个 spike 属于哪个 segment
                        for seg_idx in range(num_segments):
                            seg_info = segment_manager.get_segment_info(seg_idx)
                            if seg_info is None:
                                continue
                            
                            seg_time_start = seg_info['start_time']
                            seg_time_end = seg_info['end_time']
                            
                            if seg_time_start <= spike_time <= seg_time_end:
                                segments_with_spikes.add(seg_idx)
                                print(f"DEBUG: Spike {spike.get('id')} belongs to segment {seg_idx + 1} (time range: {seg_time_start:.3f} - {seg_time_end:.3f})")
                                break
                    
                    print(f"DEBUG: Segments with spikes: {sorted(segments_with_spikes)}")
                    print(f"DEBUG: Number of segments to export: {len(segments_with_spikes)}")
                    
                    # 只为包含 spikes 的 segments 生成图表
                    for seg_idx in sorted(segments_with_spikes):
                        print(f"DEBUG: Exporting segment {seg_idx + 1}...")
                        
                        # 获取该 segment 的数据和信息
                        seg_data = segment_manager.get_segment_data(seg_idx)
                        seg_info = segment_manager.get_segment_info(seg_idx)
                        
                        if seg_info is None:
                            print(f"DEBUG: Warning - could not get info for segment {seg_idx + 1}")
                            continue
                        
                        seg_time_start = seg_info['start_time']
                        seg_time_end = seg_info['end_time']
                        
                        print(f"DEBUG: Segment {seg_idx + 1} data length: {len(seg_data)}, time range: {seg_time_start:.3f} - {seg_time_end:.3f}")
                        
                        # 创建时间轴
                        num_samples = len(seg_data)
                        seg_time_axis = np.linspace(seg_time_start, seg_time_end, num_samples)
                        
                        # 创建图表
                        fig, ax = plt.subplots(figsize=(12, 4))
                        ax.plot(seg_time_axis, seg_data, linewidth=0.5, color='blue')
                        ax.set_xlabel('Time (s)')
                        ax.set_ylabel('Amplitude (nA)')
                        ax.set_title(f"Full Trace - Segment {seg_idx + 1}/{num_segments}")
                        ax.grid(True, alpha=0.3)
                        
                        # 统计该 segment 中的 spikes 数量
                        spikes_in_segment = 0
                        
                        # 标记该 segment 中的所有 spikes
                        for spike in self.manual_spikes:
                            spike_time = spike.get('time', 0)
                            spike_id = spike.get('id', '')
                            
                            # 检查 spike 是否在当前 segment 的时间范围内
                            if seg_time_start <= spike_time <= seg_time_end:
                                spikes_in_segment += 1
                                # 找到最接近的索引
                                spike_idx_in_seg = np.abs(seg_time_axis - spike_time).argmin()
                                spike_amp = seg_data[spike_idx_in_seg]
                                
                                print(f"DEBUG:   Marking spike {spike_id} in segment {seg_idx + 1} at time {spike_time:.3f}")
                                
                                # 标记 spike 位置
                                ax.plot(spike_time, spike_amp, 'ro', markersize=8)
                                
                                # 添加 spike ID 标签
                                ax.annotate(f'{spike_id}', 
                                          xy=(spike_time, spike_amp),
                                          xytext=(0, 10),
                                          textcoords='offset points',
                                          ha='center',
                                          fontsize=8,
                                          bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
                        
                        # 在标题中显示该 segment 的 spikes 数量
                        ax.set_title(f"Full Trace - Segment {seg_idx + 1}/{num_segments} ({spikes_in_segment} spikes)")
                        
                        # 保存图表
                        trace_plot_path = os.path.join(full_trace_folder, f"full_trace_segment_{seg_idx + 1}.png")
                        print(f"DEBUG: Saving to {trace_plot_path}")
                        fig.savefig(trace_plot_path, dpi=150, bbox_inches='tight')
                        plt.close(fig)
                        print(f"DEBUG: Successfully saved segment {seg_idx + 1}")
                else:
                    # 没有 segmentation，生成单个完整图表
                    fig, ax = plt.subplots(figsize=(14, 4))
                    ax.plot(time_axis, data_obj, linewidth=0.5, color='blue')
                    ax.set_xlabel('Time (s)')
                    ax.set_ylabel('Amplitude (nA)')
                    ax.set_title("Full Trace - All Identified Spikes")
                    ax.grid(True, alpha=0.3)
                    
                    # 标记所有 spikes
                    for spike in self.manual_spikes:
                        spike_idx = spike.get('index')
                        spike_id = spike.get('id', '')
                        
                        if spike_idx is not None and 0 <= spike_idx < len(data_obj):
                            spike_time = time_axis[spike_idx]
                            spike_amp = data_obj[spike_idx]
                            
                            # 标记 spike 位置
                            ax.plot(spike_time, spike_amp, 'ro', markersize=8)
                            
                            # 添加 spike ID 标签
                            ax.annotate(f'{spike_id}', 
                                      xy=(spike_time, spike_amp),
                                      xytext=(0, 10),
                                      textcoords='offset points',
                                      ha='center',
                                      fontsize=8,
                                      bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
                    
                    # 保存图表
                    trace_plot_path = os.path.join(full_trace_folder, "full_trace.png")
                    fig.savefig(trace_plot_path, dpi=150, bbox_inches='tight')
                    plt.close(fig)
            
            
            # Success message
            # 计算 full trace 图表数量
            if has_segments:
                num_trace_plots = len(segments_with_spikes)
            else:
                num_trace_plots = 1
            
            msg = f"Successfully exported {len(data)} peaks to:\n{export_folder}\n\n"
            msg += f"- Statistics: peaks_statistics.csv\n"
            msg += f"- Waveforms: {len(grouped_spikes)} CSV files (one per group)\n"
            msg += f"- Individual spike plots: {len(self.manual_spikes)} PNG files (organized by group)\n"
            msg += f"- Group statistics plots: {len(grouped_spikes)} PNG files\n"
            msg += f"- Full trace plots: {num_trace_plots} PNG file(s) (with spike markers)"
            
            QMessageBox.information(
                self,
                "Export Successful",
                msg
            )
            
            # 更新状态
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage(
                    f"Exported {len(data)} peaks to folder: {os.path.basename(export_folder)}"
                )
            
        except Exception as e:
            import traceback
            print(f"Error exporting peaks to folder: {e}")
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
            
            # 直接设置正确的行数，这样更可靠
            self.spikes_table.setRowCount(required_rows)
            
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
                
                # Group 列 (ComboBox)
                group_widget = QWidget()
                group_layout = QHBoxLayout(group_widget)
                group_layout.setContentsMargins(0, 0, 0, 0)
                group_combo = QComboBox()
                group_combo.addItems(self.spike_groups)
                current_group = spike.get('group', 'Default')
                
                # 确保当前组在列表中
                if current_group not in self.spike_groups:
                    self.spike_groups.append(current_group)
                    group_combo.addItem(current_group)
                
                group_combo.setCurrentText(current_group)
                
                # 连接信号
                group_combo.currentTextChanged.connect(lambda text, r=row: self.on_spike_group_changed(r, text))
                group_layout.addWidget(group_combo)
                self.spikes_table.setCellWidget(row, 4, group_widget)
                
                # 操作列 (按钮)
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(2, 2, 2, 2)
                action_layout.setSpacing(2)
                
                # 编辑按钮 - 增加宽度确保文本完整显示
                edit_btn = QPushButton("Edit")
                edit_btn.setFixedSize(70, 24)  # 进一步增加宽度和高度
                edit_btn.setStyleSheet("background-color: #2196F3; color: white; font-size: 10px;")
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_spike(r))
                
                # 删除按钮 - 增加宽度确保文本完整显示
                delete_btn = QPushButton("Del")
                delete_btn.setFixedSize(55, 24)  # 增加宽度和高度
                delete_btn.setStyleSheet("background-color: #F44336; color: white;")
                delete_btn.clicked.connect(lambda checked, r=row: self.delete_spike(r))
                
                # 跳转按钮
                goto_btn = QPushButton("→")
                goto_btn.setFixedSize(32, 24)  # 调整高度与其他按钮一致
                goto_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                goto_btn.clicked.connect(lambda checked, r=row: self.goto_spike(r))
                
                action_layout.addWidget(edit_btn)
                action_layout.addWidget(delete_btn)
                action_layout.addWidget(goto_btn)
                action_layout.addStretch()
                
                self.spikes_table.setCellWidget(row, 5, action_widget)
                
            # 恢复排序功能
            self.spikes_table.setSortingEnabled(True)
            
            # 如果表格中有数据，选择第一行
            if required_rows > 0:
                self.spikes_table.selectRow(0)
            
            # 如果pop-out窗口存在且可见,也更新它的表格
            if self.spikes_list_window is not None and self.spikes_list_window.isVisible():
                self.spikes_list_window.update_table()
            
            # 注释掉自动更新统计窗口以提高性能
            # 用户可以使用每个窗口的Refresh按钮手动更新
            # if hasattr(self, 'statistics_windows'):
            #     for group_name, window in self.statistics_windows.items():
            #         if window.isVisible():
            #             window.update_plot()
                
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
                
                # 重新编号所有 spikes
                self.renumber_spikes()
                
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
    
    def renumber_spikes(self):
        """重新为所有 spikes 分配连续的 ID"""
        for i, spike in enumerate(self.manual_spikes):
            spike['id'] = i + 1
        # 更新 spike count
        self.manual_spike_count = len(self.manual_spikes)
    
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
            # 更新属性
            self.update_peak_properties()
            
            # 高亮显示该行
            self.spikes_table.selectRow(row)
            
            # 通知用户

            
        except Exception as e:
            import traceback
            print(f"Error navigating to spike: {e}")
            traceback.print_exc()
    
    # ========== 数据分段支持方法 ==========
    
    def set_time_offset(self, offset):
        """设置时间偏移（用于分段数据显示全局时间）
        
        参数:
            offset: 时间偏移（秒）
        """
        self.time_offset = offset
    
    def get_manual_results(self):
        """获取当前手动标记结果用于保存
        
        返回:
            列表，包含所有手动标记的峰值数据
        """
        if not self.manual_spikes:
            return None
        
        # 返回手动峰值列表的深拷贝
        return [spike.copy() for spike in self.manual_spikes]
    
    def load_manual_results(self, results):
        """加载之前保存的手动标记结果
        
        参数:
            results: 列表，包含手动标记的峰值数据
        """
        if not results:
            return
        
        try:
            # 清除现有手动标记
            self.manual_spikes = []
            self.manual_spike_count = 0
            
            # 加载保存的峰值数据
            for spike_data in results:
                self.manual_spikes.append(spike_data.copy())
                self.manual_spike_count += 1
            
            # 更新表格显示
            self.update_spikes_table()
            
            # 更新峰值计数标签
            if hasattr(self, 'peak_count_label'):
                if self.manual_spike_count == 0:
                    self.peak_count_label.setText("No manual peaks")
                elif self.manual_spike_count == 1:
                    self.peak_count_label.setText(f"{self.manual_spike_count} manual peak")
                else:
                    self.peak_count_label.setText(f"{self.manual_spike_count} manual peaks")
            
            # 更新画布显示（如果有）
            if hasattr(self, 'plot_canvas') and self.plot_canvas:
                self.update_manual_plot(preserve_view=True)
            
        except Exception as e:
            print(f"Error loading manual results: {e}")
            import traceback
            traceback.print_exc()
    
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
        if hasattr(self, 'popout_list_btn'):
            self.popout_list_btn.clicked.connect(self.open_spikes_list_window)
        
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
    
    def open_spikes_list_window(self):
        """打开或显示spikes列表弹出窗口"""
        try:
            # 如果窗口已经存在，则显示并激活它
            if self.spikes_list_window is not None:
                self.spikes_list_window.show()
                self.spikes_list_window.raise_()
                self.spikes_list_window.activateWindow()
                # 更新表格内容
                self.spikes_list_window.update_table()
                return
            
            # 创建新窗口，传递 ManualSpikeSelector (self) 作为 parent_selector
            # 使用顶级对话框作为 Qt parent 以保持正确的窗口层级
            parent_dialog = self._find_detector_dialog()
            self.spikes_list_window = SpikesListWindow(parent_selector=self, parent=parent_dialog)
            
            # 更新表格内容
            self.spikes_list_window.update_table()
            
            # 显示窗口
            self.spikes_list_window.show()
            
        except Exception as e:
            import traceback
            print(f"Error opening spikes list window: {e}")
            print(traceback.format_exc())
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to open spikes list window: {str(e)}"
            )



class SpikesListWindow(QDialog):
    """独立的Spikes列表窗口"""
    
    def __init__(self, parent_selector=None, parent=None):
        super(SpikesListWindow, self).__init__(parent)
        self.parent_selector = parent_selector
        self.setWindowTitle("Spikes List")
        self.resize(800, 600)
        
        # 设置窗口标志，避免影响主窗口层级
        self.setWindowFlags(Qt.WindowType.Window)
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题和统计信息
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Manual Spikes List")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        # Manual峰值数量显示标签
        self.peak_count_label = QLabel("Manual peaks: 0")
        self.peak_count_label.setStyleSheet("font-size: 11px; color: #555;")
        header_layout.addWidget(self.peak_count_label)
        
        # Statistics 按钮
        self.statistics_btn = QPushButton("Statistics")
        self.statistics_btn.setStyleSheet("background-color: #009688; color: white; font-weight: bold;")
        self.statistics_btn.clicked.connect(self.open_statistics)
        header_layout.addWidget(self.statistics_btn)
        
        layout.addLayout(header_layout)
        
        # 创建表格控件显示spikes列表
        self.spikes_table = QTableWidget()
        self.spikes_table.setColumnCount(6)  # 增加 Group 列
        self.spikes_table.setHorizontalHeaderLabels(["ID", "Time (s)", "Amplitude (nA)", "Duration (ms)", "Group", "Actions"])
        self.spikes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.spikes_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.spikes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # 设置列宽
        header = self.spikes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 时间列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 振幅列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 持续时间列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Group列
        
        # 操作列设置为固定宽度，确保按钮不重叠
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.spikes_table.setColumnWidth(5, 200)  # 增加到200px确保按钮不重叠
        
        # 添加排序功能
        self.spikes_table.setSortingEnabled(True)
        
        layout.addWidget(self.spikes_table)
        
        # 创建排序控件
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Sort by:"))
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["ID", "Time", "Amplitude", "Duration"])
        sort_layout.addWidget(self.sort_combo)
        
        self.sort_order_check = QCheckBox("Descending")
        sort_layout.addWidget(self.sort_order_check)
        
        sort_layout.addStretch(1)
        
        layout.addLayout(sort_layout)
        
        # 底部按钮
        buttons_layout = QHBoxLayout()
        
        # 删除功能按钮
        self.delete_all_btn = QPushButton("Delete All Spikes")
        self.delete_all_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.delete_all_btn.clicked.connect(self.delete_all_spikes)
        buttons_layout.addWidget(self.delete_all_btn)
        
        # 按 Group 删除
        delete_group_layout = QHBoxLayout()
        delete_group_layout.addWidget(QLabel("Delete by Group:"))
        self.delete_group_combo = QComboBox()
        self.delete_group_combo.setMinimumWidth(120)
        delete_group_layout.addWidget(self.delete_group_combo)
        
        self.delete_group_btn = QPushButton("Delete")
        self.delete_group_btn.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        self.delete_group_btn.clicked.connect(self.delete_spikes_by_group)
        delete_group_layout.addWidget(self.delete_group_btn)
        
        buttons_layout.addLayout(delete_group_layout)
        
        buttons_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)
        
        layout.addLayout(buttons_layout)
    
    def connect_signals(self):
        """连接信号"""
        # 排序控件
        if hasattr(self, 'sort_combo') and hasattr(self, 'sort_order_check'):
            self.sort_combo.currentIndexChanged.connect(self.apply_sort)
            self.sort_order_check.stateChanged.connect(self.apply_sort)
        
        # 表格头部点击
        if hasattr(self, 'spikes_table'):
            self.spikes_table.horizontalHeader().sectionClicked.connect(self.on_table_header_clicked)
    
    def update_table(self):
        """更新表格显示"""
        if not self.parent_selector:
            return
            
        try:
            # 断开排序信号以避免刷新表格时触发排序
            self.spikes_table.setSortingEnabled(False)
            
            # 获取父窗口的spikes数据
            manual_spikes = self.parent_selector.manual_spikes
            
            # 更新计数标签 - 使用正确的属性名
            count_label = self.peak_count_label if hasattr(self, 'peak_count_label') else None
            if count_label:
                if len(manual_spikes) > 0:
                    count_label.setText(f"Manual peaks: {len(manual_spikes)}")
                else:
                    count_label.setText("Manual peaks: 0")
            
            # 更新 delete group combo box
            if hasattr(self, 'delete_group_combo'):
                # 获取所有唯一的 groups
                groups = set()
                for spike in manual_spikes:
                    groups.add(spike.get('group', 'Default'))
                
                # 更新 combo box
                self.delete_group_combo.clear()
                for group in sorted(groups):
                    self.delete_group_combo.addItem(group)
            
            # 获取当前行数
            current_rows = self.spikes_table.rowCount()
            required_rows = len(manual_spikes)
            
            # 直接设置正确的行数，这样更可靠
            self.spikes_table.setRowCount(required_rows)
            
            # 填充或更新表格数据
            for row, spike in enumerate(manual_spikes):
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
                
                # Group 列 (ComboBox)
                group_widget = QWidget()
                group_layout = QHBoxLayout(group_widget)
                group_layout.setContentsMargins(0, 0, 0, 0)
                group_combo = QComboBox()
                group_combo.addItems(self.parent_selector.spike_groups)
                current_group = spike.get('group', 'Default')
                
                # 确保当前组在列表中
                if current_group not in self.parent_selector.spike_groups:
                    self.parent_selector.spike_groups.append(current_group)
                    group_combo.addItem(current_group)
                
                group_combo.setCurrentText(current_group)
                
                # 连接信号
                group_combo.currentTextChanged.connect(lambda text, r=row: self.parent_selector.on_spike_group_changed(r, text))
                group_layout.addWidget(group_combo)
                self.spikes_table.setCellWidget(row, 4, group_widget)
                
                # 操作列 (按钮)
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(2, 2, 2, 2)
                action_layout.setSpacing(2)
                
                # 编辑按钮
                edit_btn = QPushButton("Edit")
                edit_btn.setFixedSize(70, 24)  # 与主窗口按钮保持一致
                edit_btn.setStyleSheet("background-color: #2196F3; color: white; font-size: 10px;")
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_spike(r))
                
                # 删除按钮
                delete_btn = QPushButton("Del")
                delete_btn.setFixedSize(55, 24)  # 与主窗口按钮保持一致
                delete_btn.setStyleSheet("background-color: #F44336; color: white;")
                delete_btn.clicked.connect(lambda checked, r=row: self.delete_spike(r))
                
                # 跳转按钮
                goto_btn = QPushButton("→")
                goto_btn.setFixedSize(32, 24)  # 与主窗口按钮保持一致
                goto_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                goto_btn.clicked.connect(lambda checked, r=row: self.goto_spike(r))
                
                action_layout.addWidget(edit_btn)
                action_layout.addWidget(delete_btn)
                action_layout.addWidget(goto_btn)
                action_layout.addStretch()
                
                self.spikes_table.setCellWidget(row, 5, action_widget)
            
            # 恢复排序功能
            self.spikes_table.setSortingEnabled(True)
            
            # 如果表格中有数据，选择第一行
            if required_rows > 0:
                self.spikes_table.selectRow(0)
                
        except Exception as e:
            import traceback
            print(f"Error updating spikes table in pop-out window: {e}")
            print(traceback.format_exc())
    
    def edit_spike(self, row):
        """编辑指定行的spike"""
        if self.parent_selector:
            self.parent_selector.edit_spike(row)
    
    def delete_spike(self, row):
        """删除指定行的spike"""
        if self.parent_selector:
            self.parent_selector.delete_spike(row)
    
    def goto_spike(self, row):
        """跳转到指定的spike"""
        if self.parent_selector:
            self.parent_selector.goto_spike(row)
    
    def apply_sort(self):
        """应用排序"""
        if not self.parent_selector:
            return
            
        # 获取排序列和顺序
        sort_column_name = self.sort_combo.currentText()
        descending = self.sort_order_check.isChecked()
        
        # 映射列名到索引
        column_map = {
            "ID": 0,
            "Time": 1,
            "Amplitude": 2,
            "Duration": 3
        }
        
        column = column_map.get(sort_column_name, 0)
        order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
        
        # 对表格进行排序
        self.spikes_table.sortItems(column, order)
    
    def on_table_header_clicked(self, logical_index):
        """处理表头点击事件"""
        # 根据点击的列进行排序
        current_order = self.spikes_table.horizontalHeader().sortIndicatorOrder()
        new_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        self.spikes_table.sortItems(logical_index, new_order)
    
    def open_statistics(self):
        """打开统计分析对话框 - 每个组一个独立窗口"""
        if not self.parent_selector or not self.parent_selector.manual_spikes:
            QMessageBox.information(self, "No Data", "No spikes available for statistics.")
            return
        
        # 按组分组spikes
        grouped_spikes = {}
        for spike in self.parent_selector.manual_spikes:
            group = spike.get('group', 'Default')
            if group not in grouped_spikes:
                grouped_spikes[group] = []
            grouped_spikes[group].append(spike)
        
        # 过滤掉空组
        grouped_spikes = {k: v for k, v in grouped_spikes.items() if v}
        
        if not grouped_spikes:
            QMessageBox.information(self, "No Data", "No spikes in any group.")
            return
        
        # 如果没有statistics_windows属性，创建它
        if not hasattr(self.parent_selector, 'statistics_windows'):
            self.parent_selector.statistics_windows = {}
        
        # 为每个组创建或更新统计窗口
        for group_name, group_spikes in grouped_spikes.items():
            # 如果该组的窗口已经存在且可见，激活它
            if group_name in self.parent_selector.statistics_windows:
                window = self.parent_selector.statistics_windows[group_name]
                if window.isVisible():
                    window.raise_()
                    window.activateWindow()
                    window.update_plot()  # 更新现有窗口
                    continue
            
            # 找到顶级对话框作为 parent
            parent_dialog = self.parent()
            while parent_dialog is not None:
                if hasattr(parent_dialog, 'segmentation_enabled') and hasattr(parent_dialog, 'segment_manager'):
                    break
                parent_dialog = parent_dialog.parent() if hasattr(parent_dialog, 'parent') else None
            
            # 创建新窗口
            window = GroupStatisticsWindow(
                group_name,
                self.parent_selector,
                parent_dialog if parent_dialog else self
            )
            self.parent_selector.statistics_windows[group_name] = window
            window.show()
    
    def delete_all_spikes(self):
        """删除所有 spikes"""
        if not self.parent_selector or not self.parent_selector.manual_spikes:
            QMessageBox.information(self, "No Spikes", "No spikes to delete.")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "Confirm Delete All",
            f"Are you sure you want to delete all {len(self.parent_selector.manual_spikes)} spikes?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 清除所有 spikes
            self.parent_selector.manual_spikes.clear()
            self.parent_selector.manual_spike_count = 0
            
            # 更新主窗口的显示
            if hasattr(self.parent_selector, 'peak_count_label'):
                self.parent_selector.peak_count_label.setText("No manual peaks")
            
            # 更新绘图
            if hasattr(self.parent_selector, 'update_manual_plot'):
                self.parent_selector.update_manual_plot()
            
            # 更新本窗口的表格
            self.update_table()
            
            QMessageBox.information(self, "Success", "All spikes have been deleted.")
    
    def delete_spikes_by_group(self):
        """按 Group 删除 spikes"""
        if not self.parent_selector or not self.parent_selector.manual_spikes:
            QMessageBox.information(self, "No Spikes", "No spikes to delete.")
            return
        
        # 获取选中的 group
        if not hasattr(self, 'delete_group_combo') or self.delete_group_combo.count() == 0:
            QMessageBox.information(self, "No Groups", "No groups available.")
            return
        
        selected_group = self.delete_group_combo.currentText()
        
        # 统计该 group 中的 spikes 数量
        spikes_in_group = [s for s in self.parent_selector.manual_spikes if s.get('group', 'Default') == selected_group]
        
        if not spikes_in_group:
            QMessageBox.information(self, "No Spikes", f"No spikes in group '{selected_group}'.")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "Confirm Delete by Group",
            f"Are you sure you want to delete {len(spikes_in_group)} spikes in group '{selected_group}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 删除该 group 的所有 spikes
            self.parent_selector.manual_spikes = [
                s for s in self.parent_selector.manual_spikes 
                if s.get('group', 'Default') != selected_group
            ]
            
            # 重新编号所有 spikes
            if hasattr(self.parent_selector, 'renumber_spikes'):
                self.parent_selector.renumber_spikes()
            else:
                # 如果没有 renumber_spikes 方法，手动更新 count
                self.parent_selector.manual_spike_count = len(self.parent_selector.manual_spikes)
            
            # 更新主窗口的显示
            if hasattr(self.parent_selector, 'peak_count_label'):
                if self.parent_selector.manual_spike_count > 0:
                    self.parent_selector.peak_count_label.setText(f"Manual peaks: {self.parent_selector.manual_spike_count}")
                else:
                    self.parent_selector.peak_count_label.setText("No manual peaks")
            
            # 更新绘图
            if hasattr(self.parent_selector, 'update_manual_plot'):
                self.parent_selector.update_manual_plot()
            
            # 更新本窗口的表格
            self.update_table()
            
            QMessageBox.information(self, "Success", f"Deleted {len(spikes_in_group)} spikes from group '{selected_group}'.")
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 通知父窗口，pop-out窗口已关闭
        if self.parent_selector and hasattr(self.parent_selector, 'spikes_list_window'):
            self.parent_selector.spikes_list_window = None
        super().closeEvent(event)


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


class GroupStatisticsWindow(QDialog):
    """单个组的统计分析窗口 - 可实时更新"""
    def __init__(self, group_name, parent_selector, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.parent_selector = parent_selector
        
        self.setWindowTitle(f"Statistics - {group_name}")
        self.resize(1000, 500)
        
        # 设置窗口标志，避免影响主窗口层级
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.setup_ui()
        self.connect_signals()
        self.update_plot()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建matplotlib画布
        self.figure = Figure(figsize=(10, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # 添加拟合信息显示区域
        self.fit_info_label = QLabel()
        self.fit_info_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 10pt;
            }
        """)
        self.fit_info_label.setWordWrap(True)
        self.fit_info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.fit_info_label.setMinimumHeight(35)
        self.fit_info_label.setMaximumHeight(45)
        self.fit_info_label.setText("Fit statistics will be displayed here when fit curves are enabled.")
        layout.addWidget(self.fit_info_label)
        
        # 底部按钮和控件
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_plot)
        btn_layout.addWidget(refresh_btn)
        
        # Bin number 控件
        btn_layout.addWidget(QLabel("Bins:"))
        self.bin_spinbox = QSpinBox()
        self.bin_spinbox.setRange(5, 500)
        self.bin_spinbox.setValue(15)
        self.bin_spinbox.setFixedWidth(60)
        self.bin_spinbox.valueChanged.connect(self.update_plot)
        btn_layout.addWidget(self.bin_spinbox)
        
        # Duration Fit 控件
        btn_layout.addWidget(QLabel("  Duration Fit:"))
        self.duration_fit_check = QCheckBox("Show")
        self.duration_fit_check.setChecked(True)
        self.duration_fit_check.stateChanged.connect(self.update_plot)
        btn_layout.addWidget(self.duration_fit_check)
        
        self.duration_fit_type = QComboBox()
        self.duration_fit_type.addItems(["Gaussian", "Log-Normal", "Exponential"])
        self.duration_fit_type.setFixedWidth(100)
        self.duration_fit_type.currentIndexChanged.connect(self.update_plot)
        btn_layout.addWidget(self.duration_fit_type)
        
        # Amplitude Fit 控件
        btn_layout.addWidget(QLabel("  Amplitude Fit:"))
        self.amplitude_fit_check = QCheckBox("Show")
        self.amplitude_fit_check.setChecked(True)
        self.amplitude_fit_check.stateChanged.connect(self.update_plot)
        btn_layout.addWidget(self.amplitude_fit_check)
        
        self.amplitude_fit_type = QComboBox()
        self.amplitude_fit_type.addItems(["Gaussian", "Log-Normal", "Exponential"])
        self.amplitude_fit_type.setFixedWidth(100)
        self.amplitude_fit_type.currentIndexChanged.connect(self.update_plot)
        btn_layout.addWidget(self.amplitude_fit_type)
        
        btn_layout.addStretch()
        
        copy_btn = QPushButton("Copy")
        copy_btn.setToolTip("Copy plot and fit statistics to clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def copy_to_clipboard(self):
        """复制图表和拟合信息到剪贴板"""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QClipboard
            from io import BytesIO
            
            # 获取剪贴板
            clipboard = QApplication.clipboard()
            
            # 保存图表为图像
            buf = BytesIO()
            self.figure.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            # 读取图像数据
            from PyQt6.QtGui import QImage, QPixmap
            image = QImage()
            image.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(image)
            
            # 获取拟合统计文本
            fit_text = self.fit_info_label.text()
            
            # 组合文本信息
            combined_text = f"Statistics - {self.group_name}\n\n{fit_text}"
            
            # 设置剪贴板内容（图像 + 文本）
            from PyQt6.QtCore import QMimeData
            mime_data = QMimeData()
            mime_data.setImageData(pixmap)
            mime_data.setText(combined_text)
            clipboard.setMimeData(mime_data)
            
            # 显示成功消息
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Copy Success", 
                                   "Plot and fit statistics copied to clipboard!\n\n"
                                   "You can paste the image into documents or image editors,\n"
                                   "and the text into text editors.")
            
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Copy Failed", f"Failed to copy to clipboard:\n{str(e)}")
        
    def connect_signals(self):
        """连接信号以实现实时更新"""
        # 注释掉自动更新以提高性能
        # 用户可以使用Refresh按钮手动更新
        # 连接到ManualSpikeSelector的信号
        # if self.parent_selector:
        #     # 当添加、删除或更新spike时，刷新统计图
        #     if hasattr(self.parent_selector, 'peak_added'):
        #         self.parent_selector.peak_added.connect(self.on_spike_changed)
        #     if hasattr(self.parent_selector, 'peak_deleted'):
        #         self.parent_selector.peak_deleted.connect(self.on_spike_changed)
        #     if hasattr(self.parent_selector, 'peak_updated'):
        #         self.parent_selector.peak_updated.connect(self.on_spike_changed)
        pass
    
    def on_spike_changed(self, *args):
        """当spike数据变化时更新图表"""
        self.update_plot()
        
    def update_plot(self):
        """更新统计图表"""
        # 获取当前组的spikes
        group_spikes = [s for s in self.parent_selector.manual_spikes if s.get('group') == self.group_name]
        
        if not group_spikes:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, f"No spikes in {self.group_name}", 
                   ha='center', va='center', fontsize=14)
            self.canvas.draw()
            return
        
        # 清除现有图表
        self.figure.clear()
        
        # Plot 1: 叠加的spikes波形 (左, 40%)
        # Plot 2: 散点图 + 边缘直方图 (右, 60%)
        ax1 = self.figure.add_subplot(1, 2, 1)
        self.plot_overlaid_spikes(ax1, group_spikes)
        
        ax2_main = self.figure.add_subplot(1, 2, 2)
        self.plot_scatter_with_histograms(ax2_main, group_spikes)
        
        # 调整布局，增加子图之间的间距
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.92, bottom=0.1, wspace=0.35)
        self.canvas.draw()
    
    def _fit_curve(self, data, bins, fit_type, orientation='vertical'):
        """
        计算拟合曲线
        
        Parameters:
        - data: 数据数组
        - bins: bin的数量
        - fit_type: 拟合类型 ("Gaussian", "Log-Normal", "Exponential")
        - orientation: 方向 ('vertical' or 'horizontal')
        
        Returns:
        - (x_values, y_values, params_dict): 拟合曲线的坐标和参数字典
        """
        try:
            from scipy import stats
            
            # 过滤掉无效数据
            data = np.array(data)
            data = data[np.isfinite(data)]
            
            if len(data) < 3:
                return None, None, None
            
            # 计算直方图以获取数据范围和bin宽度
            counts, bin_edges = np.histogram(data, bins=bins)
            bin_width = bin_edges[1] - bin_edges[0]
            
            # 生成平滑的x值用于绘制曲线
            x_min, x_max = data.min(), data.max()
            x_range = x_max - x_min
            x_smooth = np.linspace(x_min - 0.1 * x_range, x_max + 0.1 * x_range, 200)
            
            params_dict = {}
            
            # 根据拟合类型计算PDF
            if fit_type == "Gaussian":
                mu, std = stats.norm.fit(data)
                pdf = stats.norm.pdf(x_smooth, mu, std)
                params_dict = {'mean': mu, 'std': std}
                
            elif fit_type == "Log-Normal":
                # Log-Normal需要正值数据
                if np.any(data <= 0):
                    # 如果有非正值，偏移数据
                    data_shifted = data - data.min() + 0.001
                    shape, loc, scale = stats.lognorm.fit(data_shifted, floc=0)
                    pdf = stats.lognorm.pdf(x_smooth - data.min() + 0.001, shape, loc, scale)
                    params_dict = {'shape': shape, 'loc': loc, 'scale': scale, 'offset': data.min() - 0.001}
                else:
                    shape, loc, scale = stats.lognorm.fit(data, floc=0)
                    pdf = stats.lognorm.pdf(x_smooth, shape, loc, scale)
                    params_dict = {'shape': shape, 'loc': loc, 'scale': scale}
                    
            elif fit_type == "Exponential":
                # Exponential需要非负数据
                if np.any(data < 0):
                    # 偏移到非负
                    data_shifted = data - data.min()
                    loc, scale = stats.expon.fit(data_shifted)
                    pdf = stats.expon.pdf(x_smooth - data.min(), loc, scale)
                    params_dict = {'loc': loc, 'scale': scale, 'offset': data.min()}
                else:
                    loc, scale = stats.expon.fit(data)
                    pdf = stats.expon.pdf(x_smooth, loc, scale)
                    params_dict = {'loc': loc, 'scale': scale}
            else:
                return None, None, None
            
            # 将PDF缩放到直方图的尺度（总计数 × bin宽度）
            y_smooth = pdf * len(data) * bin_width
            
            return x_smooth, y_smooth, params_dict
            
        except Exception as e:
            print(f"Warning: Failed to fit {fit_type} curve: {e}")
            return None, None, None
    
    def _update_fit_info(self, duration_params, amplitude_params):
        """更新拟合信息显示（横向排列）"""
        if not hasattr(self, 'fit_info_label'):
            return
        
        duration_text = ""
        amplitude_text = ""
        
        # Duration拟合信息
        if duration_params is not None:
            duration_fit_type = self.duration_fit_type.currentText()
            
            if duration_fit_type == "Gaussian":
                params_str = f"Mean={duration_params['mean']:.4f}ms, Std={duration_params['std']:.4f}ms"
            elif duration_fit_type == "Log-Normal":
                params_str = f"Shape={duration_params['shape']:.4f}, Scale={duration_params['scale']:.4f}"
            elif duration_fit_type == "Exponential":
                params_str = f"Scale={duration_params['scale']:.4f}, Rate={1/duration_params['scale']:.4f}"
            else:
                params_str = ""
            
            duration_text = f"📊 Duration ({duration_fit_type}): {params_str}"
        
        # Amplitude拟合信息
        if amplitude_params is not None:
            amplitude_fit_type = self.amplitude_fit_type.currentText()
            
            if amplitude_fit_type == "Gaussian":
                params_str = f"Mean={amplitude_params['mean']:.4f}nA, Std={amplitude_params['std']:.4f}nA"
            elif amplitude_fit_type == "Log-Normal":
                params_str = f"Shape={amplitude_params['shape']:.4f}, Scale={amplitude_params['scale']:.4f}"
            elif amplitude_fit_type == "Exponential":
                params_str = f"Scale={amplitude_params['scale']:.4f}, Rate={1/amplitude_params['scale']:.4f}"
            else:
                params_str = ""
            
            amplitude_text = f"📊 Amplitude ({amplitude_fit_type}): {params_str}"
        
        # 横向组合显示
        if duration_text and amplitude_text:
            display_text = f"{duration_text}    |    {amplitude_text}"
        elif duration_text:
            display_text = duration_text
        elif amplitude_text:
            display_text = amplitude_text
        else:
            display_text = "Fit statistics will be displayed here when fit curves are enabled."
        
        self.fit_info_label.setText(display_text)
        
    def plot_overlaid_spikes(self, ax, spikes):
        """绘制叠加的spike波形（时间从0开始）"""
        ax.set_title(f"{self.group_name} - Overlaid Spikes ({len(spikes)} spikes)")
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Amplitude (nA)")
        
        # 获取数据和采样率
        if not self.parent_selector.plot_canvas:
            return
        
        data = self.parent_selector.plot_canvas.current_channel_data
        sampling_rate = self.parent_selector.plot_canvas.sampling_rate
        
        if data is None or sampling_rate is None:
            return
        
        for spike in spikes:
            # 获取spike的起止索引
            start_idx = spike.get('start_idx')
            end_idx = spike.get('end_idx')
            
            if start_idx is None or end_idx is None:
                continue
            
            # 提取波形数据
            waveform = data[start_idx:end_idx+1]
            
            # 创建时间轴（从0开始，单位：毫秒）
            duration_samples = len(waveform)
            time_ms = np.arange(duration_samples) / (sampling_rate / 1000.0)
            
            # 绘制波形
            ax.plot(time_ms, waveform, alpha=0.5, linewidth=0.8)
        
        ax.grid(True, alpha=0.3)
        
    def plot_scatter_with_histograms(self, ax_main, spikes):
        """绘制散点图并添加边缘直方图"""
        # 提取duration和amplitude数据
        durations = []
        amplitudes = []
        for spike in spikes:
            dur = spike.get('duration', 0) * 1000  # 转为毫秒
            amp = spike.get('amplitude', 0)
            durations.append(dur)
            amplitudes.append(amp)
        
        if not durations or not amplitudes:
            return
        
        # 使用gridspec创建子图布局以确保对齐
        from matplotlib.gridspec import GridSpec
        
        # 获取ax_main的位置
        pos = ax_main.get_position()
        
        # 移除原来的ax_main
        ax_main.remove()
        
        # 创建gridspec布局 (3x3, 但只使用部分)
        # height_ratios: [histogram_height, gap, scatter_height]
        # width_ratios: [scatter_width, gap, histogram_width]
        gs = GridSpec(3, 3, 
                     left=pos.x0, right=pos.x0 + pos.width,
                     bottom=pos.y0, top=pos.y0 + pos.height,
                     height_ratios=[0.2, 0.02, 1],
                     width_ratios=[1, 0.02, 0.2],
                     hspace=0, wspace=0,
                     figure=self.figure)
        
        # 创建散点图 (bottom-left)
        ax_scatter = self.figure.add_subplot(gs[2, 0])
        ax_scatter.scatter(durations, amplitudes, alpha=0.6, s=30, edgecolors='black', linewidth=0.5)
        ax_scatter.set_xlabel("Duration (ms)")
        ax_scatter.set_ylabel("Amplitude (nA)")
        ax_scatter.set_title(f"{self.group_name} - Duration vs Amplitude")
        ax_scatter.grid(True, alpha=0.3)
        
        # 创建上方直方图 (top-left, 与散点图x轴对齐)
        ax_top = self.figure.add_subplot(gs[0, 0], sharex=ax_scatter)
        bins = self.bin_spinbox.value() if hasattr(self, 'bin_spinbox') else 15
        ax_top.hist(durations, bins=bins, alpha=0.7, edgecolor='black')
        ax_top.set_ylabel("Count", fontsize=9)
        ax_top.tick_params(axis='x', labelbottom=False)  # 隐藏x轴标签
        ax_top.tick_params(axis='y', labelsize=8)
        
        # 收集拟合信息
        fit_info_parts = []
        
        # 添加Duration拟合曲线
        duration_params = None
        if hasattr(self, 'duration_fit_check') and self.duration_fit_check.isChecked():
            fit_type = self.duration_fit_type.currentText()
            x_fit, y_fit, duration_params = self._fit_curve(durations, bins, fit_type, 'vertical')
            if x_fit is not None and y_fit is not None:
                ax_top.plot(x_fit, y_fit, 'r-', linewidth=2, alpha=0.8, label=f'{fit_type} Fit')
                ax_top.legend(fontsize=8, loc='upper right')
        
        # 创建右方直方图 (bottom-right, 与散点图y轴对齐)
        ax_right = self.figure.add_subplot(gs[2, 2], sharey=ax_scatter)
        ax_right.hist(amplitudes, bins=bins, orientation='horizontal', alpha=0.7, edgecolor='black')
        ax_right.set_xlabel("Count", fontsize=9)
        ax_right.tick_params(axis='y', labelleft=False)  # 隐藏y轴标签
        ax_right.tick_params(axis='x', labelsize=8)
        
        # 添加Amplitude拟合曲线
        amplitude_params = None
        if hasattr(self, 'amplitude_fit_check') and self.amplitude_fit_check.isChecked():
            fit_type = self.amplitude_fit_type.currentText()
            y_fit, x_fit, amplitude_params = self._fit_curve(amplitudes, bins, fit_type, 'horizontal')
            if x_fit is not None and y_fit is not None:
                ax_right.plot(x_fit, y_fit, 'r-', linewidth=2, alpha=0.8, label=f'{fit_type} Fit')
                ax_right.legend(fontsize=8, loc='upper right')
        
        # 更新拟合信息显示
        self._update_fit_info(duration_params, amplitude_params)


class GroupManagerDialog(QDialog):
    """组管理对话框"""
    def __init__(self, current_groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Groups")
        self.setFixedSize(350, 450)
        self.groups = list(current_groups)
        
        # 设置窗口标志，避免影响主窗口层级
        self.setWindowFlags(Qt.WindowType.Window)
        
        layout = QVBoxLayout(self)
        
        # 组列表
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.groups)
        self.list_widget.itemDoubleClicked.connect(self.rename_group_item)
        layout.addWidget(self.list_widget)
        
        # 添加组
        add_layout = QHBoxLayout()
        self.new_group_input = QLineEdit()
        self.new_group_input.setPlaceholderText("New Group Name")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_group)
        add_layout.addWidget(self.new_group_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        
        # 重命名按钮
        rename_btn = QPushButton("Rename Selected")
        rename_btn.clicked.connect(self.rename_group)
        btn_layout.addWidget(rename_btn)
        
        # 删除组
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_group)
        btn_layout.addWidget(del_btn)
        
        layout.addLayout(btn_layout)
        
        # 确认按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def add_group(self):
        name = self.new_group_input.text().strip()
        if name and name not in self.groups:
            self.groups.append(name)
            self.list_widget.addItem(name)
            self.new_group_input.clear()
    
    def rename_group(self):
        """通过按钮重命名选中的组"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.rename_group_item(self.list_widget.item(current_row))
    
    def rename_group_item(self, item):
        """重命名组（支持双击和按钮）"""
        if item is None:
            return
        
        old_name = item.text()
        new_name, ok = QLineEdit().text(), False
        
        # 创建输入对话框
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Group",
            f"Enter new name for '{old_name}':",
            QLineEdit.EchoMode.Normal,
            old_name
        )
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name != old_name and new_name not in self.groups:
                # 更新列表
                row = self.groups.index(old_name)
                self.groups[row] = new_name
                item.setText(new_name)
            elif new_name in self.groups and new_name != old_name:
                QMessageBox.warning(self, "Warning", f"Group '{new_name}' already exists")
            
    def delete_group(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            # 移除了Default组的保护，现在可以删除任何组
            self.groups.pop(current_row)
            self.list_widget.takeItem(current_row)
            
    def get_groups(self):
        return self.groups