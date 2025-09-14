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
    toggle_cursors_visibility_requested = pyqtSignal()  # 请求切换cursor可见性
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.selected_cursor_id = None
        self._updating_data = False
        self._skip_updates_during_tab_change = False  # 用于控制tab切换时是否跳过更新
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)  # 减小间距
        
        # 操作按钮组 - 改为两行布局，确保4个按钮完整显示
        button_group = QGroupBox("Cursor Controls")
        button_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
                min-height: 80px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
                color: #333333;
            }
        """)
        
        button_main_layout = QVBoxLayout()
        button_main_layout.setSpacing(10)  # 增大间距，防止按钮重叠
        button_main_layout.setContentsMargins(8, 12, 8, 12)  # 增大内边距，给按钮更多空间
        
        # 统一的按钮样式 - 增强字体颜色对比度，调整高度
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 6px;
                font-size: 11px;
                color: #1a1a1a;
                min-height: 14px;
                max-height: 22px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #b0b0b0;
                color: #000000;
            }
            QPushButton:pressed {
                background-color: #d4d4d4;
                border-color: #888888;
                color: #000000;
            }
            QPushButton:disabled {
                background-color: #f9f9f9;
                border-color: #e0e0e0;
                color: #666666;
            }
        """
        
        # 第一行按钮：Add 和 Delete Selected - 增大间距，避免重叠
        first_row_layout = QHBoxLayout()
        first_row_layout.setSpacing(10)  # 增大按钮间距
        
        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet(button_style)
        self.add_btn.clicked.connect(self.add_cursor_requested.emit)
        # 适中宽度，确保4个按钮都能显示
        self.add_btn.setMinimumWidth(75)
        self.add_btn.setMaximumWidth(75)
        first_row_layout.addWidget(self.add_btn)
        
        self.delete_selected_btn = QPushButton("Delete")
        self.delete_selected_btn.setStyleSheet(button_style)
        self.delete_selected_btn.clicked.connect(self.delete_selected_cursors)
        self.delete_selected_btn.setEnabled(False)
        # 适中宽度，确保4个按钮都能显示
        self.delete_selected_btn.setMinimumWidth(75)
        self.delete_selected_btn.setMaximumWidth(75)
        first_row_layout.addWidget(self.delete_selected_btn)
        
        button_main_layout.addLayout(first_row_layout)
        
        # 第二行按钮：Clear 和 Hide/Show - 增大间距，避免重叠
        second_row_layout = QHBoxLayout()
        second_row_layout.setSpacing(10)  # 增大按钮间距
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(button_style)
        self.clear_btn.clicked.connect(self.clear_cursors_requested.emit)
        # 适中宽度，确保4个按钮都能显示
        self.clear_btn.setMinimumWidth(75)
        self.clear_btn.setMaximumWidth(75)
        second_row_layout.addWidget(self.clear_btn)
        
        self.toggle_visibility_btn = QPushButton("Hide")
        self.toggle_visibility_btn.setStyleSheet(button_style)
        self.toggle_visibility_btn.clicked.connect(self.toggle_cursors_visibility_requested.emit)
        # 适中宽度，确保4个按钮都能显示
        self.toggle_visibility_btn.setMinimumWidth(75)
        self.toggle_visibility_btn.setMaximumWidth(75)
        second_row_layout.addWidget(self.toggle_visibility_btn)
        
        button_main_layout.addLayout(second_row_layout)
        
        button_group.setLayout(button_main_layout)
        layout.addWidget(button_group)
        
        # Cursor列表 - 修复高度问题
        cursor_list_group = QGroupBox("Cursor List")
        cursor_list_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
                color: #333333;
            }
        """)
        
        cursor_list_layout = QVBoxLayout()
        cursor_list_layout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        cursor_list_layout.setSpacing(0)  # 减小间距
        
        self.cursor_list = QListWidget()
        self.cursor_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # 支持多选
        self.cursor_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.cursor_list.itemClicked.connect(self.on_cursor_item_clicked)
        
        # 设置合理的高度范围，去除最大高度限制以支持窗口拉伸
        self.cursor_list.setMinimumHeight(120)  # 保持最小高度
        # 去除最大高度限制，让列表可以随窗口拉伸
        
        # 设置大小策略，让组件能够正确适应父容器
        from PyQt6.QtWidgets import QSizePolicy
        self.cursor_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cursor_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #e3f2fd;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
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
        
        cursor_list_layout.addWidget(self.cursor_list, 1)  # 给cursor_list分配更大的权重，让它占据更多空间
        cursor_list_group.setLayout(cursor_list_layout)
        layout.addWidget(cursor_list_group, 1)  # 给cursor list组分配最大的伸缩权重
        
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
        self.pos_label = QLabel("Y Position:")  # 使用实例变量，以便动态更改
        self.pos_label.setStyleSheet("font-weight: normal; color: #333333;")
        pos_row.addWidget(self.pos_label)
        
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
        layout.addWidget(position_group, 0)  # 不给Position Control分配伸缩权重，保持固定尺寸
        
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
        layout.addWidget(self.stats_label, 0)  # 不给统计信息分配伸缩权重，保持固定尺寸
        
        # 设置整个面板的大小策略，确保能够适应父容器
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        self.setLayout(layout)
    
    def _should_skip_update(self):
        """判断是否应该跳过更新"""
        # 在tab切换时跳过更新
        if hasattr(self.parent_dialog, '_changing_tab') and self.parent_dialog._changing_tab:
            return True
        return self._skip_updates_during_tab_change
    
    def set_skip_updates(self, skip=True):
        """设置是否跳过更新"""
        self._skip_updates_during_tab_change = skip
    
    def _delayed_refresh(self):
        """延迟刷新cursor列表"""
        try:
            self._delayed_refresh_attempted = False  # 重置标志
            if self.parent_dialog and hasattr(self.parent_dialog, 'get_current_canvas'):
                canvas = self.parent_dialog.get_current_canvas()
                if canvas and hasattr(canvas, 'get_cursor_info'):
                    cursor_info = canvas.get_cursor_info()
                    print(f"[DEBUG] Delayed refresh found {len(cursor_info)} cursors")
                    if cursor_info:  # 只有在有数据时才刷新
                        self.refresh_cursor_list(cursor_info, force_update=True)
                    else:
                        print("[DEBUG] Delayed refresh still found no cursor data")
        except Exception as e:
            print(f"Error in delayed refresh: {e}")
            self._delayed_refresh_attempted = False
    
    def refresh_cursor_list(self, cursor_info_list, force_update=True):
        """刷新cursor列表显示"""
        if self._updating_data or (not force_update and self._should_skip_update()):
            return
            
        # 在强制更新模式下，如果数据为空，先检查是否是真实的空数据
        if force_update and not cursor_info_list:
            print("[DEBUG] refresh_cursor_list called with empty data in force_update mode")
            # 在强制更新模式下，如果是空数据，可能是数据还没有同步完成
            # 稍微延迟后再试一次，但要避免无限循环
            if not hasattr(self, '_delayed_refresh_attempted'):
                self._delayed_refresh_attempted = True
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self._delayed_refresh())
                return
            else:
                # 如果已经尝试过延迟刷新，直接清空列表
                self._delayed_refresh_attempted = False
            
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
                
                # 创建列表项 - 统一显示Y坐标（因为histogram中不显示cursor）
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
        """处理列表选择变化 - 增加防护"""
        if self._updating_data:
            return
            
        try:
            selected_items = self.cursor_list.selectedItems()
            
            # 更新删除按钮状态
            self.delete_selected_btn.setEnabled(len(selected_items) > 0)
            
            # 如果只选中一个项目，显示其位置信息
            if len(selected_items) == 1:
                cursor_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
                if cursor_id is not None:
                    self.selected_cursor_id = cursor_id
                    # 在发送信号前增加防护
                    if not self._updating_data:
                        self.cursor_selected.emit(cursor_id)
                    
                    # 获取cursor位置并更新position_spinbox
                    if self.parent_dialog and hasattr(self.parent_dialog, 'get_current_canvas'):
                        canvas = self.parent_dialog.get_current_canvas()
                        if canvas and hasattr(canvas, 'get_cursor_info'):
                            cursor_info = canvas.get_cursor_info()
                            for info in cursor_info:
                                if info['id'] == cursor_id:
                                    self.position_spinbox.setValue(info['y_position'])
                                    
                                    # 检查是否在histogram tab，如果是则不启用position control
                                    is_histogram_tab = False
                                    if (hasattr(self.parent_dialog, 'tab_widget') and 
                                        hasattr(self.parent_dialog.tab_widget, 'currentIndex')):
                                        is_histogram_tab = (self.parent_dialog.tab_widget.currentIndex() == 1)
                                    
                                    if not is_histogram_tab:
                                        self.position_spinbox.setEnabled(True)
                                    # 在histogram tab中保持禁用状态
                                    break
            else:
                # 多选或无选择时禁用位置控制
                self.selected_cursor_id = None
                # 检查是否在histogram tab，如果不是才禁用position control
                is_histogram_tab = False
                if (hasattr(self.parent_dialog, 'tab_widget') and 
                    hasattr(self.parent_dialog.tab_widget, 'currentIndex')):
                    is_histogram_tab = (self.parent_dialog.tab_widget.currentIndex() == 1)
                
                if not is_histogram_tab:
                    self.position_spinbox.setEnabled(False)
                # 在histogram tab中保持原有的禁用状态
                
                if len(selected_items) == 0 and not self._updating_data:
                    self.cursor_selected.emit(-1)  # 发送无选择信号
            
            self.update_statistics()
            
        except Exception as e:
            print(f"Error in on_selection_changed: {e}")
            import traceback
            traceback.print_exc()
    
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
    
    def update_visibility_button_text(self, cursors_visible):
        """更新隐藏/显示按钮的文本"""
        if cursors_visible:
            self.toggle_visibility_btn.setText("Hide")
        else:
            self.toggle_visibility_btn.setText("Show")
    
    def update_position_label_for_tab(self, is_histogram_tab=False):
        """根据当前tab更新position control状态"""
        if is_histogram_tab:
            # 在histogram tab中，由于cursor不可见，禁用Position Control
            self.pos_label.setText("Position (Hidden):")
            self.position_spinbox.setEnabled(False)
            self.position_spinbox.setStyleSheet("""
                QDoubleSpinBox {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 11px;
                    background-color: #f5f5f5;
                    color: #888888;
                }
            """)
        else:
            # 在main view中，cursor可见，正常显示Y Position
            self.pos_label.setText("Y Position:")
            # position_spinbox的启用状态由选中状态决定，这里只恢复样式
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
