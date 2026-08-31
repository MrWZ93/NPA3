#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件系统辅助工具模块
支持复制文件、复制路径以及在系统文件管理器中打开文件所在目录
"""

import os
import sys
import subprocess
from PyQt6.QtCore import QUrl, QMimeData, Qt
from PyQt6.QtWidgets import QApplication, QMenu
from PyQt6.QtGui import QDesktopServices


def copy_file_to_clipboard(file_path: str) -> bool:
    """将文件复制到系统剪贴板 (可在文件管理器中直接粘贴)"""
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        mime_data = QMimeData()
        url = QUrl.fromLocalFile(os.path.abspath(file_path))
        mime_data.setUrls([url])
        QApplication.clipboard().setMimeData(mime_data)
        return True
    except Exception as e:
        print(f"Error copying file to clipboard: {e}")
        return False


def copy_path_to_clipboard(file_path: str) -> bool:
    """将文件/文件夹绝对路径复制到剪贴板"""
    if not file_path:
        return False
    try:
        abs_path = os.path.abspath(file_path)
        QApplication.clipboard().setText(abs_path)
        return True
    except Exception as e:
        print(f"Error copying path to clipboard: {e}")
        return False


def open_file_location(file_path: str) -> bool:
    """在系统的文件管理器中打开文件/文件夹所在目录"""
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        abs_path = os.path.abspath(file_path)
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', '-R', abs_path], check=False)
        elif sys.platform == 'win32':  # Windows
            subprocess.run(['explorer', '/select,', os.path.normpath(abs_path)], check=False)
        else:  # Linux / Unix
            dir_path = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(dir_path))
        return True
    except Exception as e:
        print(f"Error opening file location: {e}")
        return False


def show_file_context_menu(parent_widget, pos, file_path: str, status_bar=None):
    """
    在指定位置弹出英文右键菜单：
    - Copy File
    - Copy Path
    - Open File Location
    """
    if not file_path or not os.path.exists(file_path):
        return

    menu = QMenu(parent_widget)
    copy_file_act = menu.addAction("Copy File")
    copy_path_act = menu.addAction("Copy Path")
    open_loc_act = menu.addAction("Open File Location")

    global_pos = parent_widget.mapToGlobal(pos)
    selected_act = menu.exec(global_pos)

    file_name = os.path.basename(file_path)

    if selected_act == copy_file_act:
        if copy_file_to_clipboard(file_path):
            if status_bar:
                status_bar.showMessage(f"Copied file: {file_name}")
    elif selected_act == copy_path_act:
        if copy_path_to_clipboard(file_path):
            if status_bar:
                status_bar.showMessage(f"Copied path: {file_path}")
    elif selected_act == open_loc_act:
        if open_file_location(file_path):
            if status_bar:
                status_bar.showMessage(f"Opened file location for {file_name}")
