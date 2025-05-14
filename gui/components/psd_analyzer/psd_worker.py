#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSD计算工作线程模块
"""

import os
import numpy as np
import traceback
from datetime import datetime
from scipy import signal
import csv
import json
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox


class PSDWorker(QThread):
    """PSD计算工作线程，避免UI阻塞"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, data, fs, window, nperseg, noverlap, nfft, detrend, scaling):
        super().__init__()
        self.data = data
        self.fs = fs
        self.window = window
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.nfft = nfft
        self.detrend = detrend
        self.scaling = scaling
        
    def run(self):
        try:
            # 对于超大数据集，考虑分块处理
            if len(self.data) > 10_000_000:  # 1千万个样本点以上
                chunk_size = 5_000_000
                chunks = len(self.data) // chunk_size + (1 if len(self.data) % chunk_size else 0)
                frequencies = None
                psd_sum = None
                
                for i in range(chunks):
                    start_idx = i * chunk_size
                    end_idx = min(start_idx + chunk_size, len(self.data))
                    chunk_data = self.data[start_idx:end_idx]
                    
                    # 确保 noverlap < nperseg
                    noverlap = self.noverlap
                    if noverlap >= self.nperseg:
                        noverlap = self.nperseg - 1
                    
                    # 计算该块的PSD
                    f, p = signal.welch(
                        chunk_data, 
                        fs=self.fs,
                        window=self.window,
                        nperseg=self.nperseg,
                        noverlap=noverlap,
                        nfft=self.nfft,
                        detrend=self.detrend,
                        scaling=self.scaling,
                        return_onesided=True
                    )
                    
                    # 汇总结果
                    if frequencies is None:
                        frequencies = f
                        psd_sum = p
                    else:
                        psd_sum += p
                    
                    # 更新进度
                    self.progress.emit(int(100 * (i + 1) / chunks))
                
                # 平均多个块的PSD结果
                psd = psd_sum / chunks
            else:
                # 确保noverlap < nperseg
                noverlap = self.noverlap
                if noverlap >= self.nperseg:
                    noverlap = self.nperseg - 1
                    
                # 正常计算单个PSD
                frequencies, psd = signal.welch(
                    self.data, 
                    fs=self.fs,
                    window=self.window,
                    nperseg=self.nperseg,
                    noverlap=noverlap,
                    nfft=self.nfft,
                    detrend=self.detrend,
                    scaling=self.scaling,
                    return_onesided=True
                )
                self.progress.emit(100)
                
            # 返回结果
            self.finished.emit((frequencies, psd))
            
        except Exception as e:
            self.error.emit(str(e))
            traceback.print_exc()


def export_psd_to_csv(file_path, frequencies, psd, is_db_scale, normalized, plot_params, parent=None):
    """导出PSD数据到CSV文件"""
    try:
        # 使用UTF-8编码打开文件，并添加BOM头以支持Excel
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # 写入元数据头 (注释行)
            metadata = [f"# PSD Analysis - Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
            if 'window_type' in plot_params and plot_params['window_type']:
                metadata.append(f"# Window: {plot_params['window_type']}")
            if 'nfft' in plot_params and plot_params['nfft']:
                metadata.append(f"# NFFT: {plot_params['nfft']}")
            if 'sampling_rate' in plot_params and plot_params['sampling_rate']:
                metadata.append(f"# Sampling Rate: {plot_params['sampling_rate']} Hz")
            
            # 写入其他计算参数
            params_to_include = ['low_cutoff', 'high_cutoff', 'exclude_bins']
            for param in params_to_include:
                if param in plot_params and plot_params[param]:
                    metadata.append(f"# {param}: {plot_params[param]}")
            
            # 写入元数据
            for meta in metadata:
                writer.writerow([meta])
            
            # 写入头部
            header = ["Frequency (Hz)", "Power (V²/Hz)"]
            
            # 根据显示模式添加适当的列
            if is_db_scale:
                header.append("Power (dB)")
            
            if normalized:
                header.append("Normalized Power")
                if is_db_scale:
                    header.append("Normalized Power (dB)")
            
            writer.writerow(header)
            
            # 处理对数值
            psd_safe = np.maximum(psd, 1e-20)  # 避免log(0)
            psd_db = 10 * np.log10(psd_safe) if is_db_scale else None
            
            # 归一化处理
            max_psd = np.max(psd_safe)
            norm_psd = psd / max_psd if normalized else None
            norm_psd_db = 10 * np.log10(norm_psd) if norm_psd is not None and is_db_scale else None
            
            # 写入数据
            for i in range(len(frequencies)):
                row = [frequencies[i], psd_safe[i]]
                
                if is_db_scale:
                    row.append(psd_db[i])
                
                if normalized:
                    row.append(norm_psd[i])
                    if is_db_scale:
                        row.append(norm_psd_db[i])
                
                writer.writerow(row)
        
        if parent:
            QMessageBox.information(parent, "Success", f"PSD data exported to {file_path}")
        
        return True
        
    except Exception as e:
        if parent:
            QMessageBox.warning(parent, "Error", f"Error exporting PSD data: {str(e)}")
        traceback.print_exc()
        return False


def export_psd_to_json(file_path, frequencies, psd, is_db_scale, normalized, plot_params, peak_indices=None, parent=None):
    """导出PSD数据到JSON文件"""
    try:
        # 处理对数值和归一化
        psd_safe = np.maximum(psd, 1e-20)  # 避免log(0)
        
        data_dict = {
            "metadata": {
                "export_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "parameters": plot_params
            },
            "frequencies": frequencies.tolist(),
            "psd": psd_safe.tolist()
        }
        
        # 添加dB缩放
        if is_db_scale:
            data_dict["psd_db"] = (10 * np.log10(psd_safe)).tolist()
        
        # 添加归一化值
        if normalized:
            max_psd = np.max(psd_safe)
            norm_psd = psd_safe / max_psd
            data_dict["psd_normalized"] = norm_psd.tolist()
            
            if is_db_scale:
                data_dict["psd_normalized_db"] = (10 * np.log10(norm_psd)).tolist()
        
        # 如果有峰值检测结果，也导出
        if peak_indices is not None:
            data_dict["peaks"] = {
                "indices": peak_indices.tolist(),
                "frequencies": frequencies[peak_indices].tolist(),
                "powers": psd_safe[peak_indices].tolist()
            }
        
        # 写入JSON文件
        with open(file_path, 'w') as f:
            json.dump(data_dict, f, indent=2)
        
        if parent:
            QMessageBox.information(parent, "Success", f"PSD data exported to {file_path}")
        
        return True
        
    except Exception as e:
        if parent:
            QMessageBox.warning(parent, "Error", f"Error exporting PSD data: {str(e)}")
        traceback.print_exc()
        return False


def export_psd_to_npy(file_path, frequencies, psd, plot_params, parent=None):
    """导出PSD数据到NPY二进制文件"""
    try:
        # 创建一个包含频率和功率谱密度的结构化数组
        dtype = [('frequency', 'f8'), ('psd', 'f8')]
        data = np.zeros(len(frequencies), dtype=dtype)
        data['frequency'] = frequencies
        data['psd'] = psd
        
        # 保存为NPY文件
        np.save(file_path, data)
        
        # 同时生成一个元数据JSON文件
        meta_file = os.path.splitext(file_path)[0] + '_metadata.json'
        with open(meta_file, 'w') as f:
            json.dump({
                "export_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "parameters": plot_params,
                "structure": {
                    "fields": ["frequency", "psd"],
                    "types": ["float64", "float64"],
                    "units": ["Hz", "V²/Hz"]
                }
            }, f, indent=2)
        
        if parent:
            QMessageBox.information(parent, "Success", 
                                 f"PSD data exported to {file_path}\n"+
                                 f"Metadata saved to {meta_file}")
        
        return True
        
    except Exception as e:
        if parent:
            QMessageBox.warning(parent, "Error", f"Error exporting PSD data: {str(e)}")
        traceback.print_exc()
        return False
