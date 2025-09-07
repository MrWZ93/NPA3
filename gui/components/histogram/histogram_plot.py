#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histogram Plot - 直方图绘图组件 (重构版)
现在作为模块入口，导入重构后的组件
"""

# 导入重构后的组件
from .plot_coordinator import HistogramPlot
from .fitting_manager import FitDataManager

# 为了向后兼容，保持原有的导入接口
__all__ = ['HistogramPlot', 'FitDataManager']

# 原有的HistogramPlot类现在从plot_coordinator导入
# FitDataManager从fitting_manager导入

# 这里可以添加一些兼容性代码，如果需要的话
