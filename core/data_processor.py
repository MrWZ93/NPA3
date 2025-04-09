#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件数据处理模块
"""

import os
import numpy as np
import pandas as pd
import h5py
from datetime import datetime
from scipy import signal
import traceback

# 导入示波器CSV文件加载模块
try:
    from core.load_oscilloscope_csv import load_oscilloscope_csv
    OSCILLOSCOPE_CSV_SUPPORT = True
except ImportError:
    OSCILLOSCOPE_CSV_SUPPORT = False
    print("load_oscilloscope_csv module not found, oscilloscope CSV support will be limited")

# 尝试导入不同文件格式的库
try:
    import nptdms
    TDMS_SUPPORT = True
except ImportError:
    TDMS_SUPPORT = False
    print("nptdms library not installed, TDMS format support will not be available")

try:
    import pyabf
    ABF_SUPPORT = True
except ImportError:
    ABF_SUPPORT = False
    print("pyabf library not installed, ABF format support will not be available")

# 设置CSV格式支持
CSV_SUPPORT = True
print("CSV format support enabled")

class FileDataProcessor:
    """文件数据处理类"""
    def __init__(self):
        self.current_data = None
        self.file_info = {}
        self.file_path = None
        self.file_type = None
        self.sampling_rate = 1000.0  # Default sampling rate
    
    def load_file(self, file_path):
        """加载文件"""
        self.file_path = file_path
        self.file_type = os.path.splitext(file_path)[1].lower()
        
        try:
            if self.file_type == '.tdms' and TDMS_SUPPORT:
                self._load_tdms(file_path)
            elif self.file_type == '.h5':
                self._load_h5(file_path)
            elif self.file_type == '.abf' and ABF_SUPPORT:
                self._load_abf(file_path)
            elif self.file_type == '.csv' and CSV_SUPPORT:
                self._load_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {self.file_type}")
            
            return True, self.current_data, self.file_info
            
        except Exception as e:
            return False, None, {"Error": str(e)}
    
    def _load_tdms(self, file_path):
        """加载TDMS文件"""
        tdms_file = nptdms.TdmsFile.read(file_path)
        
        # 获取基本信息
        self.file_info = {
            "File Type": "TDMS",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": len(tdms_file.groups())
        }
        
        # 加载数据
        self.current_data = {}
        for group in tdms_file.groups():
            for channel in group.channels():
                channel_name = f"{group.name}/{channel.name}"
                self.current_data[channel_name] = channel[:]
        
    def _load_h5(self, file_path):
        """加载H5文件"""
        with h5py.File(file_path, 'r') as h5file:
            # 获取基本信息
            self.file_info = {
                "File Type": "HDF5",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Dataset Count": len(h5file.keys())
            }
            
            # 加载主要数据集
            self.current_data = {}
            
            def extract_datasets(name, obj):
                if isinstance(obj, h5py.Dataset):
                    # 只加载数值型数据集
                    if obj.dtype.kind in 'iuf':  # 整数, 无符号整数, 浮点数
                        try:
                            self.current_data[name] = obj[:]
                        except Exception as e:
                            import logging
                            logging.warning(f"Could not load dataset {name}: {str(e)}")
                            self.current_data[name] = "Dataset too large or incompatible format"
            
            h5file.visititems(extract_datasets)
    
    def _load_abf(self, file_path):
        """加载ABF文件"""
        abf = pyabf.ABF(file_path)
        
        # 获取基本信息
        self.file_info = {
            "File Type": "ABF",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": abf.channelCount,
            "Sampling Rate": f"{abf.dataRate} Hz",
            "Sample Points": abf.sweepPointCount,
            "Protocol": abf.protocol,
            "Creation Time": abf.abfDateTime
        }
        
        # 加载数据
        self.current_data = {}
        for i in range(abf.channelCount):
            abf.setSweep(sweepNumber=0, channel=i)
            self.current_data[f"Channel {i+1}"] = abf.sweepY
        
        # Store the sampling rate
        self.sampling_rate = abf.dataRate
    
    def _load_csv(self, file_path):
        """加载CSV文件 - 优化版本，添加示波器CSV支持"""
        # 初始化变量，防止finally块引用未声明的变量
        old_thread_count = None
        
        try:
            import logging
            logging.info(f"Loading CSV file: {file_path}")
            
            # 检查文件路径是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 控制pandas的多线程设置
            try:
                old_thread_count = pd.options.io_thread_count
                pd.options.io_thread_count = 1  # 强制使用单线程模式
            except Exception as thread_exc:
                logging.warning(f"Failed to set thread count: {str(thread_exc)}")
            
            # 首先尝试使用示波器CSV加载器
            if OSCILLOSCOPE_CSV_SUPPORT:
                try:
                    # 判断是否可能是示波器CSV格式
                    is_oscilloscope = False
                    with open(file_path, 'r', errors='replace') as f:
                        for i in range(10):  # 检查前10行
                            line = f.readline()
                            if not line:
                                break
                            if any(keyword in line for keyword in ["Model", "BlockNumber", "TraceName", "Xviewer", "HResolution"]):
                                is_oscilloscope = True
                                break
                    
                    if is_oscilloscope:
                        logging.info("Detected possible oscilloscope CSV format, using specialized loader")
                        # 调用示波器CSV加载器，设置force_time_from_zero=True使时间轴从0开始
                        data_dict, file_info, sampling_rate = load_oscilloscope_csv(file_path, force_time_from_zero=True)
                        if data_dict is not None and file_info is not None:
                            # 示波器CSV文件成功加载
                            self.current_data = data_dict
                            self.file_info = file_info
                            if sampling_rate is not None and sampling_rate > 0:
                                self.sampling_rate = sampling_rate
                            return
                except Exception as osc_error:
                    logging.warning(f"Oscilloscope CSV loader failed: {str(osc_error)}")
                    traceback.print_exc()
            
            # 如果不是示波器格式或示波器加载器不可用，继续使用标准CSV加载
            # 先读取文件前10行来分析文件结构
            with open(file_path, 'r', errors='replace') as f:
                header_lines = [f.readline() for _ in range(10)]
            
            # 检测可能的分隔符
            possible_delimiters = [',', '\t', ';', ' ']
            delimiter = ','
            for d in possible_delimiters:
                if any(header_lines[i].count(d) > 1 for i in range(min(5, len(header_lines)))):
                    delimiter = d
                    break
            
            # 检测文件是否有头部元数据/注释行
            skip_rows = 0
            for line in header_lines:
                if line.strip() == "" or line.startswith("#"):
                    skip_rows += 1
                else:
                    break
                    
            # 使用分块读取处理大文件
            try:
                # 尝试使用高效读取模式
                df = pd.read_csv(file_path,
                                delimiter=delimiter,
                                skiprows=skip_rows,
                                on_bad_lines='skip',
                                memory_map=True,  # 使用内存映射减少内存使用
                                low_memory=True,  # 低内存模式
                                dtype=None,       # 自动检测数据类型
                                encoding='utf-8-sig')  # 处理带BOM的UTF-8
            except Exception as e:
                logging.warning(f"Initial CSV parsing failed: {str(e)}, trying alternative method")
                try:
                    # 使用更宽松的引擎
                    df = pd.read_csv(file_path,
                                    delimiter=delimiter,
                                    skiprows=skip_rows,
                                    engine='python',
                                    on_bad_lines='skip')
                except Exception as e2:
                    logging.warning(f"Python engine CSV parsing failed: {str(e2)}, trying final fallback")
                    # 最后的后备方案 - 使用迭代读取
                    try:
                        # 尝试分块读取并合并
                        chunks = pd.read_csv(file_path,
                                          delimiter=delimiter,
                                          skiprows=skip_rows,
                                          on_bad_lines='skip',
                                          chunksize=10000)  # 每次读取10000行
                        df = pd.concat([chunk for chunk in chunks])
                    except:
                        # 如果所有方法都失败，回退到原始的CSV解析器
                        import csv
                        with open(file_path, 'r', errors='replace') as f:
                            reader = csv.reader(f, delimiter=delimiter)
                            rows = list(reader)
                        
                        if not rows:
                            raise ValueError("Cannot parse CSV file, no valid data rows found")
                            
                        # 找出最常见的列数
                        col_counts = [len(row) for row in rows if row]
                        most_common_count = max(set(col_counts), key=col_counts.count)
                        
                        # 只保留列数正确的行
                        valid_rows = [row for row in rows if len(row) == most_common_count]
                        
                        if valid_rows:
                            header = valid_rows[0]
                            data = valid_rows[1:]
                            df = pd.DataFrame(data, columns=header)
            
            # 尝试将所有可能的列转换为数值
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass  # 无法转换的列保持原样
            
            # 获取基本信息
            self.file_info = {
                "File Type": "CSV",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Rows": len(df),
                "Columns": len(df.columns),
                "Column Names": ", ".join(df.columns.tolist())
            }
            
            # 检查数据类型
            numeric_columns = df.select_dtypes(include=np.number).columns.tolist()
            if numeric_columns:
                self.file_info["Numeric Columns"] = ", ".join(numeric_columns)
            
            # 首先检查是否有时间列
            time_cols = [col for col in df.columns if any(time_keyword in str(col).lower() 
                            for time_keyword in ['time', 'date', '时间', '日期'])]
            
            # 构建数据字典
            self.current_data = {}
            
            # 如果有时间列，尝试将其作为X轴
            x_data = None
            if time_cols and len(time_cols) > 0:
                time_col = time_cols[0]
                try:
                    # 尝试将时间列转换为日期时间格式
                    x_data = pd.to_datetime(df[time_col])
                    self.file_info["Time Column"] = time_col
                except:
                    # 如果转换失败，使用原始数据
                    x_data = df[time_col].values
            
            # 将数值列加载为数据通道
            for col in numeric_columns:
                if col in time_cols:
                    continue  # 跳过时间列
                
                # 将列数据保存到字典中
                self.current_data[col] = df[col].values
            
            # 如果没有找到数值列，尝试将所有列都加载为数据
            if not self.current_data:
                for col in df.columns:
                    try:
                        # 尝试将列转换为数值类型
                        values = pd.to_numeric(df[col], errors='coerce').fillna(0).values
                        self.current_data[col] = values
                    except:
                        # 如果转换失败，跳过该列
                        continue
            
            # 如果仍然没有数据，返回错误
            if not self.current_data:
                raise ValueError("Cannot find valid numeric data in CSV file")
                
        except Exception as e:
            self.file_info = {
                "File Type": "CSV",
                "File Path": file_path,
                "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
                "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                "Error": f"Error reading CSV file: {str(e)}"
            }
            
            # 错误情况下的示例数据
            self.current_data = {"Error": np.zeros(100)}
            
            # 打印堆栈跟踪信息以便调试
            traceback.print_exc()
            
        finally:
            # 恢复原始pandas设置
            if old_thread_count is not None:
                try:
                    pd.options.io_thread_count = old_thread_count
                except Exception:
                    pass  # 忽略恢复设置时的错误
    
    def process_data(self, operation, params=None):
        """处理数据"""
        if self.current_data is None:
            return False, None, "No data to process"
        
        processed_data = {}
        
        try:
            # Get sampling rate from params
            sampling_rate = params.get("sampling_rate", self.sampling_rate)
            
            # 检查是否选择了特定通道
            selected_channel = params.get("channel", None)
            
            if isinstance(self.current_data, dict):
                # 如果数据是字典，处理指定通道或全部通道
                channels_to_process = [selected_channel] if selected_channel else self.current_data.keys()
                
                # 检查是否有Time通道
                has_time_channel = "Time" in self.current_data
                time_data = self.current_data.get("Time", None)
                
                # 先复制原始数据，只处理选定的通道
                for channel in self.current_data.keys():
                    if channel in channels_to_process or channel == "Time":
                        # 执行选定通道的处理
                        data = self.current_data[channel]
                        if isinstance(data, np.ndarray):
                            if operation == "裁切":
                                # Get time values
                                start_time = params.get("start_time", 0)
                                end_time = params.get("end_time", len(data) / sampling_rate)
                                
                                # 特殊处理Time通道 - 直接使用相对时间（从0开始）进行裁切
                                if channel == "Time" and time_data is not None:
                                    # 计算相对时间（从0开始）
                                    time_offset = time_data[0] if len(time_data) > 0 else 0
                                    relative_time = time_data - time_offset
                                    
                                    # 根据输入的范围在相对时间上找到索引
                                    start_indices = np.where(relative_time >= start_time)[0]
                                    if len(start_indices) == 0:
                                        max_time = np.max(relative_time)
                                        raise ValueError(f"起始时间 {start_time}s 超出了有效范围（最大时间为 {max_time:.3f}s）")
                                    start_sample = start_indices[0]
                                    
                                    end_indices = np.where(relative_time <= end_time)[0]
                                    if len(end_indices) == 0:
                                        max_time = np.max(relative_time)
                                        raise ValueError(f"结束时间 {end_time}s 超出了有效范围（最大时间为 {max_time:.3f}s）")
                                    end_sample = end_indices[-1]
                                    
                                    # 确保end_sample > start_sample
                                    if end_sample <= start_sample:
                                        raise ValueError(f"裁切范围无效：结束时间必须大于起始时间")
                                    
                                    # 保存范围信息，用于基于图表显示的反馈
                                    actual_relative_start = relative_time[start_sample]
                                    actual_relative_end = relative_time[end_sample]
                                    print(f"裁切时间通道: 输入范围 {start_time}s-{end_time}s, 实际裁切范围（x轴上显示） {actual_relative_start:.3f}s-{actual_relative_end:.3f}s")
                                    
                                    # 记录偏移量，用于后续的更新
                                    self.time_offset = time_offset
                                    
                                    # 确保end_sample > start_sample
                                    if end_sample <= start_sample:
                                        end_sample = min(start_sample + 1, len(time_data)-1)
                                        
                                    # 保存开始和结束索引，以便其他通道使用相同的裁切范围
                                    time_start_sample = start_sample
                                    time_end_sample = end_sample
                                    
                                    # 获取实际的时间范围
                                    actual_start = time_data[start_sample]
                                    actual_end = time_data[end_sample]
                                    print(f"裁切时间通道: 请求范围 {start_time}-{end_time}s, 实际范围 {actual_start}-{actual_end}s")
                                else:
                                    # 对于非Time通道，使用与Time通道相同的索引范围
                                    if has_time_channel and 'time_start_sample' in locals() and 'time_end_sample' in locals():
                                        start_sample = time_start_sample
                                        end_sample = time_end_sample
                                    else:
                                        # 回退到采样率计算
                                        start_sample = int(start_time * sampling_rate)
                                        end_sample = int(end_time * sampling_rate)
                                
                                # Make sure indices are within bounds
                                start_sample = max(0, min(start_sample, len(data) - 1))
                                end_sample = max(start_sample + 1, min(end_sample, len(data)))
                                
                                processed_data[channel] = data[start_sample:end_sample]
                            
                            elif operation == "低通滤波":
                                # Get frequency in Hz
                                cutoff_hz = params.get("cutoff_hz", 1000)
                                
                                # Safety check: ensure cutoff is less than Nyquist frequency
                                nyquist = sampling_rate / 2
                                if cutoff_hz >= nyquist:
                                    # If cutoff is too high, set it to 99% of Nyquist
                                    cutoff_hz = 0.99 * nyquist
                                
                                # Convert to normalized frequency (0-1) required by scipy.signal.butter
                                cutoff_norm = cutoff_hz / nyquist
                                
                                # 特殊处理Time通道 - 不对时间通道应用滤波
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    # Use a try-except block to handle filter design errors
                                    try:
                                        b, a = signal.butter(4, cutoff_norm, 'low')
                                        processed_data[channel] = signal.filtfilt(b, a, data)
                                    except Exception as e:
                                        return False, None, f"Filter design error: {str(e)}"
                            
                            elif operation == "高通滤波":
                                # Get frequency in Hz
                                cutoff_hz = params.get("cutoff_hz", 1000)
                                
                                # Safety check: ensure cutoff is less than Nyquist frequency
                                nyquist = sampling_rate / 2
                                if cutoff_hz >= nyquist:
                                    # If cutoff is too high, set it to 99% of Nyquist
                                    cutoff_hz = 0.99 * nyquist
                                
                                # Convert to normalized frequency (0-1) required by scipy.signal.butter
                                cutoff_norm = cutoff_hz / nyquist
                                
                                # 特殊处理Time通道 - 不对时间通道应用滤波
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    # Use a try-except block to handle filter design errors
                                    try:
                                        b, a = signal.butter(4, cutoff_norm, 'high')
                                        processed_data[channel] = signal.filtfilt(b, a, data)
                                    except Exception as e:
                                        return False, None, f"Filter design error: {str(e)}"
                            
                            elif operation == "基线校正":
                                # 特殊处理Time通道 - 不对时间通道进行基线校正
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    baseline = params.get("baseline", np.mean(data[:params.get("points", 100)]))
                                    processed_data[channel] = data - baseline
                            
                            else:
                                processed_data[channel] = data.copy()
                        else:
                            processed_data[channel] = data
                    else:
                        # 对于未选中的通道，直接保持原样
                        processed_data[channel] = self.current_data[channel]
            
            # 其余代码保持不变...
            elif isinstance(self.current_data, np.ndarray):
                # 处理NumPy数组类型的数据
                data = self.current_data
                
                if data.ndim == 1 or selected_channel is None:
                    # 对1D数组或没有选择特定通道的情况，处理所有数据
                    if operation == "裁切":
                        # Get time values
                        start_time = params.get("start_time", 0)
                        end_time = params.get("end_time", len(data) / sampling_rate)
                        
                        # Convert time to samples
                        start_sample = int(start_time * sampling_rate)
                        end_sample = int(end_time * sampling_rate)
                        
                        # Make sure indices are within bounds
                        start_sample = max(0, min(start_sample, data.shape[0] - 1))
                        end_sample = max(start_sample + 1, min(end_sample, data.shape[0]))
                        
                        processed_data = data[start_sample:end_sample]
                    
                    # 其余代码保持不变...

            # 将悬浮的NaN值设为0
            if isinstance(processed_data, dict):
                for channel in processed_data:
                    if isinstance(processed_data[channel], np.ndarray):
                        processed_data[channel] = np.nan_to_num(processed_data[channel])
            elif isinstance(processed_data, np.ndarray):
                processed_data = np.nan_to_num(processed_data)
            
            # 对于裁切操作，返回实际裁切的时间范围
            if operation == "裁切" and isinstance(processed_data, dict) and "Time" in processed_data:
                time_data = processed_data["Time"]
                if len(time_data) > 0:
                    # 计算相对时间（图表x轴上显示的时间）
                    time_offset = getattr(self, 'time_offset', time_data[0])
                    relative_start = time_data[0] - time_offset
                    relative_end = time_data[-1] - time_offset
                    
                    return True, processed_data, f"处理成功: 裁切范围（图表x轴上显示的） {relative_start:.3f}s - {relative_end:.3f}s"
            
            return True, processed_data, "Processing successful"
            
        except Exception as e:
            return False, None, f"Processing error: {str(e)}"
    
    def save_processed_data(self, data, save_path):
        """保存处理后的数据为H5格式"""
        try:
            with h5py.File(save_path, 'w') as h5file:
                # 添加元数据
                h5file.attrs['source_file'] = self.file_path
                h5file.attrs['source_type'] = self.file_type
                h5file.attrs['processed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                h5file.attrs['sampling_rate'] = self.sampling_rate
                
                # 存储数据
                if isinstance(data, dict):
                    for channel, values in data.items():
                        if isinstance(values, np.ndarray):
                            h5file.create_dataset(channel, data=values)
                        
                elif isinstance(data, np.ndarray):
                    h5file.create_dataset('data', data=data)
                
                return True, "Data saved successfully"
                
        except Exception as e:
            return False, f"Save error: {str(e)}"