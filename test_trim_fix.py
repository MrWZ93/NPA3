#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试trim功能修复的脚本
"""

import numpy as np
import sys
import os

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.data_processor import FileDataProcessor

def test_trim_function():
    """测试trim功能是否正确工作"""
    print("=== 测试trim功能修复 ===")
    
    # 创建测试数据
    print("\n1. 创建测试数据...")
    
    # 模拟多通道数据
    time_axis = np.linspace(0, 10, 1000)  # 10秒，1000个点
    channel1_data = np.sin(2 * np.pi * 1 * time_axis)  # 1Hz正弦波
    channel2_data = np.cos(2 * np.pi * 2 * time_axis)  # 2Hz余弦波
    
    # 创建数据字典（包含Time通道）
    test_data_with_time = {
        "Time": time_axis,
        "Channel1": channel1_data,
        "Channel2": channel2_data
    }
    
    # 创建数据字典（不包含Time通道）
    test_data_no_time = {
        "Channel1": channel1_data,
        "Channel2": channel2_data
    }
    
    print(f"   原始数据通道: {list(test_data_with_time.keys())}")
    print(f"   每个通道长度: {len(time_axis)}")
    print(f"   时间范围: {time_axis[0]:.2f}s 到 {time_axis[-1]:.2f}s")
    
    # 创建数据处理器
    processor = FileDataProcessor()
    processor.current_data = test_data_with_time
    processor.sampling_rate = 100.0  # 100 Hz
    
    print("\n2. 测试带Time通道的数据...")
    
    # 测试trim操作（截取3-7秒的数据）
    trim_params = {
        "start_time": 3.0,
        "end_time": 7.0,
        "sampling_rate": 100.0
    }
    
    success, processed_data, message = processor.process_data("裁切", trim_params, time_axis)
    
    if success:
        print("   ✓ Trim操作成功")
        print(f"   处理后通道: {list(processed_data.keys())}")
        
        # 检查是否有额外的"time"通道
        has_extra_time = any("time" in str(k).lower() and k != "Time" for k in processed_data.keys())
        if has_extra_time:
            print("   ✗ 发现额外的time通道！")
        else:
            print("   ✓ 没有额外的time通道")
        
        # 检查原始通道是否被替换
        for channel in ["Time", "Channel1", "Channel2"]:
            if channel in processed_data:
                data_length = len(processed_data[channel])
                print(f"   {channel}: 长度 = {data_length}")
                
                # 检查数据内容是否正确
                if channel == "Time":
                    time_range = f"{processed_data[channel][0]:.2f}s 到 {processed_data[channel][-1]:.2f}s"
                    print(f"     时间范围: {time_range}")
                elif channel == "Channel1":
                    # 检查是否为正弦波数据而不是时间轴数据
                    is_sine_like = np.abs(np.mean(processed_data[channel])) < 0.1  # 正弦波均值应该接近0
                    if is_sine_like:
                        print("     ✓ Channel1数据正确（正弦波特征）")
                    else:
                        print("     ✗ Channel1数据可能被替换！")
    else:
        print(f"   ✗ Trim操作失败: {message}")
    
    print("\n3. 测试不带Time通道的数据...")
    
    # 测试不带Time通道的数据
    processor.current_data = test_data_no_time
    success2, processed_data2, message2 = processor.process_data("裁切", trim_params, time_axis)
    
    if success2:
        print("   ✓ 无Time通道trim操作成功")
        print(f"   处理后通道: {list(processed_data2.keys())}")
        
        # 检查是否自动添加了time通道
        has_auto_time = "Time" in processed_data2 or any("time" in str(k).lower() for k in processed_data2.keys())
        if has_auto_time:
            print("   ✗ 自动添加了time通道！")
        else:
            print("   ✓ 没有自动添加time通道")
        
        # 检查原始通道数据
        for channel in ["Channel1", "Channel2"]:
            if channel in processed_data2:
                data_length = len(processed_data2[channel])
                print(f"   {channel}: 长度 = {data_length}")
    else:
        print(f"   ✗ 无Time通道trim操作失败: {message2}")
    
    print("\n4. 测试选择特定通道处理...")
    
    # 测试只处理Channel1
    trim_params_single = {
        "start_time": 3.0,
        "end_time": 7.0,
        "sampling_rate": 100.0,
        "channel": "Channel1"
    }
    
    processor.current_data = test_data_with_time
    success3, processed_data3, message3 = processor.process_data("裁切", trim_params_single, time_axis)
    
    if success3:
        print("   ✓ 单通道trim操作成功")
        print(f"   处理后通道: {list(processed_data3.keys())}")
        
        # 检查Channel1是否被正确处理，Channel2是否保持不变
        if "Channel1" in processed_data3 and "Channel2" in processed_data3:
            ch1_len = len(processed_data3["Channel1"])
            ch2_len = len(processed_data3["Channel2"])
            print(f"   Channel1长度: {ch1_len} (应该被裁切)")
            print(f"   Channel2长度: {ch2_len} (应该保持原始长度)")
            
            if ch1_len < ch2_len:
                print("   ✓ 选择性通道处理正确")
            else:
                print("   ✗ 选择性通道处理可能有问题")
    else:
        print(f"   ✗ 单通道trim操作失败: {message3}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_trim_function()
