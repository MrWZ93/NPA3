#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口UI组件
"""

import os
import sys
import numpy as np

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QLabel, QLineEdit, QPushButton, QFileDialog, 
                            QListWidget, QListWidgetItem, QSplitter, QMessageBox,
                            QDialog, QApplication, QFormLayout, QSpinBox, QToolBar,
                            QMenu, QSizePolicy)
from PyQt6.QtGui import QFont, QIcon, QAction  # 从QtGui导入QAction
# 导入样式
from gui.styles import GLOBAL_STYLE, StyleHelper, COLORS
from PyQt6.QtCore import Qt, QDir, QSize, QFileInfo, QTimer
from PyQt6.QtGui import QFont, QIcon

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from core.data_processor import FileDataProcessor
from core.data_visualizer import DataVisualizer
from utils.notes_manager import NotesManager
from gui.tabs import FileDetailsTab, NotesTab, VisualizationControlsTab, ProcessingTab
from gui.processed_files_widget import ProcessedFilesWidget
from gui.components.psd_analyzer import PSDAnalyzerDialog
from utils.config_manager import ConfigManager  # 添加ConfigManager导入

from gui.components.fitter_dialog import SimpleFitterDialog
from gui.components.histogram import HistogramDialog

import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')




class FileExplorerApp(QMainWindow):
    """主应用窗口"""
    def closeEvent(self, event):
        """Window closing event - save configuration and clean up threads"""
        # Save window size
        self.config_manager.update_config('window_size', [self.width(), self.height()])
        
        # Save splitter sizes
        self.config_manager.update_config('splitter_sizes', self.splitter.sizes())
        
        # Save sampling rate
        self.config_manager.update_config('sampling_rate', self.viz_controls_tab.sampling_rate_input.value())
        
        # Save visible channels
        if hasattr(self.visualizer, 'visible_channels'):
            self.config_manager.update_config('visible_channels', self.visualizer.visible_channels)
        
        # Force release any resources that might be used by pandas or other libraries
        try:
            import gc
            gc.collect()  # 强制进行垃圾回收
            
            # 清理资源
            if hasattr(self, 'data_processor'):
                self.data_processor.current_data = None
            
            if hasattr(self, 'visualizer'):
                self.visualizer.current_data = None
                self.visualizer.data = None
                self.visualizer.original_data = None
            
            # 检查是否有活动的线程
            import threading
            import time
            
            # 等待其他线程结束，但最多只等待短时间
            threads = [t for t in threading.enumerate() if t != threading.current_thread() and not t.daemon]
            for t in threads:
                try:
                    if t.is_alive():
                        t.join(0.1)  # 等待最多100毫秒
                except:
                    pass
        except Exception as e:
            import traceback
            print(f"Error during cleanup: {str(e)}")
            traceback.print_exc()
        
        event.accept()
        
    def __init__(self):
        super(FileExplorerApp, self).__init__()
        
        # 创建配置管理器
        self.config_manager = ConfigManager()
        
        # 设置应用图标
        self.setWindowIcon(QIcon.fromTheme("accessories-text-editor", QIcon.fromTheme("text-x-generic")))
        
        # 设置窗口标题和大小
        self.setWindowTitle("NP_Analyzer")
        self.resize(1200, 800)  # 减小初始窗口大小以适应小屏幕
        
        # 应用全局样式
        self.setStyleSheet(GLOBAL_STYLE)
        
        # 添加一个标题栏
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setMinimumHeight(50)
        title_bar.setMaximumHeight(50)
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        # 添加图标
        app_icon = QLabel()
        app_icon_pixmap = self.windowIcon().pixmap(24, 24)
        app_icon.setPixmap(app_icon_pixmap)
        
        # 添加标题
        app_title = QLabel("NP_Analyzer")
        app_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        app_title.setStyleSheet("color: white;")
        
        # 添加版本信息
        app_version = QLabel("Version 3.1")
        app_version.setFont(QFont("Arial", 10))
        app_version.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        
        title_layout.addWidget(app_icon)
        title_layout.addWidget(app_title)
        title_layout.addStretch(1)
        title_layout.addWidget(app_version)
        
        # 创建主部件和布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 使用垂直布局包含标题栏和主内容
        central_layout = QVBoxLayout(self.central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)  # 移除外边距
        central_layout.setSpacing(0)  # 移除组件间的空隙
        
        # 将主布局保存为类成员变量，以便在createToolbar中使用
        self.central_layout = central_layout
        
        # 添加标题栏
        central_layout.addWidget(title_bar)
        
        # 创建工具栏并添加到布局中(标题栏下方)
        self.createToolbar()
        
        # 创建内容区域
        content_widget = QWidget()
        content_widget.setContentsMargins(10, 10, 10, 10)  # 内容区域边距
        central_layout.addWidget(content_widget, 1)  # 1表示占用所有剩余空间
        
        # 对内容区域使用水平布局
        self.main_layout = QHBoxLayout(content_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建左中右三个区域的分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        # 启用分割器手柄能够折叠区域
        self.splitter.setChildrenCollapsible(True)
        
        # 左侧文件浏览和信息区域
        self.left_widget = QWidget()
        self.left_widget.setMinimumWidth(200)  # 设置最小宽度
        self.left_widget.setMaximumWidth(350)  # 设置最大宽度，防止过大
        self.left_layout = QVBoxLayout(self.left_widget)
        
        # 添加文件夹选择区域
        self.folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Current Folder:")
        self.folder_path = QLineEdit()
        self.folder_path.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_folder)
        
        self.folder_layout.addWidget(self.folder_label)
        self.folder_layout.addWidget(self.folder_path, 1)  # 1表示拉伸因子
        self.folder_layout.addWidget(self.browse_button)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_selected)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.file_list.setMinimumWidth(180)
        # 启用工具提示以显示完整文件名
        self.file_list.setToolTip("")
        self.file_list.setMouseTracking(True)
        self.file_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        
        # 设置初始文件夹路径
        self.current_folder = self.get_initial_folder()
        self.folder_path.setText(self.current_folder)
        # 加载当前文件夹内容
        self.load_folder_contents(self.current_folder)
        
        # 底部标签页
        self.tabs = QTabWidget()
        
        # 创建笔记管理器
        self.notes_manager = NotesManager()
        
        # 创建文件信息、笔记和处理标签页
        self.details_tab = FileDetailsTab()
        self.notes_tab = NotesTab(self.notes_manager)
        self.processing_tab = ProcessingTab()
        
        # 创建可视化控制标签页
        self.viz_controls_tab = VisualizationControlsTab()
        
        self.tabs.addTab(self.details_tab, QIcon.fromTheme("dialog-information"), "Info")
        self.tabs.addTab(self.processing_tab, QIcon.fromTheme("system-run"), "Proc")
        self.tabs.addTab(self.viz_controls_tab, QIcon.fromTheme("preferences-desktop"), "View")
        self.tabs.addTab(self.notes_tab, QIcon.fromTheme("accessories-text-editor"), "Note")
        
        # 设置选项卡的样式 - 缩小宽度以显示更多tab
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                min-width: 50px;
                max-width: 60px;
                padding: 6px 4px;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
            }
        """)
        
        # 设置tab工具提示以显示完整名称
        self.tabs.setTabToolTip(0, "File Details")
        self.tabs.setTabToolTip(1, "Data Processing")
        self.tabs.setTabToolTip(2, "Visualization Controls")
        self.tabs.setTabToolTip(3, "Notes")
        
        # 左侧布局添加组件，调整文件列表和标签页的比例
        self.left_layout.addLayout(self.folder_layout)
        
        # 创建文件浏览器标题
        file_browser_label = QLabel("  File Browser")
        file_browser_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        file_browser_label.setStyleSheet("color: #0078d7; margin: 8px 0; background-color: #f0f0f0; border-radius: 4px; padding: 4px;")
        file_browser_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 在标签旁边添加图标
        file_browser_icon = QLabel()
        icon_pixmap = QIcon.fromTheme("system-file-manager").pixmap(24, 24)
        file_browser_icon.setPixmap(icon_pixmap)
        
        # 创建水平布局来放置图标和标签
        header_layout = QHBoxLayout()
        header_layout.addWidget(file_browser_icon)
        header_layout.addWidget(file_browser_label, 1)  # 1表示拉伸因子
        
        self.left_layout.addLayout(header_layout)
        self.left_layout.addWidget(self.file_list, 1)  # 减小文件列表的拉伸因子
        self.left_layout.addWidget(self.tabs, 2)  # 增加标签页的拉伸因子
        
        # 中间数据可视化区域
        self.center_widget = QWidget()
        self.center_layout = QVBoxLayout(self.center_widget)
        
        # 创建数据可视化组件
        self.visualizer = DataVisualizer(self.center_widget)
        
        # 创建导航工具栏
        self.toolbar = NavigationToolbar(self.visualizer, self.center_widget)
        
        # 扩大可视化区域
        self.visualizer.setMinimumSize(800, 600)  # 设置最小尺寸
        
        # 添加标题标签
        self.visualization_title = QLabel("Data Visualization")
        self.visualization_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.visualization_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.visualization_title.setStyleSheet("color: #0078d7; margin: 10px 0;")
        
        # 调整布局以使图表占据全部空间
        self.center_layout.addWidget(self.visualization_title)
        self.center_layout.addWidget(self.toolbar)
        self.center_layout.addWidget(self.visualizer, 1)  # 添加拉伸因子，使可视化区域占据全部空间
        
        # 右侧处理后文件区域
        self.processed_files_widget = ProcessedFilesWidget()
        self.processed_files_widget.setMinimumWidth(200)  # 设置最小宽度
        self.processed_files_widget.setMaximumWidth(350)  # 设置最大宽度，防止过大
        
        # 添加三个区域到分割器，调整初始大小比例
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.center_widget)
        self.splitter.addWidget(self.processed_files_widget)
        
        # 设置分割器的初始大小，给中间区域更多空间
        self.splitter.setSizes([220, 900, 220])  # 调整分割器初始大小比例
        
        # 设置分割器样式
        self.splitter.setHandleWidth(1)
        
        # 添加侧边栏折叠按钮
        self.add_sidebar_toggle_buttons()
        
        # 将分割器添加到主布局
        self.main_layout.addWidget(self.splitter)
        
        # 创建数据处理器
        self.data_processor = FileDataProcessor()
        
        # 扫描处理文件夹
        self.scan_processed_files()
        
        # 连接事件处理函数
        self.connect_signals()
        
        # 创建状态栏
        self.statusBar = self.statusBar()
        
        # 添加状态栏右侧固定的版权信息
        copyright_label = QLabel("© 2025 NPA Visualizer")
        self.statusBar.addPermanentWidget(copyright_label)
        
        self.statusBar.showMessage("Ready")
        
        # 当前选中的文件路径
        self.current_file_path = None
        self.processed_data = None
    

    
    def add_sidebar_toggle_buttons(self):
        """添加侧边栏折叠按钮"""
        # 在分割器上方添加左右折叠按钮
        left_toggle_layout = QVBoxLayout()
        left_toggle_layout.setContentsMargins(0, 0, 0, 0)
        left_toggle_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.left_toggle_btn = QPushButton("◀")
        self.left_toggle_btn.setToolTip("Toggle left sidebar")
        self.left_toggle_btn.setMaximumWidth(20)
        self.left_toggle_btn.setMaximumHeight(60)
        self.left_toggle_btn.clicked.connect(self.toggle_left_sidebar)
        left_toggle_layout.addWidget(self.left_toggle_btn)
        
        right_toggle_layout = QVBoxLayout()
        right_toggle_layout.setContentsMargins(0, 0, 0, 0)
        right_toggle_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.right_toggle_btn = QPushButton("▶")
        self.right_toggle_btn.setToolTip("Toggle right sidebar")
        self.right_toggle_btn.setMaximumWidth(20)
        self.right_toggle_btn.setMaximumHeight(60)
        self.right_toggle_btn.clicked.connect(self.toggle_right_sidebar)
        right_toggle_layout.addWidget(self.right_toggle_btn)
        
        # 将按钮添加到中间区域的左右两侧
        sidebar_container = QWidget()
        sidebar_layout = QHBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addLayout(left_toggle_layout)
        sidebar_layout.addStretch(1)
        sidebar_layout.addLayout(right_toggle_layout)
        
        # 将折叠按钮添加到可视化区域的顶部
        self.center_layout.insertWidget(0, sidebar_container)  # 插入到最上面
    
    def toggle_left_sidebar(self):
        """切换左侧边栏显示/隐藏"""
        sizes = self.splitter.sizes()
        if sizes[0] > 0:  # 如果左侧边栏当前可见
            # 保存当前宽度并隐藏
            self._left_sidebar_width = sizes[0]
            sizes[1] += sizes[0]  # 将左侧边栏的宽度添加到中间区域
            sizes[0] = 0
            self.left_toggle_btn.setText("▶")  # 更改为右箭头形状
        else:  # 如果左侧边栏当前隐藏
            # 恢复到之前的宽度并显示
            width = getattr(self, "_left_sidebar_width", 220)  # 默认宽度如果没有保存
            sizes[1] -= width  # 从中间区域减去左侧边栏的宽度
            sizes[0] = width
            self.left_toggle_btn.setText("◀")  # 更改为左箭头形状
        
        self.splitter.setSizes(sizes)
        self.statusBar.showMessage("Left sidebar toggled", 2000)
    
    def toggle_right_sidebar(self):
        """切换右侧边栏显示/隐藏"""
        sizes = self.splitter.sizes()
        if sizes[2] > 0:  # 如果右侧边栏当前可见
            # 保存当前宽度并隐藏
            self._right_sidebar_width = sizes[2]
            sizes[1] += sizes[2]  # 将右侧边栏的宽度添加到中间区域
            sizes[2] = 0
            self.right_toggle_btn.setText("◀")  # 更改为左箭头形状
        else:  # 如果右侧边栏当前隐藏
            # 恢复到之前的宽度并显示
            width = getattr(self, "_right_sidebar_width", 220)  # 默认宽度如果没有保存
            sizes[1] -= width  # 从中间区域减去右侧边栏的宽度
            sizes[2] = width
            self.right_toggle_btn.setText("▶")  # 更改为右箭头形状
        
        self.splitter.setSizes(sizes)
        self.statusBar.showMessage("Right sidebar toggled", 2000)
    
    def createToolbar(self):
        """创建应用工具栏"""
        # 创建一个工具栏
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)  # 减少边距使其更紧凑
        toolbar_layout.setSpacing(5)
        
        # 添加工具栏按钮
        # 打开文件夹按钮
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setIcon(QIcon.fromTheme("folder-open"))
        open_folder_btn.clicked.connect(self.browse_folder)
        toolbar_layout.addWidget(open_folder_btn)
        
        # 数据处理按钮
        process_data_btn = QPushButton("Process Data")
        process_data_btn.setIcon(QIcon.fromTheme("system-run"))
        process_data_btn.clicked.connect(self.process_data)
        toolbar_layout.addWidget(process_data_btn)
        
        # 保存按钮
        save_btn = QPushButton("Save Results")
        save_btn.setIcon(QIcon.fromTheme("document-save"))
        save_btn.clicked.connect(self.save_processed_data)
        toolbar_layout.addWidget(save_btn)
        
        # X轴同步切换按钮
        # 删除了Sync X-Axis按钮
        
        # 添加PSD分析器按钮
        psd_analyzer_btn = QPushButton("PSD Analyzer")
        psd_analyzer_btn.setIcon(QIcon.fromTheme("utilities-system-monitor", QIcon.fromTheme("applications-science")))
        psd_analyzer_btn.clicked.connect(self.open_psd_analyzer)
        toolbar_layout.addWidget(psd_analyzer_btn)
        
        # 添加拟合工具按钮
        fit_btn = QPushButton("Curve Fit")
        fit_btn.setIcon(QIcon.fromTheme("accessories-calculator"))
        fit_btn.clicked.connect(self.open_curve_fitter)
        toolbar_layout.addWidget(fit_btn)
        
        # 添加Spikes Detector按钮
        spikes_detector_btn = QPushButton("Spikes Detector")
        spikes_detector_btn.setIcon(QIcon.fromTheme("utilities-system-monitor", QIcon.fromTheme("applications-utilities")))
        spikes_detector_btn.clicked.connect(self.open_spikes_detector)
        toolbar_layout.addWidget(spikes_detector_btn)
        
        # 添加Histogram按钮
        histogram_btn = QPushButton("Histogram")
        histogram_btn.setIcon(QIcon.fromTheme("view-statistics", QIcon.fromTheme("office-chart-bar")))
        histogram_btn.clicked.connect(self.open_histogram)
        toolbar_layout.addWidget(histogram_btn)
        
        # 添加弹簧使帮助按钮靠右
        toolbar_layout.addStretch(1)
        
        # 设置默认路径按钮
        set_default_path_btn = QPushButton("Set Default Path")
        set_default_path_btn.setIcon(QIcon.fromTheme("preferences-system"))
        set_default_path_btn.clicked.connect(self.set_default_path)
        toolbar_layout.addWidget(set_default_path_btn)
        
        # 帮助按钮
        help_btn = QPushButton("Help")
        help_btn.setIcon(QIcon.fromTheme("help-contents"))
        help_btn.clicked.connect(self.show_help)
        toolbar_layout.addWidget(help_btn)
        
        # 将工具栏添加到主布局
        self.central_layout.addWidget(toolbar_widget)
    
    def load_folder_contents(self, folder_path):
        """加载文件夹内容到列表小部件"""
        self.file_list.clear()
        
        # 添加返回上级目录的选项
        if os.path.dirname(folder_path) != folder_path:  # 不是根目录
            parent_item = QListWidgetItem("📁..")
            parent_item.setData(Qt.ItemDataRole.UserRole, os.path.dirname(folder_path))
            self.file_list.addItem(parent_item)
        
        # 获取目录内容
        try:
            dirs = []
            files = []
            
            # 获取所有文件和目录
            for item in os.listdir(folder_path):
                full_path = os.path.join(folder_path, item)
                
                if os.path.isdir(full_path):
                    dirs.append((item, full_path))
                elif os.path.isfile(full_path):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.tdms', '.h5', '.abf', '.csv']:  # 修改这里添加CSV支持
                        files.append((item, full_path))
            
            # 先添加目录（按名称排序）
            for dir_name, dir_path in sorted(dirs, key=lambda x: x[0].lower()):
                list_item = QListWidgetItem(f"📁 {dir_name}")
                list_item.setData(Qt.ItemDataRole.UserRole, dir_path)
                list_item.setToolTip(dir_path)  # 设置完整路径为工具提示
                self.file_list.addItem(list_item)
            
            # 再添加文件（按名称排序）
            for file_name, file_path in sorted(files, key=lambda x: x[0].lower()):
                list_item = QListWidgetItem(f"📄 {file_name}")
                list_item.setData(Qt.ItemDataRole.UserRole, file_path)
                list_item.setToolTip(file_path)  # 设置完整路径为工具提示
                self.file_list.addItem(list_item)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load folder contents: {str(e)}")
    
    def get_initial_folder(self):
        """获取初始文件夹路径"""
        # 从配置中获取默认路径
        default_path = self.config_manager.config.get('default_path')
        
        if default_path and os.path.exists(default_path):
            return default_path
        
        # 如果默认路径不存在，使用代码所在目录
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.exists(script_dir):
            return script_dir
            
        # 最后的选择：当前工作目录
        return QDir.currentPath()
    
    def set_default_path(self):
        """设置默认路径"""
        current_default = self.config_manager.config.get('default_path', self.current_folder)
        
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Set Default Folder", 
            current_default
        )
        
        if folder:
            # 保存到配置
            self.config_manager.update_config('default_path', folder)
            
            # 显示成功消息
            QMessageBox.information(
                self, 
                "Success", 
                f"Default path has been set to:\n{folder}\n\nThis will be used as the starting folder next time you open the application."
            )
            
            # 更新状态栏
            self.statusBar.showMessage(f"Default path set to: {folder}", 3000)
    
    def browse_folder(self):
        """浏览并选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.current_folder)
        
        if folder:  # 如果用户没有取消对话框
            self.current_folder = folder
            self.folder_path.setText(folder)
            
            # 加载新文件夹内容
            self.load_folder_contents(folder)
            
            # 扫描新文件夹中的处理后文件
            self.scan_processed_files()
            
            # 更新状态栏
            self.statusBar.showMessage(f"Browsing folder: {folder}")
    
    def connect_signals(self):
        """连接信号和槽"""
        # 处理按钮点击
        self.processing_tab.process_button.clicked.connect(self.process_data)
        self.processing_tab.save_button.clicked.connect(self.save_processed_data)
        
        # 处理后文件单击和双击打开
        self.processed_files_widget.files_list.itemClicked.connect(self.on_processed_file_selected)
        self.processed_files_widget.files_list.itemDoubleClicked.connect(self.on_processed_file_selected)
        
        # 可视化控制面板连接
        self.viz_controls_tab.sampling_rate_input.valueChanged.connect(self.on_sampling_rate_changed)
        self.viz_controls_tab.subplot_button.clicked.connect(self.configure_subplot_heights)
        self.viz_controls_tab.sync_check.stateChanged.connect(self.toggle_sync_mode)
        self.viz_controls_tab.apply_channel_button.clicked.connect(self.apply_channel_selection)
        
        # 连接可视化器的通道更新信号到控制面板
        self.visualizer.channels_updated.connect(self.viz_controls_tab.update_available_channels)
    
    def on_sampling_rate_changed(self, value):
        """处理采样率变更"""
        if hasattr(self, 'visualizer'):
            self.visualizer.set_sampling_rate(value)
    
    def on_file_selected(self, item):
        """文件选中处理"""
        item_path = item.data(Qt.ItemDataRole.UserRole)
        
        if os.path.isdir(item_path):
            # 如果选中的是目录，则进入该目录
            self.current_folder = item_path
            self.folder_path.setText(item_path)
            self.load_folder_contents(item_path)
            self.scan_processed_files()
        elif os.path.isfile(item_path):
            # 如果选中的是文件，则加载文件数据
            file_path = item_path
            # 文件扩展名
            ext = os.path.splitext(file_path)[1].lower()
            
            # 检查是否是支持的文件类型
            if ext in ['.tdms', '.h5', '.abf', '.csv']:  # 修改这里添加CSV支持
                self.current_file_path = file_path
                
                # 加载文件数据
                success, data, info = self.data_processor.load_file(file_path)
                
                if success:
                    # 更新文件信息
                    self.details_tab.update_info(info)
                    
                    # 提取采样率信息（如果有）
                    sampling_rate = None
                    for key, value in info.items():
                        if "Sampling Rate" in key:
                            try:
                                # 尝试提取数值部分
                                if isinstance(value, str):
                                    rate_str = value.split()[0]  # 例如 "1000 Hz" 取 "1000"
                                    sampling_rate = float(rate_str)
                                elif isinstance(value, (int, float)):
                                    sampling_rate = float(value)
                                
                                print(f"Found sampling rate: {sampling_rate} Hz")
                                
                                # 更新采样率输入小部件
                                self.viz_controls_tab.sampling_rate_input.setValue(sampling_rate)
                                break
                            except Exception as e:
                                print(f"Error extracting sampling rate: {str(e)}")
                                pass
                    
                    # 可视化数据
                    self.visualizer.plot_data(
                        data, 
                        title=os.path.basename(file_path),
                        sampling_rate=sampling_rate or self.viz_controls_tab.sampling_rate_input.value()
                    )
                    
                    # 更新处理标签页的通道选择器
                    self.update_channel_selector(data)
                    
                    # 在第一次加载文件后显示提示，告知用户可以选择特定通道进行处理
                    QTimer.singleShot(1000, lambda: self.statusBar.showMessage(
                        "Tip: You can select a specific channel for processing in the Data Processing tab", 5000))
                    
                    # 加载笔记
                    self.notes_tab.load_file_note(file_path)
                    
                    # 更新状态栏
                    self.statusBar.showMessage(f"Loaded file: {os.path.basename(file_path)}")
                else:
                    QMessageBox.warning(self, "Error", f"Cannot load file: {info.get('Error', 'Unknown error')}")
    
    def configure_subplot_heights(self):
        """配置子图高度"""
        if not hasattr(self, 'visualizer') or not self.visualizer.data:
            QMessageBox.information(self, "Information", "Please load data first")
            return
        
        # Get current heights
        current_heights = self.visualizer.get_subplot_heights()
        
        # Get channel names
        channels = []
        if isinstance(self.visualizer.data, dict):
            channels = list(self.visualizer.data.keys())
        elif isinstance(self.visualizer.data, np.ndarray) and self.visualizer.data.ndim == 2:
            channels = [f"Channel {i+1}" for i in range(self.visualizer.data.shape[1])]
        
        if not channels:
            QMessageBox.information(self, "Information", "No channels to configure")
            return
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Subplot Heights")
        dialog.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(dialog)
        
        # Create form layout for height inputs
        form_layout = QFormLayout()
        form_layout.setContentsMargins(20, 20, 20, 20)  # 添加边距
        form_layout.setSpacing(12)  # 增加间距
        height_widgets = {}
        
        for channel in channels:
            spin = QSpinBox()
            spin.setRange(1, 10)
            spin.setValue(current_heights.get(channel, 1))
            form_layout.addRow(channel + ":", spin)
            height_widgets[channel] = spin
        
        layout.addLayout(form_layout)
        
        # Add buttons
        button_box = QHBoxLayout()
        button_box.setContentsMargins(20, 20, 20, 20)  # 添加边距
        apply_button = QPushButton("Apply")
        apply_button.setIcon(QIcon.fromTheme("dialog-ok"))
        apply_button.setMinimumWidth(120)
        cancel_button = QPushButton("Cancel")
        cancel_button.setIcon(QIcon.fromTheme("dialog-cancel"))
        cancel_button.setMinimumWidth(120)
        
        apply_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_box.addWidget(apply_button)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)
        
        # Show dialog
        if dialog.exec():
            # Apply new heights
            for channel, widget in height_widgets.items():
                self.visualizer.set_subplot_height(channel, widget.value())
            
            # Redraw with new heights
            self.visualizer.plot_data(
                self.visualizer.data,
                title=self.visualizer.fig._suptitle.get_text() if hasattr(self.visualizer.fig, "_suptitle") and self.visualizer.fig._suptitle else "Data",
                sampling_rate=self.visualizer.sampling_rate
            )
            
            # 更新状态栏
            self.statusBar.showMessage("Subplot heights updated")

        # 调整对话框大小
        dialog.resize(400, 300)  # 增加对话框尺寸，使内容更清晰
    
    def on_processed_file_selected(self, item):
        """处理后文件选中处理"""
        file_path = self.processed_files_widget.get_selected_file()
        if file_path:
            success, data, info = self.data_processor.load_file(file_path)
            
            if success:
                # 更新文件信息
                self.details_tab.update_info(info)
                
                # 可视化数据 - use current sampling rate
                self.visualizer.plot_data(
                    data, 
                    title=os.path.basename(file_path) + " (Processed)",
                    sampling_rate=self.viz_controls_tab.sampling_rate_input.value()
                )
    
    def process_data(self):
        """处理数据"""
        if not self.current_file_path:
            QMessageBox.warning(self, "Error", "Please select a file first")
            return
        
        operation = self.processing_tab.current_operation
        if not operation:
            QMessageBox.warning(self, "Error", "Please select a processing operation")
            return
        
        params = self.processing_tab.get_parameters()
        
        # Add current sampling rate to params
        params["sampling_rate"] = self.viz_controls_tab.sampling_rate_input.value()
        
        success, processed_data, message = self.data_processor.process_data(operation, params)
        
        if success:
            self.processed_data = processed_data
            
            # Get operation display name (English)
            operation_display = operation
            for eng, ch in self.processing_tab.operation_mappings.items():
                if ch == operation:
                    operation_display = eng
                    break
            
            # 可视化处理后数据 - use current sampling rate
            self.visualizer.plot_data(
                processed_data, 
                title=f"{os.path.basename(self.current_file_path)} (After {operation_display})",
                sampling_rate=self.viz_controls_tab.sampling_rate_input.value()
            )
            
            # 更新通道选择器，以适应处理后的数据结构
            self.update_channel_selector(processed_data)
            
            QMessageBox.information(self, "Success", message if message == "处理成功" else "Processing successful")
            
            # 更新状态栏
            operation_display = operation
            for eng, ch in self.processing_tab.operation_mappings.items():
                if ch == operation:
                    operation_display = eng
                    break
            self.statusBar.showMessage(f"Processing complete: {operation_display}")
        else:
            QMessageBox.warning(self, "Error", message)
    
    def save_processed_data(self):
        """保存处理后数据"""
        if self.processed_data is None:
            QMessageBox.warning(self, "Error", "No processed data to save")
            return
        
        # 默认保存路径
        default_dir = self.current_folder
        
        # 生成默认文件名
        file_count = len([f for f in os.listdir(default_dir) 
                         if f.startswith("proc_") and f.endswith(".h5")])
        default_name = f"proc_{file_count:04d}.h5"
        
        # 获取保存路径
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Processed Data", 
            os.path.join(default_dir, default_name),
            "HDF5 Files (*.h5)"
        )
        
        if save_path:
            # Update processor sampling rate with current UI value
            self.data_processor.sampling_rate = self.viz_controls_tab.sampling_rate_input.value()
            
            success, message = self.data_processor.save_processed_data(
                self.processed_data, save_path)
            
            if success:
                QMessageBox.information(self, "Success", "Data saved successfully")
                
                # 添加到处理后文件列表
                self.processed_files_widget.add_file(save_path)
                
                # 更新状态栏
                self.statusBar.showMessage(f"File saved: {os.path.basename(save_path)}")
            else:
                QMessageBox.warning(self, "Error", message)
    
    def scan_processed_files(self):
        """扫描处理后文件夹"""
        # 清空当前列表
        self.processed_files_widget.files_list.clear()
        self.processed_files_widget.file_paths = {}
        
        # 扫描当前文件夹中的h5文件
        h5_files = [f for f in os.listdir(self.current_folder) if f.endswith(".h5")]
        
        for file_name in h5_files:
            file_path = os.path.join(self.current_folder, file_name)
            self.processed_files_widget.add_file(file_path)
            
    def open_psd_analyzer(self):
        """打开PSD分析器"""
        # 创建对话框
        dialog = None
        
        # 检查是否有当前可视化数据
        current_data = None
        sampling_rate = None
        data_title = None
        
        # 获取当前控制面板中的采样率
        if hasattr(self, 'viz_controls_tab') and hasattr(self.viz_controls_tab, 'sampling_rate_input'):
            sampling_rate = self.viz_controls_tab.sampling_rate_input.value()
        
        # 检查可视化器中的数据
        if hasattr(self, 'visualizer') and hasattr(self.visualizer, 'data') and self.visualizer.data is not None:
            current_data = self.visualizer.data
            
            # 尝试获取数据标题
            if hasattr(self.visualizer, 'fig') and hasattr(self.visualizer.fig, '_suptitle') and self.visualizer.fig._suptitle:
                data_title = self.visualizer.fig._suptitle.get_text()
            else:
                # 使用当前文件名
                if self.current_file_path:
                    data_title = os.path.basename(self.current_file_path)
                else:
                    data_title = "Current Data"
            
            dialog = PSDAnalyzerDialog(self, data=current_data, sampling_rate=sampling_rate, title=f"PSD Analyzer - {data_title}")
            
            # 执行直接数据初始化
            if dialog.initialize_with_direct_data():
                # 显示对话框
                dialog.exec()
                return
        
        # 如果无法初始化直接数据，则回滨到标准模式
        if dialog is None:
            dialog = PSDAnalyzerDialog(self)
            dialog.setWindowTitle("PSD Analyzer")
        
        # 如果当前有打开的H5文件，尝试加载
        if self.current_file_path and self.current_file_path.lower().endswith((".h5", ".hdf5")):
            dialog.load_file(self.current_file_path)
        else:
            # 如果没有H5文件但有当前数据，显示提示
            if current_data is not None:
                QMessageBox.information(self, "Information", 
                                      "Failed to initialize with current data. Please load an H5 file.")
        
        # 显示对话框
        dialog.exec()

    def toggle_sync_mode(self, state):
        """切换同步/手动模式"""
        if hasattr(self, 'visualizer'):
            # Qt.CheckState.Checked 对应值为 2
            is_sync = (state == 2)
            self.visualizer.set_sync_mode(is_sync)
            
            # 如果有数据，刷新显示
            if hasattr(self.visualizer, 'original_data') and self.visualizer.original_data is not None:
                # 获取当前标题
                current_title = self.visualizer.fig._suptitle.get_text() \
                    if hasattr(self.visualizer.fig, "_suptitle") and self.visualizer.fig._suptitle else "Data"
                
                # 重绘图表保持当前标题并应用当前通道选择
                self.visualizer.plot_data(
                    self.visualizer.original_data,
                    title=current_title,
                    sampling_rate=self.visualizer.sampling_rate,
                    channels_to_plot=self.visualizer.visible_channels
                )
    
    def update_channel_selector(self, data):
        """更新处理标签页的通道选择器"""
        # 清空当前选项
        self.processing_tab.channel_combo.clear()
        
        # 始终添加"All Channels"选项
        self.processing_tab.channel_combo.addItem("All Channels")
        
        channels = []
        
        # 获取通道名称
        if isinstance(data, dict):
            # 如果数据是字典，则直接使用键作为通道名
            channels = list(data.keys())
        elif isinstance(data, np.ndarray) and data.ndim == 2:
            # 如果数据是二维数组，使用"Channel N"形式
            channels = [f"Channel {i+1}" for i in range(data.shape[1])]
        
        # 添加所有通道到下拉菜单
        for channel in channels:
            self.processing_tab.channel_combo.addItem(channel)
            
    def apply_channel_selection(self):
        """应用通道选择更改"""
        if hasattr(self, 'visualizer'):
            selected_channels = self.viz_controls_tab.selected_channels
            self.visualizer.set_visible_channels(selected_channels)
            
            # 更新状态栏
            if selected_channels:
                channel_str = ", ".join(selected_channels) if len(selected_channels) <= 3 else \
                              f"{len(selected_channels)} channels"
                self.statusBar.showMessage(f"Displaying channels: {channel_str}", 3000)

    def open_curve_fitter(self):
        """打开曲线拟合工具"""
        # 检查是否有加载的数据
        if not hasattr(self.visualizer, 'data') or self.visualizer.data is None:
            QMessageBox.warning(self, "Error", "Please load data first")
            return
            
        # 创建拟合对话框
        dialog = SimpleFitterDialog(self)
        
        # 设置数据
        dialog.set_data(self.visualizer.data)
        
        # 显示对话框
        dialog.exec()
        
    def open_spikes_detector(self):
        """打开峰值检测器"""
        # 检查是否有加载的数据
        if not hasattr(self.visualizer, 'data') or self.visualizer.data is None:
            QMessageBox.warning(self, "Error", "Please load data first")
            return
            
        # 导入峰值检测器组件
        from gui.components.spikes_detector import SpikesDetectorDialog
        
        # 创建峰值检测器对话框
        dialog = SpikesDetectorDialog(self)
        
        # 设置数据和采样率
        dialog.set_data(self.visualizer.data, self.visualizer.sampling_rate)
        
        # 显示对话框
        dialog.exec()
    
    def open_histogram(self):
        """打开直方图分析工具"""
        # 检查是否有加载的数据
        if not hasattr(self.visualizer, 'data') or self.visualizer.data is None:
            QMessageBox.warning(self, "Error", "Please load data first")
            return
            
        # 创建直方图对话框
        dialog = HistogramDialog(self)
        
        # 设置数据和采样率
        dialog.set_data(self.visualizer.data, self.visualizer.sampling_rate)
        
        # 显示对话框
        dialog.exec()
    
    def show_help(self):
        """显示帮助对话框"""
        help_text = """
        <h2>NP_Analyzer Help</h2>
        <p>This application helps you analyze and visualize neural data files.</p>
        
        <h3>Basic Operations:</h3>
        <ul>
            <li><b>Browse Folder</b>: Select a folder containing data files</li>
            <li><b>Set Default Path</b>: Set a default starting folder for the application</li>
            <li><b>Select File</b>: Click on a file in the file browser to load it</li>
            <li><b>Process Data</b>: Select processing operations in the Processing tab</li>
            <li><b>Save Results</b>: Save processed data to a new file</li>
            <li><b>Visualize</b>: View data in the central visualization panel</li>
            <li><b>Curve Fit</b>: Perform curve fitting on your data</li>
            <li><b>Spikes Detector</b>: Detect and analyze spikes in time-series data</li>
        </ul>
        
        <h3>Supported File Types:</h3>
        <ul>
            <li>.tdms - National Instruments TDMS files</li>
            <li>.h5 - HDF5 files</li>
            <li>.abf - Axon Binary Format files</li>
            <li>.csv - Comma Separated Value files</li>
        </ul>
        
        <p>For more information, please refer to the documentation.</p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("NP_Analyzer Help")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(help_text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()