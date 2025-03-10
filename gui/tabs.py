#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标签页UI组件
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QLabel, QMessageBox, QGroupBox,
                            QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, 
                            QScrollArea, QCheckBox,QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

import os
import h5py

from gui.styles import COLORS, StyleHelper

class FileDetailsTab(QWidget):
    """文件详情标签页"""
    def __init__(self, parent=None):
        super(FileDetailsTab, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.info_label = QTextEdit()
        self.info_label.setReadOnly(True)
        # 使用QScrollArea让文本编辑框可滚动
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.info_label)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.info_label.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-size: 11pt;
            }
        """)
        
        self.layout.addWidget(scroll_area)
        self.setLayout(self.layout)
    
    def update_info(self, info_dict):
        """更新文件信息"""
        info_text = f"<style>\n.info-table {{width: 100%; border-collapse: collapse;}}\n.info-table td {{padding: 8px; border-bottom: 1px solid #eeeeee;}}\n.info-key {{font-weight: bold; color: {COLORS['secondary']}; width: 40%;}}\n.info-value {{width: 60%;}}\n</style>\n"
        info_text += "<table class='info-table'>\n"
        
        for key, value in info_dict.items():
            # Translate keys to English
            translated_key = self.translate_key(key)
            info_text += f"<tr><td class='info-key'>{translated_key}:</td><td class='info-value'>{value}</td></tr>\n"
            
        info_text += "</table>"
        
        self.info_label.setHtml(info_text)
    
    def translate_key(self, key):
        """Translate Chinese key names to English"""
        translations = {
            "文件类型": "File Type",
            "文件路径": "File Path",
            "文件大小": "File Size",
            "修改时间": "Modified Time",
            "行数": "Rows",
            "列数": "Columns",
            "列名": "Column Names",
            "数值列": "Numeric Columns",
            "时间列": "Time Column",
            "错误": "Error",
            "通道数": "Channels",
            "采样率": "Sampling Rate",
            "采样点数": "Sample Points",
            "协议": "Protocol",
            "创建时间": "Creation Time",
            "数据集数量": "Dataset Count"
        }
        return translations.get(key, key)


class NotesTab(QWidget):
    """笔记标签页"""
    def __init__(self, notes_manager, parent=None):
        super(NotesTab, self).__init__(parent)
        self.notes_manager = notes_manager
        self.current_file = None
        
        self.layout = QVBoxLayout(self)
        
        # 标题和信息区域
        self.info_area = QWidget()
        self.info_layout = QHBoxLayout(self.info_area)
        
        self.info_label = QLabel("No file selected")
        self.info_label.setStyleSheet("color: #777; font-style: italic;")
        
        self.storage_info = QLabel("")
        self.storage_info.setStyleSheet("font-size: 10pt; color: #3498db;")
        
        self.info_layout.addWidget(self.info_label)
        self.info_layout.addStretch(1)
        self.info_layout.addWidget(self.storage_info)
        
        # 笔记编辑区域
        self.notes_edit = QTextEdit()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.notes_edit)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-family: Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.5;
            }
        """)
        
        # 按钮区域
        self.button_area = QWidget()
        self.button_layout = QHBoxLayout(self.button_area)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用漂亮的按钮
        self.save_button = QPushButton()
        self.save_button.setText("Save Notes")
        self.save_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_button.setIconSize(QSize(16, 16))
        self.save_button.setMinimumHeight(36)
        self.save_button.clicked.connect(self.save_note)
        
        self.delete_button = QPushButton()
        self.delete_button.setText("Clear Notes")
        self.delete_button.setIcon(QIcon.fromTheme("edit-clear"))
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setMinimumHeight(36)
        self.delete_button.setProperty("class", "secondary")
        self.delete_button.clicked.connect(self.clear_note)
        
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.delete_button)
        
        # 组装布局
        self.layout.addWidget(self.info_area)
        self.layout.addWidget(scroll_area)
        self.layout.addWidget(self.button_area)
        self.setLayout(self.layout)
    
    def load_file_note(self, file_path):
        """加载文件笔记"""
        self.current_file = file_path
        file_name = os.path.basename(file_path)
        self.info_label.setText(f"Notes for: {file_name}")
        
        note_text = self.notes_manager.load_note(file_path)
        self.notes_edit.setText(note_text)
        
        # 检查存储位置，更新信息标签
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.h5':
            try:
                with h5py.File(file_path, 'r') as h5file:
                    if 'metadata' in h5file and 'note' in h5file['metadata'].attrs:
                        self.storage_info.setText("(Stored in file and backup)")
                        return
            except Exception:
                pass
        
        # 如果不在文件中存储或检查失败
        self.storage_info.setText("(Stored in backup)")
    
    def save_note(self):
        """保存笔记"""
        if self.current_file:
            note_text = self.notes_edit.toPlainText()
            result = self.notes_manager.save_note(self.current_file, note_text)
            
            if result:
                QMessageBox.information(self, "Success", "Notes saved successfully")
                
                # 更新存储位置信息
                ext = os.path.splitext(self.current_file)[1].lower()
                if ext == '.h5':
                    try:
                        with h5py.File(self.current_file, 'r') as h5file:
                            if 'metadata' in h5file and 'note' in h5file['metadata'].attrs:
                                self.storage_info.setText("(Stored in file and backup)")
                                return
                    except Exception:
                        pass
                
                self.storage_info.setText("(Stored in backup)")
            else:
                QMessageBox.warning(self, "Error", "Failed to save notes")
        else:
            QMessageBox.warning(self, "Error", "No file selected")
    
    def clear_note(self):
        """清除笔记"""
        if not self.current_file:
            return
            
        if self.notes_edit.toPlainText().strip():
            result = QMessageBox.question(
                self, "Clear Notes", 
                "Are you sure you want to clear all notes for this file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                self.notes_edit.clear()
                self.notes_manager.delete_note(self.current_file)
                self.storage_info.setText("")
                QMessageBox.information(self, "Success", "Notes cleared")
        else:
            # 如果文本已经为空，但笔记文件可能存在
            self.notes_manager.delete_note(self.current_file)
            self.storage_info.setText("")



class VisualizationControlsTab(QWidget):
    # 添加显示通道变化的信号
    from PyQt6.QtCore import pyqtSignal
    channel_selection_changed = pyqtSignal(list)
    """可视化控制标签页"""
    def __init__(self, parent=None):
        super(VisualizationControlsTab, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # 存储当前可用通道
        self.available_channels = []
        # 存储选中的通道
        self.selected_channels = []
        
        # 采样率设置 - 使用更现代的标题
        sampling_rate_header = StyleHelper.header_label("Sampling Rate")
        self.sampling_rate_group = QGroupBox()
        self.sampling_rate_layout = QHBoxLayout()
        
        self.sampling_rate_label = QLabel("Sampling Rate (Hz):")
        self.sampling_rate_input = QDoubleSpinBox()
        self.sampling_rate_input.setRange(0.1, 1000000.0)
        self.sampling_rate_input.setValue(50000.0)  # Default to 50 kHz
        self.sampling_rate_input.setDecimals(1)
        self.sampling_rate_input.setSingleStep(100.0)
        
        self.sampling_rate_layout.addWidget(self.sampling_rate_label)
        self.sampling_rate_layout.addWidget(self.sampling_rate_input)
        self.sampling_rate_layout.addStretch()
        
        rate_layout = QVBoxLayout()
        rate_layout.addWidget(sampling_rate_header)
        rate_layout.addLayout(self.sampling_rate_layout)
        self.sampling_rate_group.setLayout(rate_layout)

        # 设置采样率输入框的最小宽度
        self.sampling_rate_input.setMinimumWidth(150)
        
        # 子图高度设置 - 使用更现代的标题
        subplot_header = StyleHelper.header_label("Subplot Configuration")
        self.subplot_group = QGroupBox()
        self.subplot_layout = QVBoxLayout()  # 改为垂直布局以容纳新控件
        
        # 添加配置按钮（与高度配置同行）
        height_layout = QHBoxLayout()
        self.subplot_label = QLabel("Configure subplot heights:")
        self.subplot_button = QPushButton("Configure Subplots")
        self.subplot_button.setIcon(QIcon.fromTheme("preferences-system"))
        
        height_layout.addWidget(self.subplot_label)
        height_layout.addWidget(self.subplot_button)
        height_layout.addStretch()
        self.subplot_layout.addLayout(height_layout)
        
        # 添加通道选择功能
        self.channel_layout = QVBoxLayout()
        self.channel_select_label = QLabel("Select channels to display:")
        self.channel_select_label.setStyleSheet("margin-top: 10px;")
        self.channel_layout.addWidget(self.channel_select_label)
        
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.channel_list.setMinimumHeight(100)  # 设置列表最小高度
        self.channel_layout.addWidget(self.channel_list)
        
        # 添加全选/取消全选按钮
        self.channel_buttons_layout = QHBoxLayout()
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all_channels)
        self.deselect_all_button = QPushButton("Deselect All")
        self.deselect_all_button.clicked.connect(self.deselect_all_channels)
        self.apply_channel_button = QPushButton("Apply")
        self.apply_channel_button.clicked.connect(self.apply_channel_selection)
        
        self.channel_buttons_layout.addWidget(self.select_all_button)
        self.channel_buttons_layout.addWidget(self.deselect_all_button)
        self.channel_buttons_layout.addWidget(self.apply_channel_button)
        self.channel_layout.addLayout(self.channel_buttons_layout)
        
        # 添加通道选择到子图配置布局
        self.subplot_layout.addLayout(self.channel_layout)
        
        subplot_wrapper = QVBoxLayout()
        subplot_wrapper.addWidget(subplot_header)
        subplot_wrapper.addLayout(self.subplot_layout)
        self.subplot_group.setLayout(subplot_wrapper)
        
        # X轴同步设置
        sync_header = StyleHelper.header_label("X-Axis Synchronization")
        self.sync_group = QGroupBox()
        self.sync_layout = QHBoxLayout()

        # 添加同步复选框
        self.sync_check = QCheckBox("Sync X-Axis between channels")
        self.sync_check.setChecked(True)  # 默认同步
        self.sync_layout.addWidget(self.sync_check)

        # 添加标题和设置到布局
        sync_wrapper = QVBoxLayout()
        sync_wrapper.addWidget(sync_header)
        sync_wrapper.addLayout(self.sync_layout)
        self.sync_group.setLayout(sync_wrapper)

        # 添加到主布局
        self.layout.addWidget(self.sampling_rate_group)
        self.layout.addWidget(self.subplot_group)
        self.layout.addWidget(self.sync_group)  # 添加同步设置组
        self.layout.addStretch()
        
        # 添加通道选择相关的方法
    def update_available_channels(self, channels):
        """更新可用通道列表"""
        self.available_channels = channels
        self.channel_list.clear()
        
        # 添加所有通道到列表中，并默认选中
        for channel in channels:
            item = QListWidgetItem(channel)
            item.setSelected(True)  # 默认选中所有通道
            self.channel_list.addItem(item)
        
        # 更新选中的通道
        self.selected_channels = channels[:]
    
    def select_all_channels(self):
        """选中所有通道"""
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setSelected(True)
    
    def deselect_all_channels(self):
        """取消选中所有通道"""
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setSelected(False)
    
    def apply_channel_selection(self):
        """应用通道选择"""
        # 获取选中的通道
        selected_channels = []
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item.isSelected():
                selected_channels.append(item.text())
        
        # 如果未选择任何通道，至少保留一个默认通道
        if not selected_channels and self.available_channels:
            selected_channels = [self.available_channels[0]]
            # 更新UI上的选择
            self.channel_list.item(0).setSelected(True)
        
        # 保存选中的通道
        self.selected_channels = selected_channels
        
        # 发出信号通知通道选择改变
        self.channel_selection_changed.emit(selected_channels)


class ProcessingTab(QWidget):
    """数据处理标签页"""
    def __init__(self, parent=None):
        super(ProcessingTab, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # 处理操作选择 - 使用更现代的标题
        operation_header = StyleHelper.header_label("Processing Operations")
        self.operation_group = QGroupBox()
        self.operation_layout = QVBoxLayout()
        
        self.operation_combo = QComboBox()
        self.operation_combo.addItems(["Select operation...", "Trim", "Low-pass Filter", "High-pass Filter", "Baseline Correction"])
        self.operation_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #cccccc;
            }
        """)
        self.operation_combo.currentIndexChanged.connect(self.on_operation_changed)
        
        self.operation_layout.addWidget(self.operation_combo)
        # 添加标题和操作选择器到布局
        operation_wrapper = QVBoxLayout()
        operation_wrapper.addWidget(operation_header)
        operation_wrapper.addLayout(self.operation_layout)
        self.operation_group.setLayout(operation_wrapper)
        
        # 通道选择区域 - 新增
        channel_header = StyleHelper.header_label("Channel Selection")
        self.channel_group = QGroupBox()
        self.channel_layout = QVBoxLayout()
        
        # 添加通道选择说明标签
        channel_description = QLabel("Select a specific channel to process or 'All Channels' to process all:")
        channel_description.setStyleSheet("color: #666; font-size: 10pt;")
        self.channel_layout.addWidget(channel_description)
        
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("All Channels")
        self.channel_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #cccccc;
            }
        """)
        
        self.channel_layout.addWidget(self.channel_combo)
        # 添加标题和通道选择器到布局
        channel_wrapper = QVBoxLayout()
        channel_wrapper.addWidget(channel_header)
        channel_wrapper.addLayout(self.channel_layout)
        self.channel_group.setLayout(channel_wrapper)
        
        # 参数设置区域 - 使用更现代的标题
        params_header = StyleHelper.header_label("Parameters")
        self.params_group = QGroupBox()
        self.params_layout = QFormLayout()
        # 添加标题和参数设置到布局
        params_wrapper = QVBoxLayout()
        params_wrapper.addWidget(params_header)
        params_wrapper.addLayout(self.params_layout)
        self.params_group.setLayout(params_wrapper)

        # 设置下拉框的最小宽度
        self.operation_combo.setMinimumWidth(200)
        self.channel_combo.setMinimumWidth(200)
        
        # 操作按钮
        # 创建美观的按钮
        self.process_button = QPushButton("Process Data")
        self.process_button.setIcon(QIcon.fromTheme("system-run"))
        self.process_button.setIconSize(QSize(16, 16))
        self.process_button.setMinimumHeight(36)
        
        self.save_button = QPushButton("Save Results")
        self.save_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_button.setIconSize(QSize(16, 16))
        self.save_button.setMinimumHeight(36)
        
        # 布局添加
        self.layout.addWidget(self.operation_group)
        self.layout.addWidget(self.channel_group)  # 添加通道选择区域
        self.layout.addWidget(self.params_group)
        self.layout.addWidget(self.process_button)
        self.layout.addWidget(self.save_button)
        self.layout.addStretch()
        
        self.setLayout(self.layout)
        
        # 参数控件字典
        self.param_widgets = {}
        self.current_operation = None
        
        # Operation name mappings (English to Chinese for backend compatibility)
        self.operation_mappings = {
            "Trim": "裁切",
            "Low-pass Filter": "低通滤波",
            "High-pass Filter": "高通滤波", 
            "Baseline Correction": "基线校正"
        }
    
    def on_operation_changed(self, index):
        """操作类型变更处理"""
        # 清空参数区域
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.param_widgets = {}
        
        if index == 0:  # "Select operation..."
            self.current_operation = None
            return
        
        operation_display = self.operation_combo.currentText()
        # Map English UI name to Chinese backend name
        self.current_operation = self.operation_mappings.get(operation_display, operation_display)
        
        # 根据操作类型添加相应参数控件
        if self.current_operation == "裁切":  # Trim
            start_spin = QDoubleSpinBox()
            start_spin.setRange(0, 1000000)
            start_spin.setValue(0)
            start_spin.setSuffix(" s")  # Add seconds suffix
            start_spin.setDecimals(3)  # Allow millisecond precision
            start_spin.setMinimumWidth(200)  # Set minimum width
            
            end_spin = QDoubleSpinBox()
            end_spin.setRange(0, 1000000)
            end_spin.setValue(1)
            end_spin.setSuffix(" s")  # Add seconds suffix
            end_spin.setDecimals(3)  # Allow millisecond precision
            end_spin.setMinimumWidth(200)  # Set minimum width
            
            self.params_layout.addRow("Start Time:", start_spin)
            self.params_layout.addRow("End Time:", end_spin)
            
            self.param_widgets["start_time"] = start_spin
            self.param_widgets["end_time"] = end_spin
            
        elif self.current_operation in ["低通滤波", "高通滤波"]:  # Filters
            cutoff_spin = QDoubleSpinBox()
            cutoff_spin.setRange(0.1, 100000)  # Wide range in Hz
            cutoff_spin.setValue(1000)  # Default to 1000 Hz
            cutoff_spin.setSuffix(" Hz")
            cutoff_spin.setDecimals(1)
            cutoff_spin.setSingleStep(100)
            cutoff_spin.setMinimumWidth(200)  # Set minimum width
            
            self.params_layout.addRow("Cutoff Frequency:", cutoff_spin)
            self.param_widgets["cutoff_hz"] = cutoff_spin
            
        elif self.current_operation == "基线校正":  # Baseline Correction
            points_spin = QSpinBox()
            points_spin.setRange(1, 10000)
            points_spin.setValue(100)
            points_spin.setMinimumWidth(200)  # Set minimum width
            
            self.params_layout.addRow("Baseline Points:", points_spin)
            self.param_widgets["points"] = points_spin
    
    def get_parameters(self):
        """获取当前参数设置"""
        if not self.current_operation:
            return None
        
        params = {}
        # 添加所有通用参数
        for key, widget in self.param_widgets.items():
            params[key] = widget.value()
        
        # 添加通道选择参数
        selected_channel = self.channel_combo.currentText()
        if selected_channel != "All Channels":
            params["channel"] = selected_channel
        
        return params
