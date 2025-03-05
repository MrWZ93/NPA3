#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Detector Module - 自动峰值检测模块
实现自动峰值检测和持续时间计算的功能
"""

import os
import numpy as np
from scipy import signal
import pandas as pd

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QFileDialog, QMessageBox, QGroupBox, QSplitter, QRadioButton,
                            QButtonGroup, QApplication, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar


class PeakDetectionWorker(QObject):
    """峰值检测工作线程"""
    finished = pyqtSignal(list)  # 完成信号，返回峰值索引
    progress = pyqtSignal(int)   # 进度信号
    
    def __init__(self, data, threshold, min_distance, method="threshold"):
        super().__init__()
        # 确保数据是副本以防止引用问题
        if isinstance(data, np.ndarray):
            self.data = np.array(data, copy=True)
        else:
            self.data = data
            
        self.threshold = threshold
        self.min_distance = max(1, int(min_distance))  # 确保最小距离至少为1
        self.method = method
        self._should_abort = False  # 添加中止标志

    def abort(self):
        """设置中止标志"""
        self._should_abort = True
    
    def run(self):
        """执行峰值检测"""
        try:
            if self.method == "threshold":
                # 基于阈值的简单峰值检测
                peaks_indices = []
                
                # 确定我们是寻找正峰值还是负峰值
                is_positive_threshold = self.threshold >= 0
                
                for i in range(1, len(self.data)-1):
                    # 检查中止标志
                    if self._should_abort:
                        print("Peak detection aborted")
                        self.finished.emit([])
                        return
                        
                    if is_positive_threshold:
                        # 检测正峰值（大于阈值的局部最大值）
                        if self.data[i] > self.threshold:
                            if self.data[i] > self.data[i-1] and self.data[i] >= self.data[i+1]:
                                # 是一个局部最大值
                                if not peaks_indices or i - peaks_indices[-1] >= self.min_distance:
                                    peaks_indices.append(i)
                    else:
                        # 检测负峰值（小于阈值的局部最小值）
                        if self.data[i] < self.threshold:
                            if self.data[i] < self.data[i-1] and self.data[i] <= self.data[i+1]:
                                # 是一个局部最小值
                                if not peaks_indices or i - peaks_indices[-1] >= self.min_distance:
                                    peaks_indices.append(i)
                    
                    # 每处理10%的数据发出进度信号
                    if i % max(1, len(self.data) // 10) == 0:
                        progress = int(i / len(self.data) * 100)
                        self.progress.emit(progress)
            
            elif self.method == "scipy":
                # 使用scipy的峰值检测
                if self.threshold >= 0:
                    # 寻找正峰值 - 添加错误处理
                    try:
                        peaks_indices, _ = signal.find_peaks(
                            self.data, 
                            height=self.threshold,
                            distance=self.min_distance
                        )
                    except Exception as e:
                        print(f"Error in scipy peak detection: {e}")
                        # 回退到简单阈值方法
                        peaks_indices = []
                        for i in range(1, len(self.data)-1):
                            if self._should_abort:
                                break
                            if self.data[i] > self.threshold:
                                if self.data[i] > self.data[i-1] and self.data[i] >= self.data[i+1]:
                                    if not peaks_indices or i - peaks_indices[-1] >= self.min_distance:
                                        peaks_indices.append(i)
                else:
                    # 寻找负峰值，需要取相反数并找到最大值
                    # 将阈值取绝对值，因为我们需要找小于负阈值的点
                    try:
                        abs_threshold = abs(self.threshold)
                        peaks_indices, _ = signal.find_peaks(
                            -self.data,  # 取相反数，将负峰值转换为正峰值
                            height=abs_threshold,
                            distance=self.min_distance
                        )
                    except Exception as e:
                        print(f"Error in scipy negative peak detection: {e}")
                        # 回退到简单阈值方法
                        peaks_indices = []
                        for i in range(1, len(self.data)-1):
                            if self._should_abort:
                                break
                            if self.data[i] < self.threshold:
                                if self.data[i] < self.data[i-1] and self.data[i] <= self.data[i+1]:
                                    if not peaks_indices or i - peaks_indices[-1] >= self.min_distance:
                                        peaks_indices.append(i)
                
                self.progress.emit(100)
            
            self.finished.emit(peaks_indices)
        
        except Exception as e:
            import traceback
            print(f"Error in peak detection: {str(e)}")
            print(traceback.format_exc())
            self.finished.emit([])


class PeakDurationWorker(QObject):
    """峰值持续时间计算工作线程"""
    finished = pyqtSignal(dict)  # 完成信号，返回每个峰值的持续时间数据
    progress = pyqtSignal(int)   # 进度信号
    
    def __init__(self, data, peaks_indices, threshold_ratio=0.5):
        super().__init__()
        # 确保数据是副本以防止引用问题
        if isinstance(data, np.ndarray):
            self.data = np.array(data, copy=True)
        else:
            self.data = data
            
        # 确保峰值索引也是副本
        self.peaks_indices = np.array(peaks_indices, copy=True)
        self.threshold_ratio = threshold_ratio  # 峰值高度的比例，用于确定起点和终点
        self._should_abort = False  # 添加中止标志
    
    def abort(self):
        """设置中止标志"""
        self._should_abort = True
    
    def run(self):
        """计算每个峰值的持续时间"""
        try:
            peaks_durations = {}
            
            for i, peak_idx in enumerate(self.peaks_indices):
                # 检查中止标志
                if self._should_abort:
                    print("Duration calculation aborted")
                    self.finished.emit({})
                    return
                    
                # 确保索引在有效范围内
                if peak_idx < 0 or peak_idx >= len(self.data):
                    continue
                    
                peak_value = self.data[peak_idx]
                # 根据峰值是正还是负来确定阈值计算方式
                is_positive_peak = peak_value >= 0
                
                # 设置默认值
                start_idx = max(0, peak_idx - 10)
                end_idx = min(len(self.data) - 1, peak_idx + 10)
                
                if is_positive_peak:
                    # 正峰值，阈值是峰值的一定比例
                    threshold = peak_value * self.threshold_ratio
                    
                    # 向后搜索结束点
                    end_idx = peak_idx
                    for j in range(peak_idx, min(len(self.data), peak_idx + 1000)):
                        if self.data[j] < threshold:
                            end_idx = j
                            break
                    
                    # 向前搜索起始点
                    start_idx = peak_idx
                    for j in range(peak_idx, max(0, peak_idx - 1000), -1):
                        if self.data[j] < threshold:
                            start_idx = j
                            break
                else:
                    # 负峰值，阈值是峰值加上其绝对值的一定比例
                    # 例如，如果峰值是-10，阈值比例是0.5，那么阈值就是 -10 + |-10| * 0.5 = -5
                    threshold = peak_value + abs(peak_value) * (1 - self.threshold_ratio)
                    
                    # 向后搜索结束点
                    end_idx = peak_idx
                    for j in range(peak_idx, min(len(self.data), peak_idx + 1000)):
                        if self.data[j] > threshold:
                            end_idx = j
                            break
                    
                    # 向前搜索起始点
                    start_idx = peak_idx
                    for j in range(peak_idx, max(0, peak_idx - 1000), -1):
                        if self.data[j] > threshold:
                            start_idx = j
                            break
                
                # 存储结果
                peaks_durations[i] = {
                    'start_idx': start_idx,
                    'peak_idx': peak_idx,
                    'end_idx': end_idx
                }
                
                # 每处理10%的峰值发出进度信号
                if len(self.peaks_indices) > 0:
                    progress = int((i+1) / len(self.peaks_indices) * 100)
                    self.progress.emit(progress)
            
            self.progress.emit(100)
            self.finished.emit(peaks_durations)
            
        except Exception as e:
            import traceback
            print(f"Error in duration calculation: {str(e)}")
            print(traceback.format_exc())
            self.finished.emit({})


class AutoSpikeDetector(QWidget):
    """自动峰值检测界面"""
    
    # 信号
    detection_finished = pyqtSignal(list)  # 检测完成
    duration_calculated = pyqtSignal(dict)  # 持续时间计算完成
    peak_selected = pyqtSignal(int)  # 峰值选择（ID）
    
    def __init__(self, parent=None):
        super(AutoSpikeDetector, self).__init__(parent)
        
        # 初始化数据
        self.plot_canvas = None  # 将由父级设置
        self.toolbar = None      # 将由父级设置
        self.detection_thread = None
        self.detection_worker = None
        self.duration_thread = None
        self.duration_worker = None
        self.plot_widget = None  # 添加一个引用到绘图区域
        
        # 线程保护标志
        self._is_thread_running = False
        self._thread_lock = False
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def set_plot_canvas(self, canvas, toolbar):
        """设置绘图画布和工具栏"""
        # 保存引用
        self.plot_canvas = canvas
        self.toolbar = toolbar
        
        # 确保plot_widget存在
        if not self.plot_widget:
            print("Error: plot_widget is not created")
            return False
        
        # 获取绘图区域的布局
        plot_layout = self.plot_widget.layout()
        
        # 清除现有内容
        while plot_layout.count():
            item = plot_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        
        # 添加工具栏和画布
        plot_layout.addWidget(toolbar)
        plot_layout.addWidget(canvas)
        
        print("Canvas and toolbar added successfully")
        
        # 确保显示更新
        self.plot_widget.update()
        
        return True
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 减少主布局边距
        
        # 创建顶部和底部分割器
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ==================== 顶部区域：绘图和控制面板 ====================
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 5, 5, 5)  # 减少边距
        
        # ----------------- 左侧：控制面板 -----------------
        control_panel = QWidget()
        control_panel.setMaximumWidth(350)  # 设置控制面板最大宽度
        control_layout = QVBoxLayout(control_panel)
        
        # 1. 检测设置部分
        detection_group = QGroupBox("Peak Detection Settings")
        detection_layout = QVBoxLayout(detection_group)
        
        # 1.1 检测方法选择
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Threshold", "Scipy Algorithm"])
        method_layout.addWidget(self.method_combo, 1)
        
        # 1.2 阈值设置
        threshold_layout = QVBoxLayout()
        threshold_header = QHBoxLayout()
        threshold_header.addWidget(QLabel("Threshold:"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-1000, 1000)
        self.threshold_spin.setValue(0.5)
        self.threshold_spin.setDecimals(3)
        self.threshold_spin.setSingleStep(0.1)
        threshold_header.addWidget(self.threshold_spin, 1)
        
        # 1.3 添加提示文字
        threshold_tip = QLabel("Note: Positive threshold detects positive peaks, negative threshold detects negative peaks")
        threshold_tip.setStyleSheet("color: gray; font-size: 9px;")
        threshold_tip.setWordWrap(True)
        
        threshold_layout.addLayout(threshold_header)
        threshold_layout.addWidget(threshold_tip)
        
        # 1.4 最小距离设置
        min_distance_layout = QHBoxLayout()
        min_distance_layout.addWidget(QLabel("Min Distance (samples):"))
        self.min_distance_spin = QSpinBox()
        self.min_distance_spin.setRange(1, 10000)
        self.min_distance_spin.setValue(10)
        min_distance_layout.addWidget(self.min_distance_spin, 1)
        
        # 1.5 持续时间设置
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration Threshold (%):"))
        self.duration_threshold_spin = QDoubleSpinBox()
        self.duration_threshold_spin.setRange(1, 99)
        self.duration_threshold_spin.setValue(50)
        self.duration_threshold_spin.setDecimals(1)
        self.duration_threshold_spin.setSingleStep(5)
        duration_layout.addWidget(self.duration_threshold_spin, 1)
        
        # 1.6 检测按钮
        self.detect_btn = QPushButton("Detect Peaks")
        self.detect_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px;")
        
        # 1.7 添加到检测设置布局
        detection_layout.addLayout(method_layout)
        detection_layout.addLayout(threshold_layout)
        detection_layout.addLayout(min_distance_layout)
        detection_layout.addLayout(duration_layout)
        detection_layout.addWidget(self.detect_btn)
        
        # 2. 游标模式选择
        cursor_group = QGroupBox("Cursor Mode")
        cursor_layout = QVBoxLayout(cursor_group)
        
        # 2.1 添加标签
        cursor_label = QLabel("Select cursor to adjust:")
        cursor_layout.addWidget(cursor_label)
        
        # 2.2 单选按钮组
        self.cursor_mode_group = QButtonGroup(self)
        
        # 2.3 开始游标按钮
        self.start_cursor_radio = QRadioButton("Start Time")
        self.start_cursor_radio.setChecked(True)  # 默认选中
        self.cursor_mode_group.addButton(self.start_cursor_radio, 1)
        cursor_layout.addWidget(self.start_cursor_radio)
        
        # 2.4 结束游标按钮
        self.end_cursor_radio = QRadioButton("End Time")
        self.cursor_mode_group.addButton(self.end_cursor_radio, 2)
        cursor_layout.addWidget(self.end_cursor_radio)
        
        # 2.5 振幅游标按钮
        self.amp_cursor_radio = QRadioButton("Amplitude")
        self.cursor_mode_group.addButton(self.amp_cursor_radio, 3)
        cursor_layout.addWidget(self.amp_cursor_radio)
        
        # 3. 保存部分
        save_group = QGroupBox("Save Results")
        save_layout = QVBoxLayout(save_group)
        
        # 3.1 选择要保存的参数
        self.save_time_check = QCheckBox("Time (s)")
        self.save_time_check.setChecked(True)
        self.save_amplitude_check = QCheckBox("Amplitude")
        self.save_amplitude_check.setChecked(True)
        self.save_duration_check = QCheckBox("Duration (ms)")
        self.save_duration_check.setChecked(True)
        
        # 3.2 保存按钮
        self.save_btn = QPushButton("Save Peaks Data")
        self.save_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 5px;")
        
        # 3.3 添加到保存部分布局
        save_layout.addWidget(self.save_time_check)
        save_layout.addWidget(self.save_amplitude_check)
        save_layout.addWidget(self.save_duration_check)
        save_layout.addWidget(self.save_btn)
        
        # 4. 将控件添加到左侧控制面板
        control_layout.addWidget(detection_group)
        control_layout.addWidget(cursor_group)
        control_layout.addWidget(save_group)
        control_layout.addStretch(1)  # 添加弹性空间
        
        # ----------------- 右侧：绘图区域 -----------------
        # 建立一个专门的绘图容器
        self.plot_widget = QWidget()
        self.plot_widget.setMinimumWidth(600)  # 设置绘图区域最小宽度
        self.plot_widget.setMinimumHeight(400)  # 设置绘图区域最小高度
        plot_layout = QVBoxLayout(self.plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        
        # 给绘图区域设置一个明显的背景颜色，以便调试时观察（可以在发布时移除）
        # self.plot_widget.setStyleSheet("background-color: #E0F7FA;")
        
        # 设置左右区域比例 (左侧控制面板占比例小，右侧绘图区域占比例大)
        top_layout.addWidget(control_panel)  # 控制面板自动设置了最大宽度
        top_layout.addWidget(self.plot_widget, 1)  # 绘图区域应占据所有剩余空间
        
        # ==================== 底部区域：峰值数据表格 ====================
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # 1. 表格标题和筛选控件
        table_header_layout = QHBoxLayout()
        
        # 1.1 表格标题
        table_title = QLabel("Detected Peaks")
        table_title.setFont(self.font())
        table_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        
        # 1.2 筛选控件
        self.filter_check = QCheckBox("Filter by Amplitude >")
        self.filter_value = QDoubleSpinBox()
        self.filter_value.setRange(-1000, 1000)
        self.filter_value.setValue(0)
        self.filter_value.setDecimals(3)
        self.filter_value.setSingleStep(0.1)
        self.filter_apply_btn = QPushButton("Apply Filter")
        
        # 1.3 导航按钮
        self.prev_peak_btn = QPushButton("◀ Previous")
        self.next_peak_btn = QPushButton("Next ▶")
        self.remove_peak_btn = QPushButton("Remove Selected")
        self.remove_peak_btn.setStyleSheet("color: red;")
        
        # 1.4 添加到表格标题布局
        table_header_layout.addWidget(table_title)
        table_header_layout.addStretch(1)
        table_header_layout.addWidget(self.filter_check)
        table_header_layout.addWidget(self.filter_value)
        table_header_layout.addWidget(self.filter_apply_btn)
        table_header_layout.addWidget(self.prev_peak_btn)
        table_header_layout.addWidget(self.next_peak_btn)
        table_header_layout.addWidget(self.remove_peak_btn)
        
        # 2. 峰值数据表格
        self.peaks_table = QTableWidget()
        self.peaks_table.setColumnCount(5)
        self.peaks_table.setHorizontalHeaderLabels(["#", "Time (s)", "Amplitude", "Duration (ms)", "Actions"])
        self.peaks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 3. 添加到底部布局
        bottom_layout.addLayout(table_header_layout)
        bottom_layout.addWidget(self.peaks_table)
        
        # ==================== 将顶部和底部区域添加到分割器 ====================
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([600, 300])  # 设置初始高度分配，增加顶部区域高度
        
        # 添加到主布局
        main_layout.addWidget(main_splitter)
    
    def connect_signals(self):
        """连接信号"""
        # 检测按钮
        self.detect_btn.clicked.connect(self.detect_peaks)
        
        # 表格选择
        self.peaks_table.itemSelectionChanged.connect(self.on_peak_selected)
        
        # 表格筛选
        self.filter_apply_btn.clicked.connect(self.apply_filter)
        
        # 导航按钮
        self.prev_peak_btn.clicked.connect(self.select_previous_peak)
        self.next_peak_btn.clicked.connect(self.select_next_peak)
        
        # 删除峰值
        self.remove_peak_btn.clicked.connect(self.remove_selected_peak)
        
        # 游标模式
        self.cursor_mode_group.buttonClicked.connect(self.on_cursor_mode_changed)
        
        # 保存按钮
        self.save_btn.clicked.connect(self.save_peaks_data)
    
    def detect_peaks(self):
        """检测峰值"""
        if self.plot_canvas is None or self.plot_canvas.current_channel_data is None:
            QMessageBox.warning(self, "Warning", "No data available for detection")
            return
        
        # 阻止多次启动线程
        if self._is_thread_running:
            QMessageBox.information(self, "Information", "Peak detection in progress, please wait...")
            return
            
        # 确保线程锁被重置
        if self._thread_lock:
            print("Thread lock was not properly reset. Forcing reset.")
            self._thread_lock = False
            
        self._thread_lock = True  # 设置线程锁
        
        try:
            # 获取检测参数
            threshold = self.threshold_spin.value()
            min_distance = self.min_distance_spin.value()
            method = "threshold" if self.method_combo.currentIndex() == 0 else "scipy"
            
            # 确保任何旧的线程都被清理
            self.cleanup_detection_thread()
            
            # 创建并启动检测线程
            self.detection_thread = QThread()
            self.detection_worker = PeakDetectionWorker(
                self.plot_canvas.current_channel_data, threshold, min_distance, method)
            
            self.detection_worker.moveToThread(self.detection_thread)
            self.detection_thread.started.connect(self.detection_worker.run)
            self.detection_worker.finished.connect(self._on_detection_done)
            self.detection_worker.progress.connect(self.update_detection_progress)
            
            # 在线程退出后执行_reset_thread_state
            self.detection_thread.finished.connect(self._reset_thread_state)
            
            # 设置标志指示线程正在运行
            self._is_thread_running = True
            
            # 禁用检测按钮并更新状态
            self.detect_btn.setEnabled(False)
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage("Detecting peaks...")
            
            # 启动线程
            self.detection_thread.start()
            
        except Exception as e:
            import traceback
            print(f"Error starting detection thread: {e}")
            print(traceback.format_exc())
            self.detect_btn.setEnabled(True)
            self._is_thread_running = False
            self._thread_lock = False  # 确保错误时释放锁
    
    def _reset_thread_state(self):
        """重置线程状态"""
        print("Thread state reset")
        self._is_thread_running = False
        self._thread_lock = False
    
    def _on_detection_done(self, peaks_indices):
        """峰值检测完成的中间处理函数"""
        print("Detection finished, resetting detect button")
        self.detect_btn.setEnabled(True)
        
        # 确保线程锁被重置
        self._thread_lock = False
        
        # 调用原始处理函数
        self.on_peaks_detected(peaks_indices)
    
    def update_detection_progress(self, progress):
        """更新检测进度"""
        if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
            self.parent().status_bar.showMessage(f"Detecting peaks... {progress}%")
    
    def on_peaks_detected(self, peaks_indices):
        """峰值检测完成后处理"""
        # 重新启用检测按钮
        self.detect_btn.setEnabled(True)
        
        # 显示峰值
        self.plot_canvas.plot_peaks(peaks_indices)
        
        # 计算峰值持续时间
        self.calculate_peak_durations(peaks_indices)
        
        # 更新状态栏
        if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
            self.parent().status_bar.showMessage(f"Detected {len(peaks_indices)} peaks")
        
        # 发送检测完成信号
        self.detection_finished.emit(peaks_indices)
    
    def cleanup_detection_thread(self):
        """清理现有的检测线程"""
        if self.detection_thread and self.detection_thread.isRunning():
            # 尝试安全停止线程
            if self.detection_worker:
                self.detection_worker.abort()
            self.detection_thread.quit()
            self.detection_thread.wait(1000)  # 等待最多1秒
            
            # 如果线程仍在运行，强制终止
            if self.detection_thread.isRunning():
                self.detection_thread.terminate()
                self.detection_thread.wait()
    
    def cleanup_duration_thread(self):
        """清理现有的持续时间计算线程"""
        if self.duration_thread and self.duration_thread.isRunning():
            # 尝试安全停止线程
            if self.duration_worker:
                self.duration_worker.abort()
            self.duration_thread.quit()
            self.duration_thread.wait(1000)  # 等待最多1秒
            
            # 如果线程仍在运行，强制终止
            if self.duration_thread.isRunning():
                self.duration_thread.terminate()
                self.duration_thread.wait()
    
    def calculate_peak_durations(self, peaks_indices):
        """计算每个峰值的持续时间"""
        if not peaks_indices:
            self.update_peaks_table()
            return
        
        # 阻止多次启动线程
        if self._is_thread_running and self._thread_lock:
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage("Another process is running, please wait...")
            return
            
        # 强制重置线程状态，确保我们能够启动新的线程
        if self._thread_lock:
            print("Thread lock was still set in calculate_peak_durations. Forcing reset.")
            self._thread_lock = False
            
        self._thread_lock = True
                
        try:
            # 确保任何旧的线程都被清理
            self.cleanup_duration_thread()
            
            # 获取持续时间阈值百分比
            threshold_ratio = self.duration_threshold_spin.value() / 100
            
            # 创建并启动持续时间计算线程
            self.duration_thread = QThread()
            self.duration_worker = PeakDurationWorker(
                self.plot_canvas.current_channel_data, peaks_indices, threshold_ratio)
            
            self.duration_worker.moveToThread(self.duration_thread)
            self.duration_thread.started.connect(self.duration_worker.run)
            self.duration_worker.finished.connect(self._on_durations_calculated)
            self.duration_worker.progress.connect(self.update_duration_progress)
            
            # 处理线程退出
            self.duration_thread.finished.connect(self._reset_thread_state)
            
            # 设置标志指示线程正在运行
            self._is_thread_running = True
            
            # 更新状态
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage("Calculating peak durations...")
            
            # 启动线程
            self.duration_thread.start()
            
        except Exception as e:
            import traceback
            print(f"Error starting duration thread: {e}")
            print(traceback.format_exc())
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage(f"Error: {str(e)}")
            self._is_thread_running = False
            self._thread_lock = False  # 确保错误时释放锁
    
    def update_duration_progress(self, progress):
        """更新持续时间计算进度"""
        if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
            self.parent().status_bar.showMessage(f"Calculating peak durations... {progress}%")
    
    def _on_durations_calculated(self, durations_data):
        """持续时间计算完成后处理的中间函数"""
        # 直接重置线程状态，确保锁被释放
        self._is_thread_running = False
        self._thread_lock = False
        
        # 处理持续时间数据
        self.on_durations_calculated(durations_data)
    
    def on_durations_calculated(self, durations_data):
        """持续时间计算完成后的实际处理函数 - 处理计算结果"""
        # 更新每个峰值的持续时间信息
        for peak_id, duration_info in durations_data.items():
            self.plot_canvas.set_peak_duration(
                peak_id, 
                duration_info['start_idx'], 
                duration_info['end_idx']
            )
        
        # 更新峰值表格
        self.update_peaks_table()
        
        # 更新状态
        if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
            self.parent().status_bar.showMessage(f"Calculated durations for {len(durations_data)} peaks")
        
        # 发送持续时间计算完成信号
        self.duration_calculated.emit(durations_data)
    
    def update_peaks_table(self):
        """更新峰值表格"""
        # 获取峰值数据
        peaks_data = self.plot_canvas.get_peaks_data()
        
        # 清空表格
        self.peaks_table.clearContents()
        self.peaks_table.setRowCount(0)
        
        # 填充表格
        for peak_id, peak_info in peaks_data.items():
            row = self.peaks_table.rowCount()
            self.peaks_table.insertRow(row)
            
            # 峰值编号
            self.peaks_table.setItem(row, 0, QTableWidgetItem(str(peak_id + 1)))
            
            # 时间
            time_item = QTableWidgetItem(f"{peak_info['time']:.4f}")
            self.peaks_table.setItem(row, 1, time_item)
            
            # 振幅
            amplitude_item = QTableWidgetItem(f"{peak_info['amplitude']:.4f}")
            self.peaks_table.setItem(row, 2, amplitude_item)
            
            # 持续时间（如果有）
            if 'duration' in peak_info:
                duration_ms = peak_info['duration'] * 1000  # 转换为毫秒
                duration_item = QTableWidgetItem(f"{duration_ms:.2f}")
                self.peaks_table.setItem(row, 3, duration_item)
            else:
                self.peaks_table.setItem(row, 3, QTableWidgetItem("N/A"))
            
            # 操作按钮
            select_btn = QPushButton("Select")
            select_btn.setProperty("peak_id", peak_id)
            select_btn.clicked.connect(lambda checked, pid=peak_id: self.highlight_peak(pid))
            
            # 将按钮添加到表格
            self.peaks_table.setCellWidget(row, 4, select_btn)
    
    def highlight_peak(self, peak_id):
        """高亮显示选中的峰值"""
        if self.plot_canvas:
            self.plot_canvas.highlight_peak(peak_id)
        
            # 在表格中选择对应行
            for row in range(self.peaks_table.rowCount()):
                if self.peaks_table.cellWidget(row, 4).property("peak_id") == peak_id:
                    self.peaks_table.selectRow(row)
                    break
            
            # 发送峰值选择信号
            self.peak_selected.emit(peak_id)
    
    def on_peak_selected(self):
        """处理表格选择变化"""
        selected_rows = self.peaks_table.selectionModel().selectedRows()
        if selected_rows and self.plot_canvas:
            row = selected_rows[0].row()
            if row >= 0:
                select_btn = self.peaks_table.cellWidget(row, 4)
                if select_btn:
                    peak_id = select_btn.property("peak_id")
                    self.plot_canvas.highlight_peak(peak_id)
                    # 发送峰值选择信号
                    self.peak_selected.emit(peak_id)
    
    def select_previous_peak(self):
        """选择上一个峰值"""
        current_row = -1
        for idx in self.peaks_table.selectedIndexes():
            if idx.column() == 0:  # 只检查第一列的选择
                current_row = idx.row()
                break
        
        if current_row > 0:
            self.peaks_table.selectRow(current_row - 1)
        elif current_row == -1 and self.peaks_table.rowCount() > 0:
            # 如果没有选中行，选择最后一行
            self.peaks_table.selectRow(self.peaks_table.rowCount() - 1)
    
    def select_next_peak(self):
        """选择下一个峰值"""
        current_row = -1
        for idx in self.peaks_table.selectedIndexes():
            if idx.column() == 0:  # 只检查第一列的选择
                current_row = idx.row()
                break
        
        if current_row >= 0 and current_row < self.peaks_table.rowCount() - 1:
            self.peaks_table.selectRow(current_row + 1)
        elif current_row == -1 and self.peaks_table.rowCount() > 0:
            # 如果没有选中行，选择第一行
            self.peaks_table.selectRow(0)
    
    def remove_selected_peak(self):
        """移除选中的峰值"""
        selected_rows = self.peaks_table.selectionModel().selectedRows()
        if not selected_rows or not self.plot_canvas:
            return
            
        row = selected_rows[0].row()
        if row >= 0:
            select_btn = self.peaks_table.cellWidget(row, 4)
            if select_btn:
                peak_id = select_btn.property("peak_id")
                
                # 确认对话框
                reply = QMessageBox.question(
                    self, 
                    "Confirm Removal", 
                    f"Are you sure you want to remove peak #{peak_id + 1}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # 从峰值数据中移除
                    peaks_data = self.plot_canvas.get_peaks_data()
                    if peak_id in peaks_data:
                        del peaks_data[peak_id]
                    
                    # 从表格中移除
                    self.peaks_table.removeRow(row)
                    
                    # 更新状态
                    if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                        self.parent().status_bar.showMessage(f"Removed peak #{peak_id + 1}")
    
    def apply_filter(self):
        """应用振幅筛选"""
        if not self.plot_canvas:
            return
            
        filter_enabled = self.filter_check.isChecked()
        filter_value = self.filter_value.value()
        
        # 获取峰值数据
        peaks_data = self.plot_canvas.get_peaks_data()
        
        # 更新表格
        self.peaks_table.clearContents()
        self.peaks_table.setRowCount(0)
        
        # 填充表格（应用筛选）
        for peak_id, peak_info in peaks_data.items():
            # 如果启用筛选，则检查振幅是否大于筛选值
            if filter_enabled and peak_info['amplitude'] <= filter_value:
                continue
                
            row = self.peaks_table.rowCount()
            self.peaks_table.insertRow(row)
            
            # 峰值编号
            self.peaks_table.setItem(row, 0, QTableWidgetItem(str(peak_id + 1)))
            
            # 时间
            time_item = QTableWidgetItem(f"{peak_info['time']:.4f}")
            self.peaks_table.setItem(row, 1, time_item)
            
            # 振幅
            amplitude_item = QTableWidgetItem(f"{peak_info['amplitude']:.4f}")
            self.peaks_table.setItem(row, 2, amplitude_item)
            
            # 持续时间（如果有）
            if 'duration' in peak_info:
                duration_ms = peak_info['duration'] * 1000  # 转换为毫秒
                duration_item = QTableWidgetItem(f"{duration_ms:.2f}")
                self.peaks_table.setItem(row, 3, duration_item)
            else:
                self.peaks_table.setItem(row, 3, QTableWidgetItem("N/A"))
            
            # 操作按钮
            select_btn = QPushButton("Select")
            select_btn.setProperty("peak_id", peak_id)
            select_btn.clicked.connect(lambda checked, pid=peak_id: self.highlight_peak(pid))
            
            # 将按钮添加到表格
            self.peaks_table.setCellWidget(row, 4, select_btn)
        
        # 更新状态
        if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
            if filter_enabled:
                visible_peaks = self.peaks_table.rowCount()
                total_peaks = len(peaks_data)
                self.parent().status_bar.showMessage(f"Showing {visible_peaks} of {total_peaks} peaks (filter: amplitude > {filter_value})")
            else:
                self.parent().status_bar.showMessage(f"Showing all {len(peaks_data)} peaks")
    
    def on_cursor_mode_changed(self, button):
        """处理游标模式切换"""
        if not self.plot_canvas:
            return
            
        mode_id = self.cursor_mode_group.id(button)
        print(f"Cursor mode changed to: {mode_id} = {button.text()}")
        
        # 如果当前没有选中峰值，则忽略
        if not hasattr(self.plot_canvas, 'current_peak_idx') or self.plot_canvas.current_peak_idx < 0:
            return
            
        # 获取游标文本
        cursor_text = button.text()
        
        # 根据不同的按钮ID和文本确定游标类型
        cursor_type = None
        
        if 'start' in cursor_text.lower():
            cursor_type = 'start'
        elif 'end' in cursor_text.lower():
            cursor_type = 'end'  
        elif 'amp' in cursor_text.lower() or 'amplitude' in cursor_text.lower():
            cursor_type = 'amp'
        else:
            # 如果不能从文本确定，则使用ID
            if mode_id == 1:
                cursor_type = 'start'
            elif mode_id == 2:
                cursor_type = 'end'
            elif mode_id == 3:
                cursor_type = 'amp'
        
        # 在plot_canvas上应用游标模式
        if cursor_type and self.plot_canvas.current_peak_idx in self.plot_canvas.peaks_data:
            # 获取当前峰值数据
            peak_data = self.plot_canvas.peaks_data[self.plot_canvas.current_peak_idx]
            
            # 使用创建游标的方法
            try:
                self.plot_canvas.create_cursors(peak_data)
            except Exception as e:
                print(f"Error creating cursor: {e}")
    
    def on_peak_data_changed(self, peak_id, peak_data):
        """处理峰值数据更新（由游标操作触发）"""
        # 更新峰值表格中的数据
        for row in range(self.peaks_table.rowCount()):
            # 获取该行的峰值 ID
            select_btn = self.peaks_table.cellWidget(row, 4)
            if select_btn and select_btn.property("peak_id") == peak_id:
                # 更新时间
                if 'time' in peak_data:
                    self.peaks_table.setItem(row, 1, QTableWidgetItem(f"{peak_data['time']:.4f}"))
                
                # 更新振幅
                if 'amplitude' in peak_data:
                    self.peaks_table.setItem(row, 2, QTableWidgetItem(f"{peak_data['amplitude']:.4f}"))
                
                # 更新持续时间
                if 'duration' in peak_data:
                    duration_ms = peak_data['duration'] * 1000  # 转换为毫秒
                    self.peaks_table.setItem(row, 3, QTableWidgetItem(f"{duration_ms:.2f}"))
                break
    
    def save_peaks_data(self):
        """保存峰值数据"""
        # 检查是否有峰值数据
        if not self.plot_canvas:
            QMessageBox.warning(self, "Warning", "No plot canvas available")
            return
            
        peaks_data = self.plot_canvas.get_peaks_data()
        if not peaks_data:
            QMessageBox.warning(self, "Warning", "No peaks data to save")
            return
        
        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Peaks Data",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 准备保存数据
            save_data = []
            
            # 获取选择的参数
            save_time = self.save_time_check.isChecked()
            save_amplitude = self.save_amplitude_check.isChecked()
            save_duration = self.save_duration_check.isChecked()
            
            # 创建表头
            header = ["Peak ID"]
            if save_time:
                header.append("Time (s)")
            if save_amplitude:
                header.append("Amplitude")
            if save_duration:
                header.append("Duration (ms)")
            
            # 填充数据
            for peak_id, peak_info in peaks_data.items():
                row_data = [peak_id + 1]  # 峰值ID（从1开始）
                
                if save_time:
                    row_data.append(peak_info['time'])
                
                if save_amplitude:
                    row_data.append(peak_info['amplitude'])
                
                if save_duration and 'duration' in peak_info:
                    row_data.append(peak_info['duration'] * 1000)  # 转换为毫秒
                elif save_duration:
                    row_data.append(float('nan'))  # 如果没有持续时间数据
                
                save_data.append(row_data)
            
            # 创建DataFrame
            df = pd.DataFrame(save_data, columns=header)
            
            # 保存CSV文件
            df.to_csv(file_path, index=False)
            
            # 更新状态
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage(f"Saved {len(save_data)} peaks to {os.path.basename(file_path)}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save peaks data: {str(e)}"
            )
            if hasattr(self, 'parent') and hasattr(self.parent(), 'status_bar'):
                self.parent().status_bar.showMessage(f"Error: {str(e)}")
