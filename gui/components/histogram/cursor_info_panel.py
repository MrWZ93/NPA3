#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cursor Info Panel - Cursor信息面板
提供cursor信息的显示、选择和删除功能
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QPushButton, QLabel, QDoubleSpinBox,
                            QMessageBox, QGroupBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class CursorInfoPanel(QWidget):
    """Cursor信息面板，支持多选删除功能"""
    
    # 定义信号
    cursor_selected = pyqtSignal(int)  # cursor被选中
    cursor_deleted = pyqtSignal(int)  # 单个cursor被删除
    cursors_deleted = pyqtSignal(list)  # 多个cursor被删除
    cursor_position_changed = pyqtSignal(int, float)  # cursor位置变化
    add_cursor_requested = pyqtSignal()  # 请求添加cursor
    clear_cursors_requested = pyqtSignal()  # 请求清除所有cursor
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.selected_cursor_id = None
        self._updating_data = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 操作按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 统一的按钮样式
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                color: #333333;
                min-height: 14px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #b0b0b0;
            }
            QPushButton:pressed {
                background-color: #d4d4d4;
                border-color: #888888;
            }
            QPushButton:disabled {
                background-color: #f9f9f9;
                border-color: #e0e0e0;
                color: #999999;
            }
        """
        
        # Add按钮
        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet(button_style)
        self.add_btn.clicked.connect(self.add_cursor_requested.emit)
        button_layout.addWidget(self.add_btn)
        
        # Delete Selected按钮
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setStyleSheet(button_style)
        self.delete_selected_btn.clicked.connect(self.delete_selected_cursors)
        self.delete_selected_btn.setEnabled(False)
        button_layout.addWidget(self.delete_selected_btn)
        
        # Clear按钮
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(button_style)
        self.clear_btn.clicked.connect(self.clear_cursors_requested.emit)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # Cursor列表
        self.cursor_list = QListWidget()
        self.cursor_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # 支持多选
        self.cursor_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.cursor_list.itemClicked.connect(self.on_cursor_item_clicked)
        self.cursor_list.setMinimumHeight(120)
        self.cursor_list.setMaximumHeight(200)
        self.cursor_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #e3f2fd;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.cursor_list)
        
        # 位置控制组
        position_group = QGroupBox("Position Control")
        position_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
            }
        """)
        position_layout = QVBoxLayout()
        
        # 位置标签和输入框
        pos_row = QHBoxLayout()
        pos_label = QLabel("Y Position:")
        pos_label.setStyleSheet("font-weight: normal; color: #333333;")
        pos_row.addWidget(pos_label)
        
        self.position_spinbox = QDoubleSpinBox()
        self.position_spinbox.setDecimals(4)
        self.position_spinbox.setRange(-999999, 999999)
        self.position_spinbox.setSingleStep(0.01)
        self.position_spinbox.valueChanged.connect(self.on_position_changed)
        self.position_spinbox.setEnabled(False)  # 初始状态为禁用
        self.position_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                background-color: white;
            }
            QDoubleSpinBox:disabled {
                background-color: #f5f5f5;
                color: #888888;
            }
        """)
        pos_row.addWidget(self.position_spinbox)
        
        position_layout.addLayout(pos_row)
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        # 统计信息
        self.stats_label = QLabel("Total Cursors: 0\nSelected: 0")
        self.stats_label.setStyleSheet("""
            color: #555555; 
            font-size: 11px; 
            line-height: 1.4;
            padding: 5px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            background-color: #f9f9f9;
        """)
        layout.addWidget(self.stats_label)
        
        self.setLayout(layout)
    
    def refresh_cursor_list(self, cursor_info_list):
        """刷新cursor列表显示"""
        if self._updating_data:
            return
            
        try:
            self._updating_data = True
            
            # 保存当前选中项
            selected_ids = []
            for item in self.cursor_list.selectedItems():
                cursor_id = item.data(Qt.ItemDataRole.UserRole)
                if cursor_id is not None:
                    selected_ids.append(cursor_id)
            
            # 清空列表
            self.cursor_list.clear()
            
            # 按照cursor ID排序
            sorted_info = sorted(cursor_info_list, key=lambda x: x['id'])
            
            # 添加cursor项
            for i, info in enumerate(sorted_info):
                cursor_id = info['id']
                y_pos = info['y_position']
                color = info['color']
                is_selected = info.get('selected', False)
                
                # 创建列表项
                display_num = i + 1
                item_text = f"Cursor {display_num}: Y = {y_pos:.4f}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, cursor_id)
                
                # 设置颜色指示
                color_obj = QColor(color)
                
                # 根据选中状态设置背景颜色
                if is_selected:
                    item.setBackground(color_obj.lighter(140))
                    item.setForeground(QColor('#1976d2'))
                else:
                    item.setBackground(color_obj.lighter(180))
                    
                self.cursor_list.addItem(item)
                
                # 恢复多选状态
                if cursor_id in selected_ids:
                    item.setSelected(True)
            
            # 更新统计信息
            self.update_statistics()
            
        except Exception as e:
            print(f"Error refreshing cursor list: {e}")
        finally:
            self._updating_data = False
    
    def on_selection_changed(self):
        """处理列表选择变化"""
        if self._updating_data:
            return
            
        selected_items = self.cursor_list.selectedItems()
        
        # 更新删除按钮状态
        self.delete_selected_btn.setEnabled(len(selected_items) > 0)
        
        # 如果只选中一个项目，显示其位置信息
        if len(selected_items) == 1:
            cursor_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if cursor_id is not None:
                self.selected_cursor_id = cursor_id
                self.cursor_selected.emit(cursor_id)
                
                # 获取cursor位置并更新position_spinbox
                if self.parent_dialog and hasattr(self.parent_dialog, 'get_current_canvas'):
                    canvas = self.parent_dialog.get_current_canvas()
                    if canvas and hasattr(canvas, 'get_cursor_info'):
                        cursor_info = canvas.get_cursor_info()
                        for info in cursor_info:
                            if info['id'] == cursor_id:
                                self.position_spinbox.setValue(info['y_position'])
                                self.position_spinbox.setEnabled(True)
                                break
        else:
            # 多选或无选择时禁用位置控制
            self.selected_cursor_id = None
            self.position_spinbox.setEnabled(False)
            if len(selected_items) == 0:
                self.cursor_selected.emit(-1)  # 发送无选择信号
        
        self.update_statistics()
    
    def on_cursor_item_clicked(self, item):
        """处理cursor列表项被点击"""
        cursor_id = item.data(Qt.ItemDataRole.UserRole)
        if cursor_id is not None:
            self.cursor_selected.emit(cursor_id)
    
    def on_position_changed(self, value):
        """处理位置输入框值变化"""
        if self.selected_cursor_id is not None and not self._updating_data:
            self.cursor_position_changed.emit(self.selected_cursor_id, value)
    
    def delete_selected_cursors(self):
        """删除选中的cursor"""
        selected_items = self.cursor_list.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的cursor ID列表
        cursor_ids = []
        for item in selected_items:
            cursor_id = item.data(Qt.ItemDataRole.UserRole)
            if cursor_id is not None:
                cursor_ids.append(cursor_id)
        
        if not cursor_ids:
            return
        
        # 确认删除
        if len(cursor_ids) == 1:
            reply = QMessageBox.question(
                self, "Confirm", f"Delete cursor {cursor_ids[0]}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self, "Confirm", f"Delete {len(cursor_ids)} cursors?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        
        if reply == QMessageBox.StandardButton.Yes:
            if len(cursor_ids) == 1:
                self.cursor_deleted.emit(cursor_ids[0])
            else:
                self.cursors_deleted.emit(cursor_ids)
    
    def update_statistics(self):
        """更新统计信息"""
        total_count = self.cursor_list.count()
        selected_count = len(self.cursor_list.selectedItems())
        
        self.stats_label.setText(f"Total Cursors: {total_count}\nSelected: {selected_count}")
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        self.cursor_list.clear()
        self.selected_cursor_id = None
        self.position_spinbox.setEnabled(False)
        self.delete_selected_btn.setEnabled(False)
        self.update_statistics()
    
    def select_cursor(self, cursor_id):
        """选中指定的cursor"""
        for i in range(self.cursor_list.count()):
            item = self.cursor_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == cursor_id:
                self.cursor_list.setCurrentItem(item)
                item.setSelected(True)
                break
    
    def deselect_all_cursors(self):
        """取消选中所有cursor"""
        self.cursor_list.clearSelection()
        self.selected_cursor_id = None
        self.position_spinbox.setEnabled(False)
        self.delete_selected_btn.setEnabled(False)
        self.update_statistics()
