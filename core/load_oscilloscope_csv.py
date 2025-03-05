#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版示波器CSV文件加载模块

修复日期: 2025-03-02
修复内容: 
1. 改进数据起始行检测逻辑
2. 优化通道名称处理，正确区分元数据和数据通道
3. 增加数据验证功能
4. 移除不兼容的pandas设置
"""

import numpy as np
import pandas as pd
import os
from datetime import datetime
import traceback

def self_validation(data_dict, data_shape, time_column):
    """
    验证数据字典是否合理并输出详细信息
    """
    try:
        print("\n=== 数据验证 ====")
        
        # 验证数据字典
        if not isinstance(data_dict, dict):
            print("\u9519\u8bef: 数据字典类型错误")
            return False
            
        # 检查数据字典
        channel_count = len(data_dict) - (1 if "Time" in data_dict else 0)  # 减去Time列
        print(f"\u6570据通道数量: {channel_count}")
        print(f"\u5404通道名称: {list(data_dict.keys())}")
        
        # 检查数据大小
        print(f"\u539f始数据形状: {data_shape}")
        
        # 检查时间列
        if len(time_column) > 0:
            try:
                print(f"\u65f6间列长度: {len(time_column)}")
                print(f"\u65f6间列范围: {np.min(time_column):.6f} 到 {np.max(time_column):.6f}")
                # 检查时间是否单调递增
                if len(time_column) > 1:
                    is_monotonic = np.all(np.diff(time_column) >= 0)
                    print(f"\u65f6间列是否单调递增: {is_monotonic}")
                    if not is_monotonic:
                        print("\u8b66\u544a: 时间列不是单调递增的")
            except Exception as e:
                print(f"\u8b66\u544a: 时间列分析错误: {str(e)}")
        else:
            print("\u8b66\u544a: 时间列为空")
        
        # 检查每个数据通道
        valid_channels = 0
        for channel, data in data_dict.items():
            if channel != "Time":
                try:
                    if len(data) > 0:
                        print(f"\u901a道 {channel}: \u957f度={len(data)}, \u8303\u56f4={np.min(data):.6f} 到 {np.max(data):.6f}")
                        valid_channels += 1
                    else:
                        print(f"\u8b66\u544a: 通道 {channel} 数据为空")
                except Exception as e:
                    print(f"\u8b66\u544a: 通道 {channel} 数据分析错误: {str(e)}")
        
        # 检查是否有有效通道
        if valid_channels == 0:
            print("\u9519\u8bef: 没有有效的数据通道")
            return False
            
        print("=== 验证完成 ===\n")
        return valid_channels > 0 and len(time_column) > 0
        
    except Exception as e:
        print(f"\u9a8c证过程发生错误: {str(e)}")
        return False

def load_oscilloscope_csv(file_path, force_time_from_zero=False):
    """
    加载示波器格式的CSV文件
    返回：数据字典, 文件信息字典, 采样率
    """
    # 初始化变量
    old_options = None
    old_workers = None
    
    def is_numeric(value):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    try:
        # 设置pandas选项
        old_options = pd.options.mode.chained_assignment
        pd.options.mode.chained_assignment = None
        
        # 移除不兼容的线程设置
        old_workers = None
        
        # 读取文件
        with open(file_path, 'r', errors='replace') as f:
            lines = f.readlines()
        
        if not lines:
            raise ValueError("Empty file")
        
        # 更宽松的示波器格式检测
        is_oscilloscope = False
        for i in range(min(10, len(lines))):
            if any(keyword in lines[i] for keyword in ["Model", "BlockNumber", "TraceName", "Xviewer", "HResolution"]):
                is_oscilloscope = True
                break
                
        if not is_oscilloscope:
            return None, None, None
            
        print("CSV file header:")
        for i in range(min(15, len(lines))):
            print(f"Line {i}: {lines[i].strip()}")
        
        # 解析元数据
        metadata = {}
        data_start_line = -1
        h_resolution = None
        h_offset = None
        
        # 第一遍：收集元数据并查找数据起始行
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            parts = [p.strip() for p in line.split(',')]
            
            # 检测数据开始行 - 多种方法
            # 方法1: 以逗号开头且后面有数字
            if line.startswith(',') and any(p.strip() and (p.strip()[0].isdigit() or p.strip()[0] == '-' or p.strip()[0] == '.') for p in parts[1:]):
                data_start_line = i
                print(f"Found data start at line {i} (method 1)")
                break
            
            # 方法2: HUnit行后就是数据
            if i > 0 and "HUnit" in lines[i-1]:
                data_start_line = i
                print(f"Found data start at line {i} (method 2)")
                break
                
            # 方法3: 首列为空，后面有数字或负数
            if parts[0] == '' and len(parts) > 1 and any(p.strip() and (p.strip()[0].isdigit() or p.strip()[0] == '-' or p.strip()[0] == '.') for p in parts[1:]):
                data_start_line = i
                print(f"Found data start at line {i} (method 3)")
                break
            
            # 解析元数据
            if len(parts) >= 2 and parts[0] and not parts[0].startswith(','):
                key = parts[0].strip('"')
                # 增强版元数据解析，处理空值
                values = []
                for p in parts[1:]:
                    p_str = p.strip()
                    if p_str:  # 只添加非空值
                        # 移除可能的引号
                        if p_str.startswith('"') and p_str.endswith('"'):
                            p_str = p_str[1:-1]
                        elif p_str.startswith('"'):
                            p_str = p_str[1:]
                        elif p_str.endswith('"'):
                            p_str = p_str[:-1]
                        values.append(p_str)
                
                # 调试输出
                print(f"Metadata: {key} = {values}")
                
                # 处理特殊字段
                if key == "HResolution" and values:
                    try:
                        h_resolution = float(values[0])
                    except:
                        pass
                        
                elif key == "HOffset" and values:
                    try:
                        h_offset = float(values[0])
                    except:
                        pass
                
                # 保存所有元数据
                if values:
                    metadata[key] = values[0] if len(values) == 1 else values
        
        # 如果第一次扫描没找到数据起始行，尝试其他方法
        if data_start_line == -1:
            # 查找空列开头、数字内容的行（包括负数和小数点开头）
            for i, line in enumerate(lines):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) > 1 and parts[0] == '' and len([p for p in parts[1:] if p and (p[0].isdigit() or p[0] == '-' or p[0] == '.')]) > 0:
                    data_start_line = i
                    print(f"Found data start at line {i} (method 4)")
                    break
            
            # 特别检查HUnit行后的行作为数据起始
            if data_start_line == -1:
                for i, line in enumerate(lines):
                    if "HUnit" in line and i+1 < len(lines):
                        data_start_line = i+1
                        print(f"Found data start at line {i+1} (method 5 - after HUnit)")
                        break
                    
        # 如果仍然找不到，选择默认行
        if data_start_line == -1:
            # 查找可能的候选行
            candidates = []
            for i, line in enumerate(lines[5:30]):  # 通常数据在5-30行之后开始
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    # 第一列为空，后续列有数值的可能性很高是数据行
                    if parts[0] == '' and any(p and (p[0].isdigit() or p[0] == '-' or p[0] == '.') for p in parts[1:]):
                        candidates.append((i + 5, 100))  # 给予较高权重
                    else:
                        numeric_count = sum(1 for p in parts if p and (p[0].isdigit() or p[0] == '-' or p[0] == '.'))
                        if numeric_count >= 1:  # 只要有数字列就考虑
                            candidates.append((i + 5, numeric_count))
            
            if candidates:
                # 选择数字列最多的行
                data_start_line = max(candidates, key=lambda x: x[1])[0]
                print(f"Defaulted data start to line {data_start_line} (best candidate)")
            else:
                # 最后的默认选择 - 查看常见的数据起始行
                common_starts = [9, 10, 11, 12]  # 常见数据起始行
                for line_num in common_starts:
                    if line_num < len(lines):
                        parts = [p.strip() for p in lines[line_num].split(',')]
                        if len(parts) > 1 and (parts[0] == '' or is_numeric(parts[0])):
                            data_start_line = line_num
                            print(f"Defaulted data start to common line {data_start_line}")
                            break
                
                # 如果仍未找到，使用固定值
                if data_start_line == -1:
                    data_start_line = 10
                    print(f"Defaulted data start to line {data_start_line} (fixed default)")
        
        # 确定通道数量
        trace_names = []
        if "TraceName" in metadata:
            if isinstance(metadata["TraceName"], list):
                # 过滤掉空字符串或None
                trace_names = [name for name in metadata["TraceName"] if name]
            else:
                trace_names = [metadata["TraceName"]]
            
            print(f"Found trace names in metadata: {trace_names}")
            
            # 调试输出而不改变原始数据
            channels_count = len([col for col in trace_names if col]) # 有效通道数
            print(f"CSV数据节梳分析: 共{channels_count}个通道")
                
        # 计算采样率
        sampling_rate = 1.0 / h_resolution if h_resolution and h_resolution != 0 else 1.0
        
        # 处理数据部分
        data_lines = lines[data_start_line:]
        data_values = []
        
        print(f"Data section starts at line {data_start_line}, file has {len(lines)} lines total")
        
        # 处理数据行
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            
            # 如果行以逗号开始，去掉开头的逗号（确保数据正确对齐）
            if line.startswith(','):
                line = line[1:]
            
            values = [v.strip() for v in line.split(',')]
            if not values:
                continue
                
            # 转换为数值
            numeric_values = []
            for v in values:
                if not v:
                    numeric_values.append(np.nan)
                else:
                    try:
                        numeric_values.append(float(v))
                    except ValueError:
                        numeric_values.append(np.nan)
            
            if len(numeric_values) >= 2:  # 至少要有两列数据（时间和一个通道）
                data_values.append(numeric_values)
        
        # 检查解析结果
        if not data_values:
            raise ValueError("No valid data found in file")
            
        print(f"First few data values: {data_values[:5]}")
        
        # 转换为numpy数组
        data_array = np.array(data_values)
        print(f"Data array shape: {data_array.shape}")
        
        # 检查数据形状
        if data_array.shape[1] < 2:
            raise ValueError(f"Invalid data format: Found only {data_array.shape[1]} columns, expected at least 2")
        
        # 检查并清理NaN值
        nan_count = np.isnan(data_array).sum()
        if nan_count > 0:
            print(f"Warning: Found {nan_count} NaN values in data")
            data_array = np.nan_to_num(data_array, nan=0.0)
        
        # 提取数据：第一列是时间，其余是通道数据
        print(f"\n>>> 数据形状检查 <<< ")
        print(f"Data array shape: {data_array.shape}")
        
        # 检查数据列数是否与预期匹配
        if data_array.shape[1] >= 2:  # 至少需要两列（时间和一个通道）
            # CSV数据处理特殊情况：第一列应该是时间，但在这个格式中第一列为空
            # 生成时间列并提取实际数据通道
            if h_resolution is not None and h_resolution > 0:
                print(f"Creating time column with h_resolution={h_resolution}, h_offset={h_offset}")
                # 使用h_resolution和h_offset生成精确的时间轴
                time_column = np.arange(0, len(data_array) * h_resolution, h_resolution)
                # 应用HOffset偏移
                if h_offset is not None:
                    time_column = time_column + h_offset
                
                # 如果需要强制时间轴从0开始
                if force_time_from_zero and len(time_column) > 0:
                    min_time = np.min(time_column)
                    if min_time < 0:
                        print(f"Adjusting time axis: shifting by {min_time} to start from 0")
                        time_column = time_column - min_time
            else:
                print("Warning: Invalid h_resolution, using default time column")
                time_column = np.arange(len(data_array)) * 0.0001  # 默认采样间隔
            
            # 提取实际数据通道 - 去掉第一列空值
            if data_array.shape[1] > 1 and np.isnan(data_array[:, 0]).all():
                print("First column is empty, using from column 1")
                channels_data = data_array[:, 1:]
            else:
                channels_data = data_array
                
            print(f"Detected {channels_data.shape[1]} data columns (excluding time column)")
        else:
            # 如果只有一列，假设是一个时间序列，创建一个虚拟的时间列
            print("Warning: Only one data column detected, assuming it's a channel")
            channels_data = data_array
            time_column = np.arange(len(data_array))
            
        print(f"Time column shape: {time_column.shape}")
        print(f"Channels data shape: {channels_data.shape}")
        
        # 创建数据字典
        data_dict = {}
        
        # 检查通道名称（保证使用TraceName字段的值）
        valid_trace_names = []
        if trace_names:
            # 过滤掉不应该被作为通道的名称（如Model和Xviewer）
            valid_trace_names = [name for name in trace_names if name not in ["Model", "Xviewer", "", "BlockNumber"] and name]
            print(f"Identified valid channel names: {valid_trace_names}")
        
        # 检查通道数量与数据列数是否匹配
        if len(valid_trace_names) != channels_data.shape[1]:
            print(f"Warning: Number of channel names ({len(valid_trace_names)}) does not match data columns ({channels_data.shape[1]})")
            # 如果通道名称数量不匹配，重新生成通道名称
            if channels_data.shape[1] > 0:
                valid_trace_names = [f"Channel {i+1}" for i in range(channels_data.shape[1])]
                print(f"Created default channel names: {valid_trace_names}")
        
        # 使用有效的通道名称
        print("\n>>> 分配通道数据 <<< ")
        print(f"Channel data columns: {channels_data.shape[1]}")
        print(f"Valid channel names: {valid_trace_names}")
        
        # 确保有名称可用
        if not valid_trace_names and channels_data.shape[1] > 0:
            valid_trace_names = [f"Channel {i+1}" for i in range(channels_data.shape[1])]
            print(f"No valid names found, created default names: {valid_trace_names}")
            
        # 分配通道数据
        for i in range(min(channels_data.shape[1], len(valid_trace_names))):
            channel_name = valid_trace_names[i]
            print(f"Mapping data column {i} to channel '{channel_name}'")
            data_dict[channel_name] = channels_data[:, i]
            
        # 如果还有未命名的通道，给它们分配默认名称
        for i in range(len(valid_trace_names), channels_data.shape[1]):
            channel_name = f"Channel {i+1}"
            print(f"Mapping extra data column {i} to default channel '{channel_name}'")
            data_dict[channel_name] = channels_data[:, i]
        
        # 验证数据是否有效
        self_validation(data_dict, channels_data.shape, time_column)
        
        # 添加时间列
        data_dict["Time"] = time_column
        
        # 准备文件信息
        file_info = {
            "File Type": "Oscilloscope CSV",
            "File Path": file_path,
            "File Size": f"{os.path.getsize(file_path) / (1024*1024):.2f} MB",
            "Modified Time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
            "Channels": len(trace_names) if trace_names else channels_data.shape[1],
            "Sample Points": len(time_column),
            "Sampling Rate": f"{sampling_rate:.1f} Hz"
        }
        
        # 添加额外元数据
        for key, value in metadata.items():
            if key not in file_info and key not in ["Model", "Xviewer"]:
                file_info[key] = value
        
        # 显示成功信息
        print(f"Successfully loaded CSV file with {channels_data.shape[1]} channels and {len(time_column)} data points")
        return data_dict, file_info, sampling_rate
        
    except Exception as e:
        # 如果处理错误，返回None以让普通CSV加载器处理
        print(f"Error processing oscilloscope CSV: {str(e)}")
        traceback.print_exc()
        return None, None, None
        
    finally:
        # 恢复设置
        if old_options is not None:
            pd.options.mode.chained_assignment = old_options
