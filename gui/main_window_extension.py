#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口扩展功能 - 添加主题切换等功能
"""

from PyQt6.QtWidgets import QMainWindow, QMenuBar, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
# 删除主题切换相关导入
# from gui.themes import apply_theme
import sys

def setup_menu_bar(self):
    """设置菜单栏"""
    if not hasattr(self, 'config_manager'):
        from utils.config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
    # 创建菜单栏
    menu_bar = self.menuBar()
    
    # 添加"文件"菜单
    file_menu = menu_bar.addMenu("File")
    
    # 添加"打开文件夹"选项
    open_action = QAction(QIcon.fromTheme("folder-open"), "Open Folder", self)
    open_action.triggered.connect(self.browse_folder)
    file_menu.addAction(open_action)
    
    # 添加分隔符
    file_menu.addSeparator()
    
    # 添加"退出"选项
    exit_action = QAction(QIcon.fromTheme("application-exit"), "Exit", self)
    exit_action.triggered.connect(self.close)
    file_menu.addAction(exit_action)
    
    # 删除主题切换相关菜单
    
    # 添加"帮助"菜单
    help_menu = menu_bar.addMenu("Help")
    
    # 添加"关于"选项
    about_action = QAction(QIcon.fromTheme("help-about"), "About", self)
    about_action.triggered.connect(self.show_about)
    help_menu.addAction(about_action)
    
    # 添加"帮助"选项
    help_action = QAction(QIcon.fromTheme("help-contents"), "Help", self)
    help_action.triggered.connect(self.show_help)
    help_menu.addAction(help_action)
    
    return menu_bar

# 删除主题切换相关函数

def show_about(self):
    """显示关于对话框"""
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import Qt
    
    about_text = """
    <h2>NP_Analyzer</h2>
    <p>Version 2.1</p>
    <p>A multi-format data visualization and analysis tool for TDMS, H5, ABF, and CSV files.</p>
    <p>Developed for scientific data processing and visualization.</p>
    <p>&copy; 2025 NPA Visualizer Team</p>
    """
    
    msg_box = QMessageBox(self)
    msg_box.setWindowTitle("About NP_Analyzer")
    msg_box.setTextFormat(Qt.TextFormat.RichText)
    msg_box.setText(about_text)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.exec()

# 扩展主窗口类
def extend_main_window(cls):
    """动态扩展主窗口类"""
    if not hasattr(cls, 'setup_menu_bar'):
        cls.setup_menu_bar = setup_menu_bar
    # 删除主题切换相关函数注册
    if not hasattr(cls, 'show_about'):
        cls.show_about = show_about
    return cls
