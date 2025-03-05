#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试CSV加载问题的独立脚本
"""

import os
import sys
import numpy as np
import time

# 设置输出格式
def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

# 主函数
def main():
    print_header("CSV文件加载调试脚本")
    
    # 导入示波器CSV加载模块
    print("导入模块...")
    try:
        from core.load_oscilloscope_csv import load_oscilloscope_csv
        print("已成功导入load_oscilloscope_csv模块")
    except ImportError as e:
        print(f"错误: 无法导入load_oscilloscope_csv模块 - {str(e)}")
        return
    
    # 指定测试文件
    test_file = os.path.join(os.path.expanduser("~"), "Desktop", "Data", "test_oscilloscope.csv")
    print(f"测试文件路径: {test_file}")
    
    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在 - {test_file}")
        return
    
    print(f"文件大小: {os.path.getsize(test_file) / 1024:.2f} KB")
    
    # 尝试加载文件
    print_header("开始尝试加载CSV文件")
    print("调用load_oscilloscope_csv...")
    
    start_time = time.time()
    try:
        data_dict, file_info, sampling_rate = load_oscilloscope_csv(test_file)
        elapsed_time = time.time() - start_time
        
        if data_dict is None or file_info is None:
            print(f"加载失败 - 返回了None (耗时: {elapsed_time:.2f}秒)")
            return
        
        print(f"加载成功! (耗时: {elapsed_time:.2f}秒)")
        
        print_header("文件信息")
        for key, value in file_info.items():
            print(f"{key}: {value}")
        
        print_header("数据信息")
        print(f"采样率: {sampling_rate} Hz")
        print(f"通道数量: {len([ch for ch in data_dict.keys() if ch != 'Time'])}")
        print(f"数据点数: {len(next(iter(data_dict.values())))}")
        
        print_header("通道详情")
        for channel, data in data_dict.items():
            print(f"通道: {channel}")
            print(f"  - 类型: {type(data)}")
            print(f"  - 形状: {data.shape}")
            print(f"  - 范围: {np.min(data)} 到 {np.max(data)}")
            print(f"  - 前5个值: {data[:5]}")
            print()
        
        print_header("测试成功!")
        return True
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"发生错误 (耗时: {elapsed_time:.2f}秒): {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
