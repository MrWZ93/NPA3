#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时测试脚本：验证示波器CSV文件加载功能
"""

import os
import sys
import numpy as np

# 添加项目根目录到路径，以便导入模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入需要测试的模块
from core.load_oscilloscope_csv import load_oscilloscope_csv

# 测试文件路径
test_file = os.path.join(os.path.expanduser("~"), "Desktop", "Data", "test_oscilloscope.csv")

print(f"Testing oscilloscope CSV loader with file: {test_file}")

# 尝试加载CSV文件
try:
    data_dict, file_info, sampling_rate = load_oscilloscope_csv(test_file)
    
    if data_dict is not None:
        print("\n=== SUCCESS ===")
        print(f"Successfully loaded file: {test_file}")
        print(f"File info: {file_info}")
        print(f"Sampling rate: {sampling_rate}")
        print("\nChannels found:")
        for channel_name, data in data_dict.items():
            if channel_name != "Time":
                print(f"  - {channel_name}: {len(data)} points, range: {min(data)} to {max(data)}")
    else:
        print("\n=== FAILURE ===")
        print("Failed to load file - returned None")
except Exception as e:
    print("\n=== ERROR ===")
    print(f"Exception occurred: {str(e)}")
    import traceback
    traceback.print_exc()
