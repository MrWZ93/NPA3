#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Popup Cursor Manager - 弹窗式cursor管理器（修复版）
提供紧贴主窗口右侧的cursor管理界面
修复了窗口交互异常和递归调用问题
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QDoubleSpinBox,
                             QMessageBox, QGroupBox, QFrame, QMainWindow, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor
import numpy as np


class PopupCursorManager(QDialog):  # 改用QDialog而不是QWidget
    """弹窗式Cursor管理器界面（彻底修复版）"""
    
    # 定义信号
    cursor_position_changed = pyqtSignal(int, float)  # cursor_id, new_position
    cursor_selection_changed = pyqtSignal(int)  # cursor_id (-1 for none)
    cursor_deleted = pyqtSignal(int)  # cursor_id
    
    def __init__(self, parent=None):
        # 使用标准Dialog设置
        super().__init__(parent)
        self.original_parent = parent
        self.plot_widget = None
        self.selected_cursor_id = None
        
        # 简化窗口设置，使用标准对话框模式
        self.setWindowTitle("Cursor Manager")
        self.setModal(False)  # 非模态对话框，允许与其他窗口交互
        
        # 【修复问题2】监听父窗口关闭事件
        if parent:
            parent.installEventFilter(self)
        
        # 设置初始尺寸，与histogram窗口高度一致
        self.resize(380, 800)  # 高度调整为800，与histogram窗口一致
        self.setMinimumSize(300, 400)
        self.setMaximumSize(800, 1200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 【修复点3】添加递归调用防护机制
        self._updating_data = False
        self._refreshing_list = False
        self._last_cursor_info_hash = None
        
        # 【修复点4】设置数据实时更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data_from_plot)
        self.update_timer.setSingleShot(False)
        self._user_interacting = False
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面 - 统一风格设计"""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # 标题标签 - 简洁设计
        title = QLabel("Cursor Manager")
        title.setStyleSheet("""
            font-weight: bold; 
            font-size: 16px; 
            color: #333333; 
            margin-bottom: 8px;
            padding: 5px 0;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 操作按钮组 - 统一简洁风格
        button_group = QGroupBox("Operations")
        button_group.setStyleSheet("""
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
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        
        # 统一的按钮样式 - 简洁专业
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
                color: #333333;
                min-height: 16px;
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
        
        # 添加cursor按钮
        self.add_btn = QPushButton("Add Cursor")
        self.add_btn.setStyleSheet(button_style)
        self.add_btn.clicked.connect(self.add_cursor)
        button_layout.addWidget(self.add_btn)
        
        # 删除选中cursor按钮
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet(button_style)
        self.delete_btn.clicked.connect(self.delete_selected_cursor)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        # 清除所有cursor按钮
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setStyleSheet(button_style)
        self.clear_all_btn.clicked.connect(self.clear_all_cursors)
        button_layout.addWidget(self.clear_all_btn)
        
        button_group.setLayout(button_layout)
        layout.addWidget(button_group)
        
        # Cursor列表 - 扩大显示区域
        list_group = QGroupBox("Cursor List")
        list_group.setStyleSheet("""
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
        list_layout = QVBoxLayout()
        
        self.cursor_list = QListWidget()
        # 确保列表控件能够正常接收用户输入
        self.cursor_list.itemClicked.connect(self.on_cursor_item_clicked)
        self.cursor_list.itemSelectionChanged.connect(self.on_selection_changed)
        # 创建自定义列表类来处理空白处点击
        self.cursor_list.mousePressEvent = self.cursor_list_mouse_press_event
        self.cursor_list.setMinimumHeight(120)
        # 设置滚动条
        self.cursor_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cursor_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cursor_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.cursor_list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.cursor_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        # 设置选择模式
        self.cursor_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
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
        list_layout.addWidget(self.cursor_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
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
        # 添加用户交互检测
        self.position_spinbox.valueChanged.connect(self.on_position_changed)
        self.position_spinbox.editingFinished.connect(self.on_position_editing_finished)
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
        
        # 实时统计信息区域
        stats_group = QGroupBox("Cursor Statistics")
        stats_group.setStyleSheet("""
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
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel("Total Cursors: 0\nSelected: None")
        self.stats_label.setStyleSheet("""
            color: #555555; 
            font-size: 11px; 
            line-height: 1.4;
            padding: 5px;
        """)
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 键盘操作说明
        info_group = QGroupBox("Keyboard Shortcuts")
        info_group.setStyleSheet("""
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
        info_layout = QVBoxLayout()
        
        info_text = QLabel(
            "• Click cursor to select\n"
            "• Delete/Backspace: Remove cursor\n"
            "• ↑/↓: Adjust cursor position\n"
            "• Click empty area to deselect\n"
            "• Right-click to add cursor"
        )
        info_text.setStyleSheet("""
            color: #666666; 
            font-size: 10px; 
            line-height: 1.3;
            padding: 5px;
        """)
        info_layout.addWidget(info_text)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        self.setLayout(layout)
        
    def eventFilter(self, obj, event):
        """事件过滤器 - 监听父窗口关闭事件"""
        # 【修复问题2】当父窗口关闭时，同时关闭cursor manager
        if obj == self.original_parent and event.type() == event.Type.Close:
            self.force_close()
        return super().eventFilter(obj, event)
        
    def show_popup(self):
        """显示弹窗并定位到合适位置"""
        if self.original_parent:
            # 获取原始父窗口的几何信息
            parent_geom = self.original_parent.geometry()
            
            # 定位到父窗口右侧，窗口完全平齐
            x = parent_geom.x() + parent_geom.width() + 5  # 紧贴右侧，间距5像素
            y = parent_geom.y()  # y坐标完全对齐，窗口顶部平齐
            
            self.move(x, y)
        
        # 显示对话框
        self.show()
        self.raise_()
        self.activateWindow()
        
        # 启动数据实时更新
        self.start_real_time_updates()
        
    def closeEvent(self, event):
        """窗口关闭时停止定时器"""
        self.stop_real_time_updates()
        # 移除事件过滤器
        if self.original_parent:
            self.original_parent.removeEventFilter(self)
        # 接受关闭事件
        event.accept()
    
    def force_close(self):
        """强制关闭窗口（用于程序退出时）"""
        self.stop_real_time_updates()
        self.close()
    
    def focusInEvent(self, event):
        """获得焦点时的处理"""
        super().focusInEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        super().mousePressEvent(event)
        
    def start_real_time_updates(self):
        """启动实时数据更新 - 降低频率，避免干扰用户交互"""
        if not self.update_timer.isActive():
            # 降低更新频率，减少系统负载和交互干扰
            self.update_timer.start(500)  # 每500ms更新一次
    
    def stop_real_time_updates(self):
        """停止实时数据更新"""
        if self.update_timer.isActive():
            self.update_timer.stop()
    
    def update_data_from_plot(self):
        """从plot更新数据 - 添加递归防护和变化检测"""
        # 递归调用防护和用户交互检测
        if self._updating_data or self._user_interacting:
            return
            
        if not self.plot_widget or not self.isVisible():
            return
            
        try:
            self._updating_data = True
            
            # 获取当前cursor信息
            cursor_info = self.plot_widget.get_cursor_info() if hasattr(self.plot_widget, 'get_cursor_info') else []
            
            # 检测数据是否真的发生了变化，避免不必要的更新
            cursor_info_hash = self._calculate_cursor_info_hash(cursor_info)
            if cursor_info_hash == self._last_cursor_info_hash:
                return  # 数据没有变化，跳过更新
            
            self._last_cursor_info_hash = cursor_info_hash
            
            # 只有在数据确实发生变化时才更新UI
            self.refresh_cursor_list()
            self.update_statistics()
            
        except Exception as e:
            print(f"Error in update_data_from_plot: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._updating_data = False
    
    def _calculate_cursor_info_hash(self, cursor_info):
        """计算cursor信息的哈希值，用于检测变化"""
        try:
            if not cursor_info:
                return 0
            
            # 创建一个简单的哈希值
            hash_str = ""
            for info in sorted(cursor_info, key=lambda x: x.get('id', 0)):
                hash_str += f"{info.get('id', 0)}_{info.get('y_position', 0):.4f}_{info.get('selected', False)}_"
            
            return hash(hash_str)
        except:
            return 0
        
    def set_plot_widget(self, plot_widget):
        """设置关联的HistogramPlot对象 - 【修复问题2】保持cursor数据持久性"""
        # 保存当前cursor数据
        saved_cursor_data = None
        saved_selected_cursor_id = self.selected_cursor_id
        
        if self.plot_widget and hasattr(self.plot_widget, 'cursors'):
            # 保存当前cursor数据
            saved_cursor_data = [cursor.copy() for cursor in self.plot_widget.cursors]
            print(f"Saving {len(saved_cursor_data)} cursors before switching plot widget")
        
        # 设置新的plot widget
        self.plot_widget = plot_widget
        
        # 如果有保存的cursor数据，在新widget中恢复
        if saved_cursor_data and plot_widget:
            # 检查新widget是否已经有cursor数据
            if not hasattr(plot_widget, 'cursors') or not plot_widget.cursors:
                # 如果新widget没有cursor数据，则恢复保存的数据
                print(f"Restoring {len(saved_cursor_data)} cursors to new plot widget")
                plot_widget.cursors = saved_cursor_data
                if hasattr(plot_widget, 'cursor_counter'):
                    plot_widget.cursor_counter = max([c.get('id', 0) for c in saved_cursor_data], default=0)
                # 恢复选中状态
                for cursor in plot_widget.cursors:
                    cursor['selected'] = (cursor.get('id') == saved_selected_cursor_id)
                if saved_selected_cursor_id is not None:
                    plot_widget.selected_cursor = next(
                        (c for c in plot_widget.cursors if c.get('id') == saved_selected_cursor_id), 
                        None
                    )
                    self.selected_cursor_id = saved_selected_cursor_id
                # 刷新cursor显示
                if hasattr(plot_widget, 'refresh_cursors_for_histogram_mode'):
                    plot_widget.refresh_cursors_for_histogram_mode()
                elif hasattr(plot_widget, 'refresh_cursors_after_plot_update'):
                    plot_widget.refresh_cursors_after_plot_update()
        
        # 刷新cursor列表显示
        self.refresh_cursor_list()
        
        # 连接plot的cursor相关信号，避免重复连接
        if hasattr(plot_widget, 'cursor_deselected'):
            try:
                plot_widget.cursor_deselected.disconnect(self.deselect_cursor)
            except:
                pass  # 如果没有连接则忽略
            plot_widget.cursor_deselected.connect(self.deselect_cursor)
            
        # 连接plot的cursor选中状态变化信号（如果存在）
        if hasattr(plot_widget, 'cursor_selected'):
            try:
                plot_widget.cursor_selected.disconnect(self.on_plot_cursor_selected)
            except:
                pass
            plot_widget.cursor_selected.connect(self.on_plot_cursor_selected)
    
    def on_plot_cursor_selected(self, cursor_id):
        """处理plot中cursor被选中的信号 - 添加递归防护"""
        if self._updating_data:
            return
            
        try:
            # 如果选中状态发生变化，更新manager状态
            if cursor_id != self.selected_cursor_id:
                self.selected_cursor_id = cursor_id
                
                # 更新UI状态
                if cursor_id is not None:
                    cursor_info = self.plot_widget.get_cursor_info()
                    for info in cursor_info:
                        if info['id'] == cursor_id:
                            # 标记用户交互状态
                            self._user_interacting = True
                            self.position_spinbox.setValue(info['y_position'])
                            self.position_spinbox.setEnabled(True)
                            self.delete_btn.setEnabled(True)
                            self._user_interacting = False
                            break
                else:
                    self.position_spinbox.setEnabled(False)
                    self.delete_btn.setEnabled(False)
                
                # 刷新列表显示
                self.refresh_cursor_list()
                self.update_statistics()
                
        except Exception as e:
            print(f"Error handling plot cursor selection: {e}")
            import traceback
            traceback.print_exc()
        
    def add_cursor(self):
        """添加新的cursor"""
        if not self.plot_widget:
            QMessageBox.warning(self, "Warning", "No plot widget connected!")
            return
        
        self._user_interacting = True  # 标记用户交互
        try:
            cursor_id = self.plot_widget.add_cursor()
            if cursor_id is not None:
                # 选中新添加的cursor
                self.select_cursor(cursor_id)
                self.refresh_cursor_list()
                self.update_statistics()
        finally:
            self._user_interacting = False
            
    def delete_selected_cursor(self):
        """删除当前选中的cursor（修复版）"""
        if not self.plot_widget or self.selected_cursor_id is None:
            return
        
        self._user_interacting = True  # 标记用户交互
        try:
            # 记录删除前的cursor ID
            deleted_id = self.selected_cursor_id
            
            # 执行删除操作
            success = self.plot_widget.remove_cursor(self.selected_cursor_id)
            if success:
                print(f"Deleted cursor with ID: {deleted_id}")
                
                # 发送删除信号
                self.cursor_deleted.emit(deleted_id)
                
                # 清除当前选中状态
                self.selected_cursor_id = None
                self.position_spinbox.setEnabled(False)
                self.delete_btn.setEnabled(False)
                
                # 重新编号cursor列表（这会重新分配连续ID）
                self.reorder_cursor_ids()
                
                # 刷新显示和统计
                self.refresh_cursor_list()
                self.update_statistics()
                
                print(f"After deletion, remaining cursors: {len(self.plot_widget.cursors)}")
        finally:
            self._user_interacting = False
            
    def clear_all_cursors(self):
        """清除所有cursor"""
        if not self.plot_widget:
            return
            
        reply = QMessageBox.question(self, "Confirm", "Clear all cursors?",
                                   QMessageBox.StandardButton.Yes | 
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self._user_interacting = True  # 标记用户交互
            try:
                success = self.plot_widget.clear_all_cursors()
                if success:
                    self.selected_cursor_id = None
                    self.position_spinbox.setEnabled(False)
                    self.delete_btn.setEnabled(False)
                    self.refresh_cursor_list()
                    self.update_statistics()
                    # 重置cursor计数器
                    if hasattr(self.plot_widget, 'cursor_counter'):
                        self.plot_widget.cursor_counter = 0
            finally:
                self._user_interacting = False
                
    def cursor_list_mouse_press_event(self, event):
        """处理cursor列表的鼠标按下事件，支持点击空白处取消选中"""
        # 获取点击位置的item
        item = self.cursor_list.itemAt(event.pos())
        
        if item is None:
            # 点击的是空白处，清除选择
            self.cursor_list.clearSelection()
            self.cursor_list.setCurrentItem(None)
            self.deselect_cursor()
        else:
            # 点击的是有效item，调用原始的mousePressEvent
            QListWidget.mousePressEvent(self.cursor_list, event)
            
    def on_selection_changed(self):
        """处理列表选择变化"""
        current_item = self.cursor_list.currentItem()
        if current_item:
            cursor_id = current_item.data(Qt.ItemDataRole.UserRole)
            if cursor_id is not None:
                self.select_cursor(cursor_id)
        else:
            # 如果没有选中的item，取消选中
            self.deselect_cursor()
    
    def on_position_editing_finished(self):
        """处理位置编辑完成"""
        if not self.plot_widget or self.selected_cursor_id is None:
            return
        
        value = self.position_spinbox.value()
        self._user_interacting = True
        try:
            # 更新cursor位置
            success = self.plot_widget.update_cursor_position(self.selected_cursor_id, value)
            if success:
                # 重新绘制
                self.plot_widget.draw()
                # 发送信号
                self.cursor_position_changed.emit(self.selected_cursor_id, value)
                # 刷新列表
                self.refresh_cursor_list()
        finally:
            self._user_interacting = False
            
    def on_cursor_item_clicked(self, item):
        """处理cursor列表项被点击"""
        self._user_interacting = True  # 标记用户交互
        try:
            cursor_id = item.data(Qt.ItemDataRole.UserRole)
            if cursor_id is not None:
                self.select_cursor(cursor_id)
                # 确保item在列表中被选中
                self.cursor_list.setCurrentItem(item)
            else:
                print("Warning: Clicked item has no cursor ID data")
        except Exception as e:
            print(f"Error selecting cursor: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._user_interacting = False
            
    def select_cursor(self, cursor_id):
        """选中指定的cursor - 添加递归防护"""
        if not self.plot_widget or self._updating_data:
            return
            
        # 在plot中选中cursor
        success = self.plot_widget.select_cursor(cursor_id)
        if not success and cursor_id is not None:
            print(f"Failed to select cursor {cursor_id} in plot")
            return
        
        # 更新UI状态
        self.selected_cursor_id = cursor_id
        
        if cursor_id is not None:
            # 获取cursor信息并更新位置输入框
            cursor_info = self.plot_widget.get_cursor_info()
            cursor_found = False
            for info in cursor_info:
                if info['id'] == cursor_id:
                    self.position_spinbox.setValue(info['y_position'])
                    self.position_spinbox.setEnabled(True)
                    self.delete_btn.setEnabled(True)
                    cursor_found = True
                    break
            
            if not cursor_found:
                print(f"Warning: Cursor {cursor_id} not found in cursor info")
                self.selected_cursor_id = None
                self.position_spinbox.setEnabled(False)
                self.delete_btn.setEnabled(False)
        else:
            self.position_spinbox.setEnabled(False)
            self.delete_btn.setEnabled(False)
            
        # 刷新列表显示选中状态
        self.refresh_cursor_list()
        self.update_statistics()
        
        # 发送信号
        self.cursor_selection_changed.emit(cursor_id if cursor_id is not None else -1)
        
    def deselect_cursor(self):
        """取消选中cursor"""
        self.select_cursor(None)
        
    def on_position_changed(self, value):
        """处理位置输入框值变化"""
        if not self.plot_widget or self.selected_cursor_id is None or self._updating_data:
            return
        
        self._user_interacting = True  # 标记用户交互
        try:
            # 更新cursor位置
            success = self.plot_widget.update_cursor_position(self.selected_cursor_id, value)
            if success:
                # 重新绘制
                self.plot_widget.draw()
                # 发送信号
                self.cursor_position_changed.emit(self.selected_cursor_id, value)
                # 刷新列表
                self.refresh_cursor_list()
        finally:
            self._user_interacting = False
            
    def refresh_cursor_list(self):
        """刷新cursor列表显示 - 添加递归防护和优化"""
        # 递归调用防护
        if self._refreshing_list or not self.plot_widget:
            return
            
        try:
            self._refreshing_list = True
            
            # 获取cursor信息
            cursor_info = self.plot_widget.get_cursor_info()
            
            # 清空列表 - 先断开信号连接避免触发多余事件
            self.cursor_list.itemClicked.disconnect()
            self.cursor_list.clear()
            
            # 按照cursor ID排序，确保顺序正确
            sorted_info = sorted(cursor_info, key=lambda x: x['id'])
            
            selected_item = None  # 记录需要选中的项
            
            for i, info in enumerate(sorted_info):
                cursor_id = info['id']
                y_pos = info['y_position']
                color = info['color']
                is_selected = info.get('selected', False)
                
                # 创建列表项 - 使用连续编号（从1开始）
                display_num = i + 1
                item_text = f"Cursor {display_num}: Y = {y_pos:.4f}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, cursor_id)
                
                # 设置颜色指示
                color_obj = QColor(color)
                
                # 根据选中状态设置不同的背景颜色
                if is_selected or cursor_id == self.selected_cursor_id:
                    item.setBackground(color_obj.lighter(140))  # 更深的高亮
                    item.setForeground(QColor('#1976d2'))  # 蓝色文字
                    selected_item = item  # 记录选中项
                else:
                    item.setBackground(color_obj.lighter(180))  # 正常背景
                    
                self.cursor_list.addItem(item)
                
            # 恢复信号连接
            self.cursor_list.itemClicked.connect(self.on_cursor_item_clicked)
            
            # 设置选中项（如果有）
            if selected_item:
                self.cursor_list.setCurrentItem(selected_item)
                selected_item.setSelected(True)
                
            # 更新按钮状态
            has_cursors = len(cursor_info) > 0
            self.clear_all_btn.setEnabled(has_cursors)
            
        except Exception as e:
            print(f"Error refreshing cursor list: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._refreshing_list = False
        
    def reorder_cursor_ids(self):
        """重新排序cursor ID - 删除后重新编号（修复版）"""
        if not self.plot_widget or not hasattr(self.plot_widget, 'cursors'):
            return
        
        # 获取当前所有cursor，按照ID排序保持稳定性
        cursors = self.plot_widget.cursors
        if len(cursors) == 0:
            if hasattr(self.plot_widget, 'cursor_counter'):
                self.plot_widget.cursor_counter = 0
            return
            
        # 先按照当前ID排序，保持相对顺序
        cursors_sorted = sorted(cursors, key=lambda c: c.get('id', 0))
        
        # 重新分配连续的ID，从1开始
        old_to_new_id_map = {}
        for i, cursor in enumerate(cursors_sorted):
            old_id = cursor.get('id')
            new_id = i + 1
            old_to_new_id_map[old_id] = new_id
            cursor['id'] = new_id
            
            # 如果当前选中的cursor ID发生了变化，更新选中状态
            if old_id == self.selected_cursor_id:
                self.selected_cursor_id = new_id
        
        # 更新cursor列表顺序
        self.plot_widget.cursors = cursors_sorted
        
        # 重置cursor计数器为下一个可用ID
        if hasattr(self.plot_widget, 'cursor_counter'):
            self.plot_widget.cursor_counter = len(cursors)
        
        # 确保所有cursor的selected状态正确
        for cursor in self.plot_widget.cursors:
            cursor['selected'] = (cursor['id'] == self.selected_cursor_id)
        
        # 刷新显示
        self.refresh_cursor_list()
        print(f"Reordered cursors: {[c['id'] for c in cursors_sorted]}")
        
    def update_statistics(self):
        """更新统计信息"""
        if not self.plot_widget:
            total_count = 0
            selected_info = "None"
        else:
            cursor_info = self.plot_widget.get_cursor_info()
            total_count = len(cursor_info)
            
            if self.selected_cursor_id is not None:
                # 找到选中cursor在列表中的显示序号
                sorted_info = sorted(cursor_info, key=lambda x: x['id'])
                display_num = None
                for i, info in enumerate(sorted_info):
                    if info['id'] == self.selected_cursor_id:
                        display_num = i + 1
                        break
                selected_info = f"Cursor {display_num}" if display_num else "None"
            else:
                selected_info = "None"
        
        self.stats_label.setText(f"Total Cursors: {total_count}\nSelected: {selected_info}")
        
    def update_from_plot(self):
        """从plot更新界面状态 - 增强同步逻辑，添加递归防护"""
        if not self.plot_widget or self._updating_data:
            return
            
        try:
            self._updating_data = True
            
            # 获取plot中当前选中的cursor
            plot_selected_cursor = None
            if hasattr(self.plot_widget, 'selected_cursor') and self.plot_widget.selected_cursor:
                plot_selected_cursor = self.plot_widget.selected_cursor.get('id')
            
            # 如果plot中的选中状态与manager不同，更新manager状态
            if plot_selected_cursor != self.selected_cursor_id:
                self.selected_cursor_id = plot_selected_cursor
                
                # 更新UI状态
                if self.selected_cursor_id is not None:
                    cursor_info = self.plot_widget.get_cursor_info()
                    for info in cursor_info:
                        if info['id'] == self.selected_cursor_id:
                            self.position_spinbox.setValue(info['y_position'])
                            self.position_spinbox.setEnabled(True)
                            self.delete_btn.setEnabled(True)
                            break
                else:
                    self.position_spinbox.setEnabled(False)
                    self.delete_btn.setEnabled(False)
            
            # 刷新列表显示
            self.refresh_cursor_list()
            self.update_statistics()
            
            # 检查当前选中的cursor是否还存在
            if self.selected_cursor_id is not None:
                cursor_info = self.plot_widget.get_cursor_info()
                cursor_exists = any(info['id'] == self.selected_cursor_id for info in cursor_info)
                
                if not cursor_exists:
                    self.selected_cursor_id = None
                    self.position_spinbox.setEnabled(False)
                    self.delete_btn.setEnabled(False)
                    self.update_statistics()
                    
        except Exception as e:
            print(f"Error in update_from_plot: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._updating_data = False
