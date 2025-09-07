#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the modified histogram interface
"""

import sys
import numpy as np
from PyQt6.QtWidgets import QApplication
from gui.components.histogram.histogram_dialog import HistogramDialog

def create_test_data():
    """创建测试数据"""
    # 生成一些示例数据
    np.random.seed(42)
    t = np.linspace(0, 10, 10000)  # 10秒，10000个点
    
    # 生成包含噪声的信号
    signal = (2 * np.sin(2 * np.pi * 5 * t) + 
              1.5 * np.sin(2 * np.pi * 10 * t) + 
              0.5 * np.random.randn(len(t)))
    
    return signal, 1000.0  # 信号和采样率

def test_histogram_interface():
    """测试直方图界面"""
    app = QApplication(sys.argv)
    
    # 创建测试数据
    test_data, sampling_rate = create_test_data()
    
    # 创建直方图对话框
    histogram_dialog = HistogramDialog()
    
    # 设置测试数据
    histogram_dialog.set_data(test_data, sampling_rate)
    
    # 显示对话框
    histogram_dialog.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    test_histogram_interface()
