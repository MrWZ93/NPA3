#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理文件组件
"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                            QListWidgetItem, QInputDialog, QLineEdit, QMessageBox,
                            QApplication, QPushButton)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

from gui.styles import COLORS, StyleHelper

class ProcessedFilesWidget(QWidget):
    """处理后文件显示区域"""
    def __init__(self, parent=None):
        super(ProcessedFilesWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)  # 减小边距使内容更紧凑
        
        # 标题和操作按钮
        header_layout = QHBoxLayout()
        self.title_label = StyleHelper.header_label("Processed Files")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        
        # 清理文件和操作按钮
        self.actions_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.setIconSize(QSize(16, 16))
        self.refresh_button.setMaximumWidth(100)
        self.refresh_button.setMinimumHeight(36)
        self.refresh_button.setProperty("class", "secondary")
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.setIcon(QIcon.fromTheme("edit-clear"))
        self.clear_button.setIconSize(QSize(16, 16))
        self.clear_button.setMaximumWidth(100)
        self.clear_button.setMinimumHeight(36)
        self.clear_button.setProperty("class", "secondary")
        
        self.actions_layout.addWidget(self.refresh_button)
        self.actions_layout.addWidget(self.clear_button)
        
        header_layout.addLayout(self.actions_layout)
        
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.files_list.itemDoubleClicked.connect(self.rename_file)
        self.files_list.setAlternatingRowColors(True)
        
        # 启用工具提示和文件名缩略
        self.files_list.setMouseTracking(True)
        self.files_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.files_list.setStyleSheet("""
            QListWidget {
                font-size: 11pt;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
            }
            QListWidget::item:alternate {
                background-color: #f8f9fa;
            }
        """)
        
        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.files_list)
        
        self.setLayout(self.layout)
        
        # 存储文件路径的字典
        self.file_paths = {}
        
        # 连接按钮信号
        self.refresh_button.clicked.connect(self.refresh_files)
        self.clear_button.clicked.connect(self.clear_files)
    
    def add_file(self, file_path):
        """添加处理后文件"""
        file_name = os.path.basename(file_path)
        item = QListWidgetItem(file_name)
        item.setToolTip(file_path)  # 设置完整路径为工具提示
        self.files_list.addItem(item)
        self.file_paths[file_name] = file_path
    
    def rename_file(self, item):
        """重命名文件"""
        old_name = item.text()
        old_path = self.file_paths[old_name]
        
        new_name, ok = QInputDialog.getText(
            self, "Rename File", "Enter new filename:", 
            QLineEdit.EchoMode.Normal, old_name
        )
        
        if ok and new_name:
            dir_path = os.path.dirname(old_path)
            new_path = os.path.join(dir_path, new_name)
            
            try:
                # 如果新文件名没有扩展名，添加.h5扩展名
                if not os.path.splitext(new_name)[1]:
                    new_path += '.h5'
                    new_name += '.h5'
                
                os.rename(old_path, new_path)
                item.setText(new_name)
                
                # 更新路径字典
                del self.file_paths[old_name]
                self.file_paths[new_name] = new_path
                
                QMessageBox.information(self, "Success", f"File renamed to {new_name}")
                
                # 更新主窗口的状态栏
                # 首先获取父窗口
                main_window = QApplication.activeWindow()
                from gui.main_window import FileExplorerApp
                if isinstance(main_window, FileExplorerApp):
                    main_window.statusBar.showMessage(f"File renamed: {old_name} → {new_name}")
            
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Rename failed: {str(e)}")
    
    def get_selected_file(self):
        """获取选中的文件路径"""
        items = self.files_list.selectedItems()
        if items:
            return self.file_paths[items[0].text()]
        return None
        
    def refresh_files(self):
        """刷新文件列表"""
        from gui.main_window import FileExplorerApp
        main_window = QApplication.activeWindow()
        if isinstance(main_window, FileExplorerApp):
            main_window.scan_processed_files()
            main_window.statusBar.showMessage("File list refreshed")
    
    def clear_files(self):
        """清空文件列表"""
        if self.files_list.count() > 0:
            result = QMessageBox.question(
                self, "Clear List", 
                "Do you want to clear the file list? This won't delete the actual files.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                self.files_list.clear()
                self.file_paths = {}
                
                # 更新状态栏
                from gui.main_window import FileExplorerApp
                main_window = QApplication.activeWindow()
                if isinstance(main_window, FileExplorerApp):
                    main_window.statusBar.showMessage("File list cleared")
