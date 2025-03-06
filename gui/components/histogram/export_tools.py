#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Tools - 导出工具
提供直方图数据导出和拟合信息复制功能
"""

import os
import numpy as np
import csv
import json
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QLabel, QGroupBox, QMessageBox, 
                            QApplication, QToolBar, QStatusBar)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon


class ExportToolsPanel(QGroupBox):
    """导出和复制工具面板"""
    
    # 定义信号
    export_histogram_requested = pyqtSignal()  # 导出直方图数据信号
    copy_fit_info_requested = pyqtSignal()     # 复制拟合信息信号
    
    def __init__(self, parent=None):
        super(ExportToolsPanel, self).__init__("Export Tools", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 5)
        
        # 导出直方图数据按钮
        self.export_hist_btn = QPushButton("Export Histogram Data")
        self.export_hist_btn.setToolTip("Export current histogram data to CSV file")
        self.export_hist_btn.clicked.connect(self.export_histogram_requested.emit)
        
        # 复制拟合信息按钮
        self.copy_fit_btn = QPushButton("Copy Fit Info")
        self.copy_fit_btn.setToolTip("Copy current fitting results to clipboard")
        self.copy_fit_btn.clicked.connect(self.copy_fit_info_requested.emit)
        
        # 添加到布局
        layout.addWidget(self.export_hist_btn)
        layout.addWidget(self.copy_fit_btn)


class HistogramExporter:
    """直方图数据导出器"""
    
    def __init__(self, parent=None):
        self.parent = parent
        
    def export_histogram_data(self, data, bins, hist_counts, bin_edges, file_name="histogram_data"):
        """导出直方图数据到CSV文件"""
        try:
            # 创建默认文件名
            if not file_name or file_name == "":
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_filename = f"histogram_data_{current_time}.csv"
            else:
                default_filename = f"{os.path.splitext(file_name)[0]}_histogram.csv"
            
            # 显示文件保存对话框
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(
                self.parent,
                "保存直方图数据",
                default_filename,
                "CSV文件 (*.csv);;所有文件 (*)",
                options=options
            )
            
            if not file_path:
                return False, "用户取消导出"
                
            # 准备直方图数据
            hist_data = []
            for i in range(len(hist_counts)):
                bin_min = bin_edges[i]
                bin_max = bin_edges[i+1]
                bin_center = (bin_min + bin_max) / 2
                hist_data.append({
                    "bin_min": bin_min,
                    "bin_max": bin_max,
                    "bin_center": bin_center,
                    "count": hist_counts[i]
                })
            
            # 计算相关统计信息
            stats_data = {
                "total_points": len(data),
                "min": float(np.min(data)),
                "max": float(np.max(data)),
                "mean": float(np.mean(data)),
                "median": float(np.median(data)),
                "std_dev": float(np.std(data)),
                "bins_count": bins
            }
            
            # 写入CSV文件
            with open(file_path, 'w', newline='') as csvfile:
                # 写入统计信息
                csvfile.write("# 直方图统计信息\n")
                for key, value in stats_data.items():
                    csvfile.write(f"# {key}: {value}\n")
                csvfile.write("#\n")
                
                # 写入直方图数据
                csvfile.write("# 直方图数据\n")
                writer = csv.writer(csvfile)
                writer.writerow(["bin_min", "bin_max", "bin_center", "count"])
                for data_row in hist_data:
                    writer.writerow([
                        data_row["bin_min"],
                        data_row["bin_max"],
                        data_row["bin_center"],
                        data_row["count"]
                    ])
                
                # 写入原始数据点
                csvfile.write("#\n# 原始数据点\n")
                writer.writerow(["data_point"])
                for point in data:
                    writer.writerow([point])
                    
            return True, file_path
            
        except Exception as e:
            return False, str(e)
    
    def copy_fit_info_to_clipboard(self, fit_info_str):
        """复制拟合信息到剪贴板"""
        try:
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(fit_info_str)
            return True, "拟合信息已复制到剪贴板"
        except Exception as e:
            return False, str(e)
