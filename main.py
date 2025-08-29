#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主应用入口文件
"""

import sys
import os
import signal
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from gui.main_window import FileExplorerApp
from gui.styles import GLOBAL_STYLE, StyleHelper
# 删除主题切换功能
# from gui.themes import apply_theme
from utils.config_manager import ConfigManager
from gui.main_window_extension import extend_main_window
# 删除主题切换功能
# from gui.integrate_theme_switcher import apply_patches

def check_dependencies():
    """检查依赖项是否已安装"""
    required_packages = ['numpy', 'pandas', 'matplotlib', 'scipy', 'h5py', 'PyQt6']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        return False, missing_packages
    return True, []

def create_splash_screen():
    """创建闪屏窗口"""
    # 如果不存在自定义闪屏图像，则创建一个简单的纯色图像
    splash_img = QPixmap(400, 300)
    splash_img.fill(Qt.GlobalColor.white)
    splash = QSplashScreen(splash_img)
    
    # 添加闪屏文本
    splash.showMessage(
        "Loading NPA Data Visualizer...", 
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
        Qt.GlobalColor.darkBlue
    )
    return splash

if __name__ == "__main__":
    # 处理信号，确保硬关销点也有效
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 检查是否运行在虚拟环境中
    in_venv = sys.prefix != sys.base_prefix
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用Fusion样式，它在所有平台上看起来都很现代
    app.setApplicationName("NPA Data Visualizer")
    
    # 应用全局样式表
    app.setStyleSheet(GLOBAL_STYLE)
    
    # 删除主题切换功能
    config_manager = ConfigManager()
    
    # 显示闪屏
    splash = create_splash_screen()
    splash.show()
    
    # 为GUI处理事件提供时间
    app.processEvents()
    
    # 检查依赖项
    deps_ok, missing_deps = check_dependencies()
    if not deps_ok:
        # 如果缺少依赖项，显示警告并继续（而不是直接退出）
        missing_str = ", ".join(missing_deps)
        QMessageBox.warning(
            None, 
            "Missing Dependencies", 
            f"The following required packages are missing: {missing_str}\n\n"
            "The application may not function correctly.\n"
            "Please install these packages using pip:"
            f"\n\npip install {' '.join(missing_deps)}"
        )
    
    # 修复导入问题
    try:
        # 尝试修夌ConfigManager导入
        import types
        import gui.main_window
        from utils.config_manager import ConfigManager
        
        # 如果主窗口模块中没有ConfigManager，添加它
        if not hasattr(gui.main_window, 'ConfigManager'):
            setattr(gui.main_window, 'ConfigManager', ConfigManager)
            print("修复 ConfigManager 导入")
    except Exception as e:
        print(f"导入修复时出错: {str(e)}")
    
    # 扩展主窗口类
    FileExplorerApp = extend_main_window(FileExplorerApp)
    
    # 删除主题切换功能
    # apply_patches()
    
    # 显示主窗口
    window = FileExplorerApp()
    
    # 设置菜单栏
    window.setup_menu_bar()
    
    # 等待一小段时间后关闭闪屏
    QTimer.singleShot(1500, splash.close)
    
    # 延迟显示主窗口，使闪屏效果更明显
    QTimer.singleShot(1500, window.show)
    
    # 设置应用程序的aboutToQuit信号处理，确保线程在退出前被清理
    def cleanup():
        # 强制清理任何可能还在运行的线程
        import threading
        import pandas as pd
        
        # 强制Pandas清理已打开的资源
        try:
            for thread in threading.enumerate():
                if thread is not threading.main_thread():
                    if hasattr(thread, 'join') and thread.is_alive():
                        # 尝试在短时间内等待线程结束
                        thread.join(0.1)
        except Exception as e:
            print(f"清理线程时出错: {str(e)}")
    
    app.aboutToQuit.connect(cleanup)
    
    try:
        sys.exit(app.exec())
    except SystemExit:
        # 再次强制清理
        cleanup()
