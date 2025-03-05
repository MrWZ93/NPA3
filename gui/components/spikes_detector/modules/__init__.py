"""
Spikes Detector Modules - 峰值检测器模块包
用于检测和分析时间序列数据中的峰值(spikes)
"""

# 导入主要模块，方便从包直接导入
from .spike_plot import SpikesDataPlot
from .auto_detector import PeakDetectionWorker, PeakDurationWorker, AutoSpikeDetector
from .manual_selector import ManualSpikeSelector
