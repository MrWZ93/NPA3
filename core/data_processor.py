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
            # 先读取文件内容来分析文件结构
            with open(file_path, 'r', errors='replace', encoding='utf-8-sig') as f:
                file_content = f.read()
            
            # 统一处理行结尾符，将\r\n和\r都转换为\n
            file_content = file_content.replace('\r\n', '\n').replace('\r', '\n')
            lines = file_content.split('\n')
            
            # 检测可能的分隔符（基于前几行非注释行）
            possible_delimiters = [',', '\t', ';', ' ']
            delimiter = ','
            for line in lines[:10]:
                if not line.startswith('#') and line.strip():
                    for d in possible_delimiters:
                        if line.count(d) > 1:
                            delimiter = d
                            break
                    break
            
            # 检测文件是否有头部元数据/注释行和采样率信息
            skip_rows = 0
            sampling_rate_found = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line == "" or line.startswith("#"):
                    skip_rows += 1
                    # 尝试提取采样率信息
                    if "sampling rate" in line.lower() or "sample rate" in line.lower():
                        import re
                        # 查找数字（可能是整数或浮点数）
                        numbers = re.findall(r'[0-9]+\.?[0-9]*', line)
                        if numbers:
                            try:
                                rate = float(numbers[0])
                                if rate > 0:
                                    sampling_rate_found = rate
                                    logging.info(f"Found sampling rate in header: {rate} Hz")
                            except ValueError:
                                pass
                else:
                    break
            
            # 如果找到了采样率，更新默认值
            if sampling_rate_found:
                self.sampling_rate = sampling_rate_found
            
            # 使用不同方法尝试读取CSV数据
            df = None
            
            # 方法1：使用pandas直接读取
            try:
                # 使用StringIO来处理预处理的内容
                from io import StringIO
                processed_content = '\n'.join(lines[skip_rows:])
                
                df = pd.read_csv(StringIO(processed_content),
                                delimiter=delimiter,
                                on_bad_lines='skip',
                                low_memory=True,
                                dtype=None)
            except Exception as e:
                logging.warning(f"StringIO CSV parsing failed: {str(e)}, trying direct file reading")
            
            # 方法2：如果方法1失败，尝试直接从文件读取
            if df is None:
                try:
                    df = pd.read_csv(file_path,
                                    delimiter=delimiter,
                                    skiprows=skip_rows,
                                    on_bad_lines='skip',
                                    encoding='utf-8-sig',
                                    engine='python')  # 使用python引擎处理特殊情况
                except Exception as e:
                    logging.warning(f"Direct file CSV parsing failed: {str(e)}, trying manual parsing")
            
            # 方法3：如果前两种方法都失败，使用手动解析
            if df is None:
                try:
                    # 手动解析CSV数据
                    import csv
                    from io import StringIO
                    processed_content = '\n'.join(lines[skip_rows:])
                    
                    # 使用csv模块解析
                    reader = csv.reader(StringIO(processed_content), delimiter=delimiter)
                    rows = [row for row in reader if row]  # 过滤空行
                    
                    if not rows:
                        raise ValueError("Cannot parse CSV file, no valid data rows found")
                    
                    # 第一行作为列标题
                    header = [col.strip() for col in rows[0]]
                    data_rows = rows[1:]
                    
                    # 创建DataFrame
                    df = pd.DataFrame(data_rows, columns=header)
                    
                except Exception as e:
                    logging.error(f"Manual CSV parsing also failed: {str(e)}")
                    raise ValueError(f"Cannot parse CSV file: {str(e)}")
            
            # 如果df仍然为空，抛出错误
            if df is None or df.empty:
                raise ValueError("No valid data found in CSV file")
            
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
            
            # 如果找到了采样率，添加到文件信息中
            if sampling_rate_found:
                self.file_info["Sampling Rate"] = f"{sampling_rate_found} Hz"
            
            # 清理列名（移除两端空格和特殊字符）
            df.columns = [col.strip() for col in df.columns]
            
            # 检查是否有时间相关的列（更广泛的检测）
            time_cols = []
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['time', 'date', '时间', '日期', 'index']):
                    time_cols.append(col)
            
            # 构建数据字典
            self.current_data = {}
            
            # 如果有时间相关列，尝试使用第一个作为时间轴
            time_column_used = None
            if time_cols:
                time_col = time_cols[0]
                try:
                    # 尝试转换为数值类型（对于time_index类型）
                    time_data = pd.to_numeric(df[time_col], errors='coerce')
                    if not time_data.isna().all():  # 如果成功转换为数值
                        self.current_data[time_col] = time_data.values
                        time_column_used = time_col
                        self.file_info["Time Column"] = time_col
                        logging.info(f"Using column '{time_col}' as time axis")
                except Exception as e:
                    logging.warning(f"Failed to process time column '{time_col}': {str(e)}")
            
            # 将所有数值列加载为数据通道
            data_channels_count = 0
            for col in df.columns:
                if col == time_column_used:
                    continue  # 已经处理过的时间列
                    
                try:
                    # 尝试转换为数值类型
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_data.isna().all():  # 如果有有效的数值数据
                        # 将NaN值替换为0
                        self.current_data[col] = numeric_data.fillna(0).values
                        data_channels_count += 1
                    else:
                        logging.warning(f"Column '{col}' contains no valid numeric data, skipping")
                except Exception as e:
                    logging.warning(f"Failed to process column '{col}': {str(e)}")
            
            # 检查是否有有效数据
            if data_channels_count == 0:
                raise ValueError("Cannot find any valid numeric data columns in CSV file")
            
            logging.info(f"Successfully loaded {data_channels_count} data channels from CSV file")
            if time_column_used:
                logging.info(f"Time column: {time_column_used}")
            
            # 添加加载的通道数到文件信息
            self.file_info["Data Channels Loaded"] = data_channels_count
                
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
    
    def process_data(self, operation, params=None, current_time_axis=None):
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
                                # **全新的简化trim逻辑**: 直接使用可视化组件提供的时间轴信息
                                start_time = params.get("start_time", 0)
                                end_time = params.get("end_time", 10.0)
                                
                                print(f"**TRIM_FIX**: Operation=trim, start_time={start_time}, end_time={end_time}")
                                print(f"**TRIM_FIX**: Channel={channel}, data_length={len(data)}")
                                
                                # **关键修复**: 使用与可视化完全一致的时间轴计算方式
                                if current_time_axis is not None and len(current_time_axis) == len(data):
                                    # 使用可视化组件提供的时间轴
                                    print(f"**TRIM_FIX**: Using visualizer time axis, range: {np.min(current_time_axis):.3f}s to {np.max(current_time_axis):.3f}s")
                                    
                                    # 直接在可视化时间轴上查找对应的索引
                                    start_indices = np.where(current_time_axis >= start_time)[0]
                                    end_indices = np.where(current_time_axis <= end_time)[0]
                                    
                                    if len(start_indices) == 0:
                                        raise ValueError(f"起始时间 {start_time}s 超出了可视化时间范围 [{np.min(current_time_axis):.3f}s, {np.max(current_time_axis):.3f}s]")
                                    if len(end_indices) == 0:
                                        raise ValueError(f"结束时间 {end_time}s 超出了可视化时间范围 [{np.min(current_time_axis):.3f}s, {np.max(current_time_axis):.3f}s]")
                                    
                                    start_sample = start_indices[0]
                                    end_sample = end_indices[-1] + 1  # +1 to include the end point
                                    
                                    if end_sample <= start_sample:
                                        raise ValueError(f"裁切范围无效：结束时间({end_time}s)必须大于起始时间({start_time}s)")
                                    
                                    # 裁切数据
                                    trimmed_data = data[start_sample:end_sample]
                                    processed_data[channel] = trimmed_data
                                    
                                    # **关键**: 如果是第一个处理的通道，也创建对应的裁切时间轴
                                    if channel == list(channels_to_process)[0] or channel == "Time":
                                        trimmed_time_axis = current_time_axis[start_sample:end_sample]
                                        processed_data["Time"] = trimmed_time_axis
                                        print(f"**TRIM_FIX**: Created trimmed time axis: {np.min(trimmed_time_axis):.3f}s to {np.max(trimmed_time_axis):.3f}s")
                                    
                                    print(f"**TRIM_FIX**: Channel {channel} trimmed from samples {start_sample} to {end_sample-1}, new shape: {trimmed_data.shape}")
                                    
                                elif channel == "Time" and time_data is not None:
                                    # 对于Time通道，如果没有可视化时间轴，则直接使用Time数据
                                    print(f"**TRIM_FIX**: Processing Time channel directly")
                                    
                                    start_indices = np.where(time_data >= start_time)[0]
                                    end_indices = np.where(time_data <= end_time)[0]
                                    
                                    if len(start_indices) == 0 or len(end_indices) == 0:
                                        raise ValueError(f"时间范围 [{start_time}s, {end_time}s] 超出数据范围")
                                    
                                    start_sample = start_indices[0]
                                    end_sample = end_indices[-1] + 1
                                    
                                    # 保存索引供其他通道使用
                                    time_start_sample = start_sample
                                    time_end_sample = end_sample
                                    
                                    trimmed_time_data = time_data[start_sample:end_sample]
                                    processed_data[channel] = trimmed_time_data
                                    
                                    print(f"**TRIM_FIX**: Time channel trimmed: {np.min(trimmed_time_data):.3f}s to {np.max(trimmed_time_data):.3f}s")
                                    
                                else:
                                    # 对于非Time通道，使用Time通道计算的索引或采样率计算
                                    if has_time_channel and 'time_start_sample' in locals() and 'time_end_sample' in locals():
                                        start_sample = time_start_sample
                                        end_sample = time_end_sample
                                        print(f"**TRIM_FIX**: Using time-based indices for channel {channel}")
                                    else:
                                        # 使用采样率计算（与可视化生成方式一致）
                                        start_sample = int(start_time * sampling_rate)
                                        end_sample = int(end_time * sampling_rate)
                                        print(f"**TRIM_FIX**: Using sampling rate calculation for channel {channel}")
                                        
                                        # 如果没有Time通道，创建时间轴
                                        if not has_time_channel and channel == list(self.current_data.keys())[0]:
                                            trimmed_time_axis = np.arange(start_sample, end_sample) / sampling_rate
                                            processed_data["Time"] = trimmed_time_axis
                                            print(f"**TRIM_FIX**: Created time axis: {np.min(trimmed_time_axis):.3f}s to {np.max(trimmed_time_axis):.3f}s")
                                    
                                    # 确保索引范围有效
                                    start_sample = max(0, min(start_sample, len(data) - 1))
                                    end_sample = max(start_sample + 1, min(end_sample, len(data)))
                                    
                                    trimmed_data = data[start_sample:end_sample]
                                    processed_data[channel] = trimmed_data
                                    
                                    print(f"**TRIM_FIX**: Channel {channel} processed, new shape: {trimmed_data.shape}")
                                    
                                # **重要**: 验证trim结果的一致性
                                if "Time" in processed_data:
                                    actual_start = np.min(processed_data["Time"])
                                    actual_end = np.max(processed_data["Time"])
                                    print(f"**TRIM_SUCCESS**: Final time range: {actual_start:.3f}s to {actual_end:.3f}s (requested: {start_time:.3f}s to {end_time:.3f}s)")
                            
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
                            
                            # NEW AC NOTCH FILTER IMPLEMENTATION
                            elif operation == "AC_Notch_Filter":
                                # Get parameters with defaults (60Hz US standard)
                                power_freq = params.get("power_frequency", 60)  # 60Hz (US) or 50Hz (China)
                                quality_factor = params.get("quality_factor", 30)  # Q factor for notch width
                                remove_harmonics = params.get("remove_harmonics", True)  # Remove harmonic frequencies
                                max_harmonic = params.get("max_harmonic", 5)  # Up to 5th harmonic
                                
                                # Skip time channel
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    try:
                                        # Create list of frequencies to remove
                                        frequencies_to_notch = [power_freq]
                                        
                                        # Add harmonics if requested
                                        if remove_harmonics:
                                            nyquist_freq = sampling_rate / 2
                                            for harmonic in range(2, max_harmonic + 1):
                                                harmonic_freq = power_freq * harmonic
                                                # Only add if below 95% of Nyquist frequency
                                                if harmonic_freq < nyquist_freq * 0.95:
                                                    frequencies_to_notch.append(harmonic_freq)
                                        
                                        # Apply notch filters sequentially
                                        filtered_data = data.copy().astype(np.float64)
                                        
                                        for freq in frequencies_to_notch:
                                            # Design IIR notch filter
                                            b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                            # Apply zero-phase filtering to avoid phase distortion
                                            filtered_data = signal.filtfilt(b, a, filtered_data)
                                        
                                        processed_data[channel] = filtered_data
                                        
                                        # Print applied frequencies for verification
                                        print(f"AC Notch Filter applied to {channel}: removed frequencies {frequencies_to_notch} Hz")
                                        
                                    except Exception as e:
                                        return False, None, f"AC notch filter error: {str(e)}"
                            
                            elif operation == "陷波滤波":
                                # 获取陷波频率和参数
                                notch_freq = params.get("notch_freq", 50)  # 默认50Hz（中国）
                                quality_factor = params.get("quality_factor", 30)  # Q值，控制陷波宽度
                                remove_harmonics = params.get("remove_harmonics", True)  # 是否移除谐波
                                max_harmonic = params.get("max_harmonic", 5)  # 最大谐波次数
                                
                                # 特殊处理Time通道 - 不对时间通道应用滤波
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    try:
                                        # 创建待滤除的频率列表
                                        frequencies_to_remove = [notch_freq]
                                        
                                        if remove_harmonics:
                                            # 添加谐波频率
                                            for harmonic in range(2, max_harmonic + 1):
                                                harmonic_freq = notch_freq * harmonic
                                                # 确保谐波频率小于奈奎斯特频率
                                                nyquist = sampling_rate / 2
                                                if harmonic_freq < nyquist * 0.95:  # 留5%余量
                                                    frequencies_to_remove.append(harmonic_freq)
                                        
                                        # 应用陷波滤波器
                                        filtered_data = data.copy()
                                        for freq in frequencies_to_remove:
                                            # 设计陷波滤波器
                                            b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                            # 应用滤波器（使用filtfilt以避免相位延迟）
                                            filtered_data = signal.filtfilt(b, a, filtered_data)
                                        
                                        processed_data[channel] = filtered_data
                                        
                                    except Exception as e:
                                        return False, None, f"陷波滤波器设计错误: {str(e)}"
                            
                            elif operation == "交流电去噪":
                                # 简化的交流电去噪接口（自动选择参数）
                                region = params.get("region", "中国")  # "中国" 或 "美国"
                                strength = params.get("strength", "标准")  # "轻度", "标准", "强力"
                                
                                # 根据地区设置基频
                                if region == "中国":
                                    base_freq = 50
                                elif region == "美国":
                                    base_freq = 60
                                else:
                                    base_freq = params.get("custom_freq", 50)
                                
                                # 根据强度设置参数
                                if strength == "轻度":
                                    quality_factor = 15  # 较宽的陷波
                                    max_harmonic = 3
                                elif strength == "标准":
                                    quality_factor = 30  # 中等宽度
                                    max_harmonic = 5
                                elif strength == "强力":
                                    quality_factor = 50  # 较窄但更深的陷波
                                    max_harmonic = 7
                                else:
                                    quality_factor = 30
                                    max_harmonic = 5
                                
                                # 特殊处理Time通道
                                if channel == "Time":
                                    processed_data[channel] = data.copy()
                                else:
                                    try:
                                        # 创建待滤除的频率列表（基频+谐波）
                                        frequencies_to_remove = [base_freq]
                                        
                                        for harmonic in range(2, max_harmonic + 1):
                                            harmonic_freq = base_freq * harmonic
                                            # 确保谐波频率小于奈奎斯特频率
                                            nyquist = sampling_rate / 2
                                            if harmonic_freq < nyquist * 0.95:
                                                frequencies_to_remove.append(harmonic_freq)
                                        
                                        # 应用陷波滤波器组
                                        filtered_data = data.copy()
                                        for freq in frequencies_to_remove:
                                            b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                            filtered_data = signal.filtfilt(b, a, filtered_data)
                                        
                                        processed_data[channel] = filtered_data
                                        
                                        print(f"交流电去噪应用于通道 {channel}: 移除频率 {frequencies_to_remove} Hz")
                                        
                                    except Exception as e:
                                        return False, None, f"交流电去噪错误: {str(e)}"
                            
                            else:
                                processed_data[channel] = data.copy()
                        else:
                            processed_data[channel] = data
                    else:
                        # 对于未选中的通道，直接保持原样
                        processed_data[channel] = self.current_data[channel]

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
                        
                        try:
                            # Design the filter
                            b, a = signal.butter(4, cutoff_norm, 'low')
                            
                            # Apply the filter
                            if data.ndim == 1:
                                processed_data = signal.filtfilt(b, a, data)
                            else:
                                # For multi-channel data
                                processed_data = np.zeros_like(data)
                                for i in range(data.shape[1]):
                                    processed_data[:, i] = signal.filtfilt(b, a, data[:, i])
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
                        
                        try:
                            # Design the filter
                            b, a = signal.butter(4, cutoff_norm, 'high')
                            
                            # Apply the filter
                            if data.ndim == 1:
                                processed_data = signal.filtfilt(b, a, data)
                            else:
                                # For multi-channel data
                                processed_data = np.zeros_like(data)
                                for i in range(data.shape[1]):
                                    processed_data[:, i] = signal.filtfilt(b, a, data[:, i])
                        except Exception as e:
                            return False, None, f"Filter design error: {str(e)}"
                    
                    # NEW AC NOTCH FILTER FOR NUMPY ARRAYS
                    elif operation == "AC_Notch_Filter":
                        # Get parameters with defaults (60Hz US standard)
                        power_freq = params.get("power_frequency", 60)  # 60Hz (US) or 50Hz (China)
                        quality_factor = params.get("quality_factor", 30)  # Q factor for notch width
                        remove_harmonics = params.get("remove_harmonics", True)  # Remove harmonic frequencies
                        max_harmonic = params.get("max_harmonic", 5)  # Up to 5th harmonic
                        
                        try:
                            # Create list of frequencies to remove
                            frequencies_to_notch = [power_freq]
                            
                            # Add harmonics if requested
                            if remove_harmonics:
                                nyquist_freq = sampling_rate / 2
                                for harmonic in range(2, max_harmonic + 1):
                                    harmonic_freq = power_freq * harmonic
                                    # Only add if below 95% of Nyquist frequency
                                    if harmonic_freq < nyquist_freq * 0.95:
                                        frequencies_to_notch.append(harmonic_freq)
                            
                            # Apply notch filters
                            if data.ndim == 1:
                                # Single channel data
                                filtered_data = data.copy().astype(np.float64)
                                for freq in frequencies_to_notch:
                                    b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                    filtered_data = signal.filtfilt(b, a, filtered_data)
                                processed_data = filtered_data
                            else:
                                # Multi-channel data
                                processed_data = np.zeros_like(data, dtype=np.float64)
                                for i in range(data.shape[1]):
                                    filtered_data = data[:, i].copy().astype(np.float64)
                                    for freq in frequencies_to_notch:
                                        b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                        filtered_data = signal.filtfilt(b, a, filtered_data)
                                    processed_data[:, i] = filtered_data
                            
                            # Print applied frequencies for verification
                            print(f"AC Notch Filter applied: removed frequencies {frequencies_to_notch} Hz")
                            
                        except Exception as e:
                            return False, None, f"AC notch filter error: {str(e)}"
                    
                    elif operation == "陷波滤波":
                        # 获取陷波参数
                        notch_freq = params.get("notch_freq", 50)  # 默认50Hz
                        quality_factor = params.get("quality_factor", 30)
                        remove_harmonics = params.get("remove_harmonics", True)
                        max_harmonic = params.get("max_harmonic", 5)
                        
                        try:
                            # 创建待滤除的频率列表
                            frequencies_to_remove = [notch_freq]
                            
                            if remove_harmonics:
                                for harmonic in range(2, max_harmonic + 1):
                                    harmonic_freq = notch_freq * harmonic
                                    nyquist = sampling_rate / 2
                                    if harmonic_freq < nyquist * 0.95:
                                        frequencies_to_remove.append(harmonic_freq)
                            
                            # 应用陷波滤波器
                            if data.ndim == 1:
                                filtered_data = data.copy()
                                for freq in frequencies_to_remove:
                                    b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                    filtered_data = signal.filtfilt(b, a, filtered_data)
                                processed_data = filtered_data
                            else:
                                # 对多通道数据
                                processed_data = np.zeros_like(data)
                                for i in range(data.shape[1]):
                                    filtered_data = data[:, i].copy()
                                    for freq in frequencies_to_remove:
                                        b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                        filtered_data = signal.filtfilt(b, a, filtered_data)
                                    processed_data[:, i] = filtered_data
                        except Exception as e:
                            return False, None, f"陷波滤波器设计错误: {str(e)}"
                    
                    elif operation == "交流电去噪":
                        # 简化的交流电去噪
                        region = params.get("region", "中国")
                        strength = params.get("strength", "标准")
                        
                        # 设置基频
                        if region == "中国":
                            base_freq = 50
                        elif region == "美国":
                            base_freq = 60
                        else:
                            base_freq = params.get("custom_freq", 50)
                        
                        # 设置参数
                        if strength == "轻度":
                            quality_factor = 15
                            max_harmonic = 3
                        elif strength == "标准":
                            quality_factor = 30
                            max_harmonic = 5
                        elif strength == "强力":
                            quality_factor = 50
                            max_harmonic = 7
                        else:
                            quality_factor = 30
                            max_harmonic = 5
                        
                        try:
                            # 创建频率列表
                            frequencies_to_remove = [base_freq]
                            for harmonic in range(2, max_harmonic + 1):
                                harmonic_freq = base_freq * harmonic
                                nyquist = sampling_rate / 2
                                if harmonic_freq < nyquist * 0.95:
                                    frequencies_to_remove.append(harmonic_freq)
                            
                            # 应用滤波器
                            if data.ndim == 1:
                                filtered_data = data.copy()
                                for freq in frequencies_to_remove:
                                    b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                    filtered_data = signal.filtfilt(b, a, filtered_data)
                                processed_data = filtered_data
                            else:
                                processed_data = np.zeros_like(data)
                                for i in range(data.shape[1]):
                                    filtered_data = data[:, i].copy()
                                    for freq in frequencies_to_remove:
                                        b, a = signal.iirnotch(freq, quality_factor, sampling_rate)
                                        filtered_data = signal.filtfilt(b, a, filtered_data)
                                    processed_data[:, i] = filtered_data
                            
                            print(f"交流电去噪应用: 移除频率 {frequencies_to_remove} Hz")
                        except Exception as e:
                            return False, None, f"交流电去噪错误: {str(e)}"
                    
                    else:
                        processed_data = data.copy()

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
            
            # **修复trim操作的返回信息**
            if operation == "裁切" and "Time" in processed_data:
                time_data = processed_data["Time"]
                if len(time_data) > 0:
                    actual_start = np.min(time_data)
                    actual_end = np.max(time_data)
                    return True, processed_data, f"裁切成功: 时间范围 {actual_start:.3f}s - {actual_end:.3f}s (数据点: {len(time_data)})"
            
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