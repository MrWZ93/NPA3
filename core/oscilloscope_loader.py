#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
示波器CSV文件加载模块 - 修复版本
"""

import numpy as np
import pandas as pd
import os
from datetime import datetime
import traceback
import logging

def load_oscilloscope_csv(file_path):
    """
    加载示波器格式的CSV文件
    返回：数据字典, 文件信息字典, 采样率
    """
    # 初始化变量，防止finally块引用未声明的变量
    old_options = None
    old_workers = None
    
    try:
        # 设置pandas不使用多线程
        old_options = pd.options.mode.chained_assignment
        pd.options.mode.chained_assignment = None
        
        # 设置较小的线程池，以防止创建过多线程
        import multiprocessing
        old_workers = pd.options.io_thread_count 
        pd.options.io_thread_count = 1  # 强制单线程
        
        # 读取整个文件
        with open(file_path, 'r', errors='replace') as f:
            lines = f.readlines()
        
        if not lines:
            raise ValueError("Empty file")
        
        # 打印文件信息
        logging.info(f"File has {len(lines)} lines")
        logging.info(f"First line: {lines[0].strip()}")
        
        # 检查是否是示波器格式
        if not ("Model" in lines[0] and "Xviewer" in lines[0]):
            # 如果不是示波器格式，返回None让普通CSV加载器处理
            return None, None, None
        
        logging.info("Detected oscilloscope format CSV file")
        
        # 解析元数据
        metadata = {}
        data_start_line = 0
        h_resolution = None
        h_offset = None
        block_size = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 找到数据开始的行
            if line.startswith(","):
                data_start_line = i
                break
                
            # 解析元数据行
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                key = parts[0].strip('"')
                values = [p.strip('"') for p in parts[1:] if p.strip()]
                
                if key == "HResolution" and values:
                    try:
                        h_resolution = float(values[0])
                        metadata["Sampling Rate"] = f"{1.0/h_resolution} Hz"
                        logging.info(f"Found sampling rate: {1.0/h_resolution} Hz")
                    except Exception as e:
                        logging.warning(f"Error parsing HResolution: {e}")
                        
                elif key == "HOffset" and values:
                    try:
                        h_offset = float(values[0])
                    except Exception as e:
                        logging.warning(f"Error parsing HOffset: {e}")
                
                elif key == "BlockSize" and values:
                    try:
                        block_size = int(values[0])
                        metadata["Sample Points"] = block_size
                    except Exception as e:
                        logging.warning(f"Error parsing BlockSize: {e}")
                
                # 保存所有元数据
                if values:
                    metadata[key] = values[0] if len(values) == 1 else values
        
        # 如果没有找到数据行，使用第10行作为数据开始行（常见的示波器格式）
        if data_start_line == 0:
            data_start_line = min(10, len(lines) - 1)
            logging.warning(f"Could not find data start marker, assuming data starts at line {data_start_line}")
        
        # 计算采样率
        sampling_rate = 1.0 / h_resolution if h_resolution else 1.0
        
        # 解析数据部分
        data_lines = lines[data_start_line:]
        data_values = []
        
        # 调试: 打印前几行数据
        logging.info(f"Data section starts at line {data_start_line}, first few data lines:")
        for i in range(min(5, len(data_lines))):
            logging.info(f"Line {i}: {data_lines[i].strip()}")
        
        # 处理数据行
        use_lines = []
        for line in data_lines:
            line = line.strip()
            if line.startswith(","):
                line = line[1:]  # 移除开头的逗号
            if line and not line.isspace():
                use_lines.append(line)
        
        # 调试: 再次打印处理后的数据
        logging.info(f"First few processed data lines:")
        for i in range(min(5, len(use_lines))):
            logging.info(f"Line {i}: {use_lines[i]}")
        
        # 执行实际的数据解析
        for line in use_lines:
            line = line.strip()
            if not line:
                continue
                
            values = [v.strip() for v in line.split(',')]
            if len(values) >= 1:  # 至少有一个值
                try:
                    # 将所有数字转换为浮点数
                    numeric_values = []
                    for v in values:
                        if not v.strip():  # 跳过空值
                            numeric_values.append(np.nan)
                        else:
                            try:
                                numeric_values.append(float(v))
                            except ValueError:
                                numeric_values.append(np.nan)
                    data_values.append(numeric_values)
                except Exception as e:
                    logging.warning(f"Error converting line to numbers: {str(e)}")
                    continue
        
        # 将数据转换为数组
        if not data_values:
            raise ValueError("No valid data found in file")
            
        # 转换为NumPy数组
        data_array = np.array(data_values)
        logging.info(f"Data array shape: {data_array.shape}")
        
        # 处理特殊情况: 只有一列数据
        if data_array.shape[1] < 2:
            logging.warning(f"Only one data column found. Creating time column automatically.")
            
            # 创建时间列
            time_column = np.arange(data_array.shape[0]) * (h_resolution or 1.0)
            channels_data = data_array[:, 0].reshape(-1, 1)  # 确保是2D数组
        else:
            # 提取数据，第一列是时间，其余是各通道数据
            time_column = data_array[:, 0]
            channels_data = data_array[:, 1:]
        
        # 检查并清理NaN值
        nan_count = np.isnan(channels_data).sum()
        if nan_count > 0:
            logging.warning(f"Found {nan_count} NaN values in data. Replacing with zeros.")
            channels_data = np.nan_to_num(channels_data)
            time_column = np.nan_to_num(time_column)
        
        # 创建数据字典，为每个通道分配数据
        data_dict = {}
        
        # 使用元数据中的通道名称
        trace_names = []
        if "TraceName" in metadata:
            if isinstance(metadata["TraceName"], list):
                trace_names = metadata["TraceName"]
            else:
                trace_names = [metadata["TraceName"]]
        
        # 确保我们有足够的通道名称
        while len(trace_names) < channels_data.shape[1]:
            trace_names.append(f"Channel {len(trace_names)+1}")
        
        # 添加每个通道的数据到字典
        for i in range(channels_data.shape[1]):
            channel_name = trace_names[i] if i < len(trace_names) else f"Channel {i+1}"
            data_dict[channel_name] = channels_data[:, i]
            logging.info(f"Channel {channel_name}: {len(channels_data[:, i])} points")
        
        # 添加时间列
        data_dict["Time"] = time_column
        logging.info(f"Time column: {len(time_column)} points")
        
        # 准备文件信息
        file_info = {
            "File Type": "Oscilloscope CSV",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": len(trace_names),
            "Sample Points": len(time_column),
            "Sampling Rate": f"{sampling_rate:.1f} Hz"
        }
        
        # 添加其他有用的元数据
        for key, value in metadata.items():
            if key not in file_info and key not in ["Model", "Xviewer"]:
                file_info[key] = value
        
        return data_dict, file_info, sampling_rate
        
    except Exception as e:
        # 如果处理过程中出现错误，返回None以让普通CSV加载器尝试处理
        logging.error(f"Error processing oscilloscope CSV: {str(e)}")
        traceback.print_exc()
        return None, None, None
        
    finally:
        # 恢复原始设置
        if old_options is not None:
            pd.options.mode.chained_assignment = old_options
        if old_workers is not None:
            pd.options.io_thread_count = old_workers
