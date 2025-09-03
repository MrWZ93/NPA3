#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Tools - 导出工具
提供直方图数据导出和图像复制功能
"""

import os
import io
import numpy as np
import csv
import json
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QLabel, QGroupBox, QMessageBox, 
                            QApplication, QProgressDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QImage
from PIL import Image

from .settings_manager import SettingsManager


class ExportToolsPanel(QGroupBox):
    """导出和复制工具面板"""
    
    # 定义信号
    export_comprehensive_requested = pyqtSignal()  # 综合导出信号
    copy_image_requested = pyqtSignal()           # 复制图像信号
    
    def __init__(self, parent=None):
        super(ExportToolsPanel, self).__init__("Export Tools", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 5)
        
        # 综合导出按钮
        self.export_comprehensive_btn = QPushButton("Export Histogram Data")
        self.export_comprehensive_btn.setToolTip("Export histogram stats, fit data, raw data, and images")
        self.export_comprehensive_btn.clicked.connect(self.export_comprehensive_requested.emit)
        
        # 复制图像按钮
        self.copy_image_btn = QPushButton("Copy Image")
        self.copy_image_btn.setToolTip("Copy main view and histogram images to clipboard")
        self.copy_image_btn.clicked.connect(self.copy_image_requested.emit)
        
        # 添加到布局
        layout.addWidget(self.export_comprehensive_btn)
        layout.addWidget(self.copy_image_btn)


class IntegratedDataExporter:
    """综合数据导出器"""
    
    def __init__(self, dialog_instance):
        self.dialog = dialog_instance
        self.settings_manager = SettingsManager()
        
    def export_comprehensive_data(self):
        """综合导出所有数据 - 改进版，创建文件夹并包含原文件路径"""
        try:
            # 获取上次保存的路径
            settings = self.settings_manager.load_settings("histogram_export")
            last_export_dir = settings.get("last_export_directory", "")
            
            # 如果没有保存的路径，使用原文件所在路径
            if not last_export_dir or not os.path.exists(last_export_dir):
                if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                    last_export_dir = os.path.dirname(self.dialog.data_manager.file_path)
                else:
                    last_export_dir = os.getcwd()
            
            # 获取基础文件名
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                base_name = os.path.splitext(os.path.basename(self.dialog.data_manager.file_path))[0]
                default_foldername = f"{base_name}_export_{current_time}"
            else:
                default_foldername = f"histogram_export_{current_time}"
            
            # 在上次保存的目录中设置默认文件夹名
            default_path = os.path.join(last_export_dir, default_foldername)
            
            # 显示文件保存对话框，让用户选择路径和文件夹名
            folder_path, _ = QFileDialog.getSaveFileName(
                self.dialog,
                "Export Comprehensive Data - Choose folder name and location",
                default_path,
                "Folder (*.folder);;All Files (*)"
            )
            
            if not folder_path:
                return False, "Export cancelled by user"
            
            # 移除可能的扩展名，获取纯文件夹名
            folder_path = os.path.splitext(folder_path)[0]
            
            # 保存新选择的目录
            new_export_dir = os.path.dirname(folder_path)
            settings["last_export_directory"] = new_export_dir
            self.settings_manager.save_settings("histogram_export", settings)
            
            # 创建导出文件夹
            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"Created export folder: {folder_path}")
            except Exception as e:
                return False, f"Failed to create export folder: {str(e)}"
            
            # 获取文件夹名作为基础名称
            folder_name = os.path.basename(folder_path)
            
            # 显示进度对话框
            progress = QProgressDialog("Exporting data...", "Cancel", 0, 6, self.dialog)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            exported_files = []
            
            # 0. 导出文件信息和元数据
            progress.setLabelText("Creating metadata...")
            progress.setValue(0)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            metadata_file = os.path.join(folder_path, f"{folder_name}_metadata.txt")
            success = self._export_metadata(metadata_file)
            if success:
                exported_files.append(os.path.basename(metadata_file))
            
            # 1. 导出直方图统计数据
            progress.setLabelText("Collecting histogram statistics...")
            progress.setValue(1)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            hist_stats_file = os.path.join(folder_path, f"{folder_name}_histogram_stats.csv")
            success = self._export_histogram_stats(hist_stats_file)
            if success:
                exported_files.append(os.path.basename(hist_stats_file))
            
            # 2. 导出拟合数据
            progress.setLabelText("Collecting fit data...")
            progress.setValue(2)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            fits_file = os.path.join(folder_path, f"{folder_name}_fits.csv")
            success = self._export_fit_data(fits_file)
            if success:
                exported_files.append(os.path.basename(fits_file))
            
            # 3. 导出原始数据
            progress.setLabelText("Collecting raw data...")
            progress.setValue(3)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            raw_data_file = os.path.join(folder_path, f"{folder_name}_raw_data.csv")
            success = self._export_raw_data(raw_data_file)
            if success:
                exported_files.append(os.path.basename(raw_data_file))
            
            # 4. 导出主视图图像
            progress.setLabelText("Exporting main view image...")
            progress.setValue(4)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            main_image_file = os.path.join(folder_path, f"{folder_name}_main_view.png")
            success = self._export_main_view_image(main_image_file)
            if success:
                exported_files.append(os.path.basename(main_image_file))
            
            # 5. 导出直方图视图图像
            progress.setLabelText("Exporting histogram view image...")
            progress.setValue(5)
            if progress.wasCanceled():
                return False, "Export cancelled"
                
            hist_image_file = os.path.join(folder_path, f"{folder_name}_histogram_view.png")
            success = self._export_histogram_view_image(hist_image_file)
            if success:
                exported_files.append(os.path.basename(hist_image_file))
            
            progress.close()
            
            if exported_files:
                file_list = "\n".join([f"  - {f}" for f in exported_files])
                return True, f"Successfully exported {len(exported_files)} files to folder:\n{folder_path}\n\nFiles:\n{file_list}"
            else:
                return False, "No data was exported"
                
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            return False, f"Export error: {str(e)}"
    
    def _export_metadata(self, file_path):
        """导出文件元数据和原始路径信息"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Histogram Export Metadata\n")
                f.write(f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("#\n")
                
                # 原文件信息
                f.write("# Original File Information:\n")
                if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                    f.write(f"# Source File Path: {self.dialog.data_manager.file_path}\n")
                    f.write(f"# Source File Name: {os.path.basename(self.dialog.data_manager.file_path)}\n")
                    
                    # 检查文件是否存在并获取信息
                    if os.path.exists(self.dialog.data_manager.file_path):
                        stat = os.stat(self.dialog.data_manager.file_path)
                        f.write(f"# File Size: {stat.st_size} bytes\n")
                        f.write(f"# File Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n")
                else:
                    f.write("# Source File Path: Not available\n")
                
                f.write("#\n")
                
                # 分析参数
                f.write("# Analysis Parameters:\n")
                if hasattr(self.dialog.data_manager, 'selected_channel'):
                    f.write(f"# Selected Channel: {self.dialog.data_manager.selected_channel}\n")
                    f.write(f"# Sampling Rate: {self.dialog.data_manager.sampling_rate}\n")
                
                if hasattr(self.dialog.plot_canvas, 'data'):
                    f.write(f"# Highlight Region Start: {self.dialog.plot_canvas.highlight_min}\n")
                    f.write(f"# Highlight Region End: {self.dialog.plot_canvas.highlight_max}\n")
                    f.write(f"# Data Inverted: {self.dialog.plot_canvas.invert_data}\n")
                
                if hasattr(self.dialog.histogram_control, 'get_bins'):
                    f.write(f"# Histogram Bins: {self.dialog.histogram_control.get_bins()}\n")
                    f.write(f"# Log X Scale: {self.dialog.histogram_control.log_x_check.isChecked()}\n")
                    f.write(f"# Log Y Scale: {self.dialog.histogram_control.log_y_check.isChecked()}\n")
                    f.write(f"# Show KDE: {self.dialog.histogram_control.kde_check.isChecked()}\n")
                
                f.write("#\n")
                f.write("# Available Channels:\n")
                channels = self.dialog.data_manager.get_channels()
                for i, ch in enumerate(channels, 1):
                    f.write(f"# Channel {i}: {ch}\n")
                    
            return True
            
        except Exception as e:
            print(f"Error exporting metadata: {e}")
            return False
    
    def _export_histogram_stats(self, file_path):
        """导出直方图统计数据（包含原文件信息）"""
        try:
            # 检查是否在直方图标签页且有数据
            if (self.dialog.tab_widget.currentIndex() == 1 and 
                hasattr(self.dialog.subplot3_canvas, 'histogram_data')):
                
                data = self.dialog.subplot3_canvas.histogram_data
                hist_counts = self.dialog.subplot3_canvas.hist_counts
                bin_edges = self.dialog.subplot3_canvas.hist_bin_edges
                
            elif hasattr(self.dialog.plot_canvas, 'data'):
                # 使用主视图数据
                highlight_min = self.dialog.plot_canvas.highlight_min
                highlight_max = self.dialog.plot_canvas.highlight_max
                data = self.dialog.plot_canvas.data[highlight_min:highlight_max]
                
                if self.dialog.plot_canvas.invert_data:
                    data = -data
                
                # 创建直方图
                bins = self.dialog.histogram_control.get_bins()
                hist_counts, bin_edges = np.histogram(data, bins=bins)
            else:
                return False
            
            # 计算统计信息
            stats = {
                "total_points": len(data),
                "min_value": float(np.min(data)),
                "max_value": float(np.max(data)),
                "mean": float(np.mean(data)),
                "median": float(np.median(data)),
                "std_dev": float(np.std(data)),
                "bins_count": len(hist_counts)
            }
            
            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # 写入文件头信息
                csvfile.write(f"# Histogram Statistics Export\n")
                csvfile.write(f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                    csvfile.write(f"# Source File: {self.dialog.data_manager.file_path}\n")
                if hasattr(self.dialog.data_manager, 'selected_channel'):
                    csvfile.write(f"# Channel: {self.dialog.data_manager.selected_channel}\n")
                csvfile.write("#\n")
                
                # 写入统计信息
                csvfile.write("# Histogram Statistics\n")
                for key, value in stats.items():
                    csvfile.write(f"# {key}: {value}\n")
                csvfile.write("#\n")
                
                # 写入直方图数据
                csvfile.write("# Histogram Data\n")
                writer = csv.writer(csvfile)
                writer.writerow(["bin_min", "bin_max", "bin_center", "count"])
                
                for i in range(len(hist_counts)):
                    bin_min = bin_edges[i]
                    bin_max = bin_edges[i+1]
                    bin_center = (bin_min + bin_max) / 2
                    writer.writerow([bin_min, bin_max, bin_center, hist_counts[i]])
            
            return True
            
        except Exception as e:
            print(f"Error exporting histogram stats: {e}")
            return False
    
    def _export_fit_data(self, file_path):
        """导出拟合数据（包含原文件信息）"""
        try:
            if not hasattr(self.dialog, 'fit_info_panel'):
                return False
                
            fit_list = self.dialog.fit_info_panel.fit_list
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # 写入文件头信息
                csvfile.write(f"# Gaussian Fit Data Export\n")
                csvfile.write(f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                    csvfile.write(f"# Source File: {self.dialog.data_manager.file_path}\n")
                if hasattr(self.dialog.data_manager, 'selected_channel'):
                    csvfile.write(f"# Channel: {self.dialog.data_manager.selected_channel}\n")
                csvfile.write(f"# Number of Fits: {fit_list.count()}\n")
                csvfile.write("#\n")
                
                writer = csv.writer(csvfile)
                writer.writerow(["fit_index", "amplitude", "mu", "sigma", "fwhm", "x_range_min", "x_range_max"])
                
                if fit_list.count() == 0:
                    # 如果没有拟合数据，只写入头信息
                    csvfile.write("# No fit data available\n")
                else:
                    for i in range(fit_list.count()):
                        item = fit_list.item(i)
                        data = item.data(Qt.ItemDataRole.UserRole)
                        
                        writer.writerow([
                            data['fit_index'],
                            data['amp'],
                            data['mu'],
                            data['sigma'],
                            data['fwhm'],
                            data['x_range'][0],
                            data['x_range'][1]
                        ])
            
            return True
            
        except Exception as e:
            print(f"Error exporting fit data: {e}")
            return False
    
    def _export_raw_data(self, file_path):
        """导出原始数据（包含原文件信息）"""
        try:
            # 获取当前高亮区域的原始数据
            if not hasattr(self.dialog.plot_canvas, 'data'):
                return False
            
            highlight_min = self.dialog.plot_canvas.highlight_min
            highlight_max = self.dialog.plot_canvas.highlight_max
            current_channel = self.dialog.data_manager.selected_channel
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # 写入文件头信息
                csvfile.write(f"# Raw Data Export - Highlighted Region\n")
                csvfile.write(f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if hasattr(self.dialog.data_manager, 'file_path') and self.dialog.data_manager.file_path:
                    csvfile.write(f"# Source File: {self.dialog.data_manager.file_path}\n")
                csvfile.write(f"# Selected Channel: {current_channel}\n")
                csvfile.write(f"# Time range (samples): {highlight_min} - {highlight_max}\n")
                csvfile.write(f"# Sampling rate: {self.dialog.data_manager.sampling_rate} Hz\n")
                csvfile.write(f"# Time range (seconds): {highlight_min/self.dialog.data_manager.sampling_rate:.6f} - {highlight_max/self.dialog.data_manager.sampling_rate:.6f}\n")
                csvfile.write(f"# Data points: {highlight_max - highlight_min}\n")
                csvfile.write(f"# Data inverted: {self.dialog.plot_canvas.invert_data}\n")
                csvfile.write("#\n")
                
                writer = csv.writer(csvfile)
                
                # 获取所有通道数据
                channels = self.dialog.data_manager.get_channels()
                headers = ["sample_index", "time_seconds"] + [f"channel_{ch}" for ch in channels]
                writer.writerow(headers)
                
                # 写入数据
                for i in range(highlight_min, highlight_max):
                    time_seconds = i / self.dialog.data_manager.sampling_rate
                    row = [i, time_seconds]
                    for ch in channels:
                        ch_data = self.dialog.data_manager.get_channel_data(ch)
                        if ch_data is not None and i < len(ch_data):
                            value = ch_data[i]
                            # 只对选中的通道应用数据取反
                            if ch == current_channel and self.dialog.plot_canvas.invert_data:
                                value = -value
                            row.append(value)
                        else:
                            row.append(np.nan)
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting raw data: {e}")
            return False
    
    def _export_main_view_image(self, file_path):
        """导出主视图图像"""
        try:
            if hasattr(self.dialog, 'plot_canvas'):
                self.dialog.plot_canvas.figure.savefig(
                    file_path, 
                    dpi=300, 
                    bbox_inches='tight',
                    facecolor='white',
                    edgecolor='none'
                )
                return True
            return False
            
        except Exception as e:
            print(f"Error exporting main view image: {e}")
            return False
    
    def _export_histogram_view_image(self, file_path):
        """导出直方图视图图像"""
        try:
            if hasattr(self.dialog, 'subplot3_canvas'):
                self.dialog.subplot3_canvas.figure.savefig(
                    file_path, 
                    dpi=300, 
                    bbox_inches='tight',
                    facecolor='white',
                    edgecolor='none'
                )
                return True
            return False
            
        except Exception as e:
            print(f"Error exporting histogram view image: {e}")
            return False


class ImageClipboardManager:
    """图像剪贴板管理器"""
    
    @staticmethod
    def copy_combined_images_to_clipboard(main_canvas, histogram_canvas):
        """将主视图和直方图合并后复制到剪贴板"""
        try:
            # 1. 渲染main view到缓冲区
            main_buffer = io.BytesIO()
            main_canvas.figure.savefig(
                main_buffer, 
                format='png', 
                dpi=300,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none'
            )
            main_buffer.seek(0)
            
            # 2. 渲染histogram view到缓冲区
            hist_buffer = io.BytesIO()
            histogram_canvas.figure.savefig(
                hist_buffer, 
                format='png', 
                dpi=300,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none'
            )
            hist_buffer.seek(0)
            
            # 3. 使用PIL合并图像
            main_image = Image.open(main_buffer)
            hist_image = Image.open(hist_buffer)
            
            # 调整图像高度一致
            min_height = min(main_image.height, hist_image.height)
            main_image = main_image.resize((
                int(main_image.width * min_height / main_image.height), 
                min_height
            ), Image.Resampling.LANCZOS)
            hist_image = hist_image.resize((
                int(hist_image.width * min_height / hist_image.height), 
                min_height
            ), Image.Resampling.LANCZOS)
            
            # 水平合并
            total_width = main_image.width + hist_image.width
            combined_image = Image.new('RGB', (total_width, min_height), 'white')
            combined_image.paste(main_image, (0, 0))
            combined_image.paste(hist_image, (main_image.width, 0))
            
            # 4. 转换为QPixmap并复制到剪贴板
            # 将PIL图像转换为字节流
            img_buffer = io.BytesIO()
            combined_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # 转换为QImage然后QPixmap
            qimage = QImage()
            qimage.loadFromData(img_buffer.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            
            return True, "Images copied to clipboard successfully"
            
        except Exception as e:
            return False, f"Error copying images: {str(e)}"


class HistogramExporter:
    """直方图数据导出器（保持向后兼容）"""
    
    def __init__(self, parent=None):
        self.parent = parent
        
    def copy_fit_info_to_clipboard(self, fit_info_str):
        """复制拟合信息到剪贴板（保持向后兼容）"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(fit_info_str)
            return True, "Fit information copied to clipboard"
        except Exception as e:
            return False, str(e)
