import sys
import h5py
import numpy as np
import matplotlib.pyplot as plt
from scipy import ndimage
import csv
import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QPushButton, QFileDialog, QLabel, QDoubleSpinBox, 
    QSpinBox, QGroupBox, QComboBox, QCheckBox, QSlider, QSplitter,
    QTextEdit, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QSize
from sklearn.cluster import DBSCAN  
from fastdtw import fastdtw  
from scipy import ndimage, signal
from scipy.spatial.distance import euclidean
import datetime

class StepDetector:
    """台阶检测工具"""
    
    def __init__(self, verbose=False):
        """初始化检测工具"""
        self.verbose = verbose
    
    def detect_steps(self, signal_data, params):
        """检测信号中的台阶变化点
        
        参数:
            signal_data: 信号数据
            params: 检测参数
            
        返回:
            边界索引列表
        """
        # 参数提取
        min_step_height = params.get('min_step_height', 0.1)
        min_step_width = params.get('min_step_width', 30)
        smoothing_width = params.get('smoothing_width', 10)
        detection_threshold = params.get('detection_threshold', 3.0)
        
        # 信号平滑处理
        if smoothing_width > 1:
            smooth_signal = ndimage.gaussian_filter1d(signal_data, smoothing_width)
        else:
            smooth_signal = signal_data.copy()
        
        # 计算一阶导数
        gradient = np.gradient(smooth_signal)
        
        # 计算导数的标准差，用于动态阈值
        gradient_std = np.std(gradient)
        step_threshold = detection_threshold * gradient_std
        
        # 检测突变点
        step_up_points = np.where(gradient > step_threshold)[0]
        step_down_points = np.where(gradient < -step_threshold)[0]
        
        # 合并并排序所有突变点
        all_step_points = np.sort(np.concatenate([step_up_points, step_down_points]))
        
        # 创建台阶边界列表
        boundaries = [0]  # 起始点
        
        # 对突变点进行聚类，防止检测到多个相邻点
        i = 0
        while i < len(all_step_points):
            current_point = all_step_points[i]
            # 找到连续突变的终点
            j = i
            while j+1 < len(all_step_points) and all_step_points[j+1] - all_step_points[j] < min_step_width/2:
                j += 1
            
            # 添加聚类后的点
            if j > i:
                # 如果有多个连续点，取中点
                boundaries.append(all_step_points[i] + (all_step_points[j] - all_step_points[i])//2)
                i = j + 1
            else:
                boundaries.append(current_point)
                i += 1
        
        # 添加终点
        if boundaries[-1] < len(signal_data) - 1:
            boundaries.append(len(signal_data) - 1)
        
        # 过滤掉太短的台阶
        filtered_boundaries = [boundaries[0]]
        for i in range(1, len(boundaries)):
            if boundaries[i] - filtered_boundaries[-1] >= min_step_width:
                filtered_boundaries.append(boundaries[i])
        
        # 确保包含末尾点
        if filtered_boundaries[-1] != boundaries[-1]:
            filtered_boundaries.append(boundaries[-1])
        
        return filtered_boundaries
    
    def count_second_derivative_zero_crossings(self, data):
        """计算二阶导数的零点数量
        
        参数:
            data: 信号数据
            
        返回:
            零点数量和零点位置列表
        """
        # 使用改进的拉普拉斯高斯方法检测
        return self.laplacian_of_gaussian_zero_crossings(data)
    
    def laplacian_of_gaussian_zero_crossings(self, signal, sigma=2.0):
        """使用拉普拉斯高斯算子检测零交叉点
        
        参数:
            signal: 信号数据
            sigma: 高斯平滑参数
            
        返回:
            零交叉点数量和位置列表，以及每个点的权重
        """
        # 高斯平滑
        smoothed = ndimage.gaussian_filter1d(signal, sigma)
        
        # 计算拉普拉斯算子(二阶导数)
        laplacian = ndimage.laplace(smoothed)
        
        # 找到零交叉点及其权重
        zero_crossings = []
        weights = []
        
        for i in range(1, len(laplacian)):
            if (laplacian[i-1] < 0 and laplacian[i] >= 0) or \
               (laplacian[i-1] >= 0 and laplacian[i] < 0):
                
                # 计算精确零点位置(线性插值)
                if laplacian[i] != laplacian[i-1]:
                    t = -laplacian[i-1] / (laplacian[i] - laplacian[i-1])
                    zero_pos = i-1 + t
                else:
                    zero_pos = i-0.5
                
                # 计算该零点的重要性权重
                # 使用附近的一阶导数最大值作为权重
                grad = np.gradient(smoothed)
                local_range = slice(max(0, i-5), min(len(grad), i+5))
                max_grad = np.max(np.abs(grad[local_range]))
                
                zero_crossings.append(int(zero_pos))
                weights.append(max_grad)
        
        # 归一化权重
        if weights:
            weights = np.array(weights) / (max(weights) + 1e-10)
        
        # 返回零点数量和位置列表，以及权重列表
        return len(zero_crossings), zero_crossings, weights
    
    def get_step_levels(self, signal_data, boundaries):
        """Get average level for each step using second derivative for boundary refinement
        
        Parameters:
            signal_data: Signal data array
            boundaries: Step boundary indices
                    
        Returns:
            List of step levels with detailed information
        """
        step_levels = []
        
        # Calculate average level for each step region, excluding edges
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i+1]
            step_duration = end_idx - start_idx
            
            # Extract complete step data
            full_step_data = signal_data[start_idx:end_idx]
            
            if step_duration >= 10:
                # Use second derivative method to determine precise stable region
                zeros_count, zero_positions, zero_weights = self.count_second_derivative_zero_crossings(full_step_data)
                
                # Get important zero positions and weights
                important_zeros = []
                threshold = 0.3  # Threshold for important zero crossings
                
                if zero_positions and zero_weights is not None:
                    for pos, weight in zip(zero_positions, zero_weights):
                        if weight > threshold:  # Only keep zero points with weight above threshold
                            important_zeros.append({
                                'position': start_idx + pos,
                                'weight': weight
                            })
                
                # Determine stable region based on important zero points
                if len(important_zeros) >= 2:
                    # Sort by position
                    important_zeros.sort(key=lambda x: x['position'])
                    
                    # Use first and last important zero crossings as boundaries
                    first_zero = important_zeros[0]['position']
                    last_zero = important_zeros[-1]['position']
                    
                    # Convert to absolute indices
                    if first_zero < last_zero:
                        stable_start = first_zero
                        stable_end = last_zero
                    else:
                        stable_start = start_idx
                        stable_end = end_idx - 1
                elif len(important_zeros) == 1:
                    # Only one important zero crossing - use it as center point
                    zero_pos = important_zeros[0]['position']
                    # Define stable region around this point
                    stable_start = max(start_idx, zero_pos - step_duration//4)
                    stable_end = min(end_idx - 1, zero_pos + step_duration//4)
                else:
                    # No important zero crossings found - use original boundaries
                    stable_start = start_idx
                    stable_end = end_idx - 1
                
                # Ensure valid boundary values
                stable_start = max(start_idx, stable_start)
                stable_end = min(end_idx - 1, stable_end)
                
                # 获取初步的stable区域数据
                initial_stable_data = signal_data[stable_start:stable_end+1]
                
                # 【新增】进一步使用三阶导数优化稳定区域
                if len(initial_stable_data) > 10:  # 确保有足够的数据点进行三阶导数分析
                    refined_region = self.refine_with_third_derivative(initial_stable_data, stable_start, stable_end)
                    
                    # 更新stable区域边界
                    refined_stable_start = refined_region['start']
                    refined_stable_end = refined_region['end']
                    found_new_region = refined_region['found_new_region']
                    third_zero_crossings = refined_region.get('zero_crossings', [])
                    
                    # 只有在找到新区域时才更新
                    if found_new_region:
                        stable_start = refined_stable_start
                        stable_end = refined_stable_end
                else:
                    found_new_region = False
                    third_zero_crossings = []
                    
                # 获取最终稳定区域数据
                stable_data = signal_data[stable_start:stable_end+1]
            else:
                # Step too short for analysis, use all points
                stable_start = start_idx
                stable_end = end_idx - 1
                stable_data = full_step_data
                found_new_region = False
                third_zero_crossings = []
            
            # Calculate average level using stable region data
            level = np.mean(stable_data)
            # Calculate RMS using stable region data
            rms = np.sqrt(np.mean(np.square(stable_data - np.mean(stable_data))))
            
            # Calculate data range (max - min)
            data_range = np.max(stable_data) - np.min(stable_data)
            
            # Calculate second derivative zero crossings
            zero_crossings, zero_positions, zero_weights = self.count_second_derivative_zero_crossings(full_step_data)
            
            # Save important zero positions and weights
            important_zeros = []
            if zero_positions and zero_weights is not None:
                for pos, weight in zip(zero_positions, zero_weights):
                    if weight > 0.3:  # Only keep zero points with weight above threshold
                        important_zeros.append({
                            'position': start_idx + pos,
                            'weight': weight
                        })
            
            step_info = {
                'start': start_idx,               # Original start position
                'end': end_idx,                   # Original end position
                'stable_start': stable_start,     # Stable region start position
                'stable_end': stable_end,         # Stable region end position
                'level': level,                   # Average level of stable region
                'rms': rms,                       # RMS of stable region
                'data_range': data_range,         # Data range of stable region
                'duration': end_idx - start_idx,  # Total duration
                'stable_duration': stable_end - stable_start + 1,  # Stable region duration
                'data': full_step_data,           # Complete data (including edges)
                'stable_data': stable_data,       # Stable region data (excluding edges)
                'zero_crossings': zero_crossings, # Number of second derivative zero crossings
                'zero_positions': important_zeros, # Important zero positions and weights
                'third_deriv_refined': found_new_region,  # 是否使用三阶导数优化了区域
                'third_zero_crossings': third_zero_crossings  # 三阶导数零点列表
            }
            
            step_levels.append(step_info)
        
        return step_levels

    def refine_with_third_derivative(self, stable_data, original_start, original_end):
        """使用三阶导数零点进一步优化stable region
        
        参数:
            stable_data: 原始stable region的数据
            original_start: 原始stable region的起始索引
            original_end: 原始stable region的结束索引
                
        返回:
            更新后的stable region信息，包括是否找到新region
        """
        try:
            # 应用高斯平滑
            sigma = 2.0  # 平滑参数
            smoothed = ndimage.gaussian_filter1d(stable_data, sigma)
            
            # 计算三阶导数 (先计算一阶导数，再计算二阶导数，最后计算三阶导数)
            first_deriv = np.gradient(smoothed)
            second_deriv = np.gradient(first_deriv)
            third_deriv = np.gradient(second_deriv)
            
            # 找到三阶导数的零点
            zero_crossings = []
            
            for i in range(1, len(third_deriv)):
                if (third_deriv[i-1] < 0 and third_deriv[i] >= 0) or \
                (third_deriv[i-1] >= 0 and third_deriv[i] < 0):
                    
                    # 计算精确零点位置(线性插值)
                    if third_deriv[i] != third_deriv[i-1]:
                        t = -third_deriv[i-1] / (third_deriv[i] - third_deriv[i-1])
                        zero_pos = i-1 + t
                    else:
                        zero_pos = i-0.5
                    
                    zero_crossings.append(int(zero_pos))
            
            # 如果找到了足够的零点，使用第二个和倒数第二个零点确定新的稳定区域
            if len(zero_crossings) >= 4:  # 至少需要4个零点才能取第二个和倒数第二个
                # 排序零点
                zero_crossings.sort()
                
                # 转换为绝对索引
                abs_zero_crossings = [original_start + zc for zc in zero_crossings]
                
                # 选择第二个和倒数第二个零点作为新边界
                new_stable_start = abs_zero_crossings[1]  # 第二个零点
                new_stable_end = abs_zero_crossings[-2]   # 倒数第二个零点
                
                # 确保新边界不超出原始stable region
                new_stable_start = max(new_stable_start, original_start)
                new_stable_end = min(new_stable_end, original_end)
                
                return {
                    'start': new_stable_start,
                    'end': new_stable_end,
                    'found_new_region': True,
                    'zero_crossings': abs_zero_crossings
                }
            elif len(zero_crossings) >= 2:  # 如果只有2-3个零点，使用首尾零点
                # 排序零点
                zero_crossings.sort()
                
                # 转换为绝对索引
                abs_zero_crossings = [original_start + zc for zc in zero_crossings]
                
                # 使用首尾零点
                new_stable_start = abs_zero_crossings[0]
                new_stable_end = abs_zero_crossings[-1]
                
                # 确保新边界不超出原始stable region
                new_stable_start = max(new_stable_start, original_start)
                new_stable_end = min(new_stable_end, original_end)
                
                return {
                    'start': new_stable_start,
                    'end': new_stable_end,
                    'found_new_region': True,
                    'zero_crossings': abs_zero_crossings
                }
            
            # 如果没有找到足够的零点，返回原始边界
            return {
                'start': original_start,
                'end': original_end,
                'found_new_region': False,
                'zero_crossings': []
            }
        
        except Exception as e:
            print(f"三阶导数优化出错: {e}")
            # 出错时返回原始边界
            return {
                'start': original_start,
                'end': original_end,
                'found_new_region': False,
                'zero_crossings': []
            }
    
    def merge_similar_steps(self, step_levels, level_tolerance):
        """合并水平值相近的相邻台阶，以及二阶导数只有一个零点的台阶
        
        参数:
            step_levels: 台阶水平列表
            level_tolerance: 水平容差 (小于此值的相邻台阶将被合并)
            
        返回:
            合并后的台阶水平列表
        """
        if not step_levels or len(step_levels) < 2:
            return step_levels.copy()
        
        # 标记需要合并的台阶
        to_merge = [False] * len(step_levels)
        
        # 标记二阶导数只有一个零点的台阶
        for i in range(len(step_levels)):
            if step_levels[i].get('zero_crossings', 0) <= 1:
                to_merge[i] = True
        
        merged_steps = [step_levels[0]]  # 从第一个台阶开始
        
        for i in range(1, len(step_levels)):
            current_step = step_levels[i]
            last_merged_step = merged_steps[-1]
            
            # 检查当前台阶是否与上一个合并后的台阶水平值接近
            # 或者当前台阶或上一个台阶是否需要合并（只有一个零点）
            if abs(current_step['level'] - last_merged_step['level']) <= level_tolerance or \
               to_merge[i] or to_merge[i-1]:
                # 合并台阶
                merged_data = np.concatenate([last_merged_step['data'], current_step['data']])
                merged_stable_data = np.concatenate([last_merged_step['stable_data'], current_step['stable_data']])
                
                # 计算新的统计值
                level = np.mean(merged_stable_data)
                rms = np.sqrt(np.mean(np.square(merged_stable_data)))
                data_range = np.max(merged_stable_data) - np.min(merged_stable_data)
                
                # 合并零点信息
                merged_zeros = []
                if 'zero_positions' in last_merged_step and last_merged_step['zero_positions']:
                    merged_zeros.extend(last_merged_step['zero_positions'])
                if 'zero_positions' in current_step and current_step['zero_positions']:
                    merged_zeros.extend(current_step['zero_positions'])
                
                merged_steps[-1] = {
                    'start': last_merged_step['start'],
                    'end': current_step['end'],
                    'stable_start': last_merged_step['stable_start'],
                    'stable_end': current_step['stable_end'],
                    'level': level,
                    'rms': rms,
                    'data_range': data_range,
                    'duration': current_step['end'] - last_merged_step['start'],
                    'stable_duration': current_step['stable_end'] - last_merged_step['stable_start'],
                    'data': merged_data,
                    'stable_data': merged_stable_data,
                    'zero_crossings': len(merged_zeros),
                    'zero_positions': merged_zeros
                }
            else:
                # 不合并，添加为新台阶
                merged_steps.append(current_step)
        
        return merged_steps
    
    def merge_steps_clustering(self, step_levels, eps_factor=0.5, min_samples=1):
        """使用聚类分析合并台阶
        
        参数:
            step_levels: 台阶水平列表
            eps_factor: 用于计算聚类距离参数的系数 (相对于水平值标准差)
            min_samples: DBSCAN的最小样本数参数
            
        返回:
            合并后的台阶水平列表
        """
        if not step_levels or len(step_levels) < 2:
            return step_levels.copy()
        
        # 提取台阶水平值
        levels = np.array([step['level'] for step in step_levels])
        levels_reshaped = levels.reshape(-1, 1)  # DBSCAN需要2D数组
        
        # 计算适合的eps参数 (基于水平值的分布)
        # 如果数据分散，eps大；如果数据集中，eps小
        data_std = np.std(levels)
        eps = data_std * eps_factor
        
        # 应用DBSCAN聚类
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(levels_reshaped)
        
        # 获取聚类标签
        labels = clustering.labels_
        
        # 识别聚类数量
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        if self.verbose:
            print(f"DBSCAN identified {n_clusters} clusters in the step levels")
        
        # 如果聚类没有产生不同的组，返回原始台阶
        if n_clusters <= 1:
            return step_levels.copy()
        
        # 准备存储合并结果
        merged_steps = []
        
        # 处理每个聚类内的台阶
        for current_label in range(n_clusters):
            # 获取当前聚类的索引
            indices = np.where(labels == current_label)[0]
            
            if len(indices) == 0:
                continue
            
            # 处理连续的台阶子组
            i = 0
            while i < len(indices):
                # 找到连续索引的起点
                start_group_idx = i
                
                # 向前查找连续的索引
                while (i + 1 < len(indices)) and (indices[i + 1] == indices[i] + 1):
                    i += 1
                
                # 现在i指向当前连续组的最后一个索引
                end_group_idx = i
                
                # 合并连续的台阶
                if start_group_idx == end_group_idx:
                    # 单一台阶，直接添加
                    merged_steps.append(step_levels[indices[start_group_idx]])
                else:
                    # 多个连续台阶需要合并
                    steps_to_merge = [step_levels[idx] for idx in indices[start_group_idx:end_group_idx+1]]
                    
                    # 创建合并台阶
                    first_step = steps_to_merge[0]
                    last_step = steps_to_merge[-1]
                    
                    # 合并所有数据
                    all_data = np.concatenate([step['data'] for step in steps_to_merge])
                    all_stable_data = np.concatenate([step['stable_data'] for step in steps_to_merge])
                    
                    # 合并零点信息
                    all_zeros = []
                    for step in steps_to_merge:
                        if 'zero_positions' in step and step['zero_positions']:
                            all_zeros.extend(step['zero_positions'])
                    
                    merged_step = {
                        'start': first_step['start'],
                        'end': last_step['end'],
                        'stable_start': first_step['stable_start'],
                        'stable_end': last_step['stable_end'],
                        'level': np.mean(all_stable_data),  # 使用稳定数据计算平均值
                        'rms': np.sqrt(np.mean(np.square(all_stable_data))),  # 使用稳定数据计算RMS
                        'data_range': np.max(all_stable_data) - np.min(all_stable_data),
                        'duration': last_step['end'] - first_step['start'],
                        'stable_duration': last_step['stable_end'] - first_step['stable_start'],
                        'data': all_data,
                        'stable_data': all_stable_data,
                        'zero_crossings': len(all_zeros),
                        'zero_positions': all_zeros
                    }
                    
                    merged_steps.append(merged_step)
                
                # 移动到下一组
                i += 1
        
        # 按开始索引排序结果
        merged_steps.sort(key=lambda x: x['start'])
        
        return merged_steps
    
    def merge_steps_dtw(self, step_levels, similarity_threshold=0.3, max_sample_points=100):
        """使用动态时间规整(DTW)比较台阶形状并合并相似台阶
        
        参数:
            step_levels: 台阶水平列表
            similarity_threshold: DTW距离阈值，小于此值的台阶被认为相似
            max_sample_points: 重采样长度，以提高计算效率
            
        返回:
            合并后的台阶水平列表
        """
        if not step_levels or len(step_levels) < 2:
            return step_levels.copy()
        
        merged_steps = [step_levels[0]]  # 从第一个台阶开始
        
        for i in range(1, len(step_levels)):
            current_step = step_levels[i]
            last_merged_step = merged_steps[-1]
            
            # 检查当前台阶是否应与上一台阶合并
            # 注意：这里应该使用稳定区域数据进行比较
            if self._are_steps_similar_dtw(
                    last_merged_step['stable_data'], 
                    current_step['stable_data'], 
                    threshold=similarity_threshold,
                    max_len=max_sample_points):
                
                # 合并台阶
                merged_data = np.concatenate([last_merged_step['data'], current_step['data']])
                merged_stable_data = np.concatenate([last_merged_step['stable_data'], current_step['stable_data']])
                
                # 合并零点信息
                merged_zeros = []
                if 'zero_positions' in last_merged_step and last_merged_step['zero_positions']:
                    merged_zeros.extend(last_merged_step['zero_positions'])
                if 'zero_positions' in current_step and current_step['zero_positions']:
                    merged_zeros.extend(current_step['zero_positions'])
                
                merged_steps[-1] = {
                    'start': last_merged_step['start'],
                    'end': current_step['end'],
                    'stable_start': last_merged_step['stable_start'],
                    'stable_end': current_step['stable_end'],
                    'level': np.mean(merged_stable_data),  # 使用稳定数据重新计算平均水平
                    'rms': np.sqrt(np.mean(np.square(merged_stable_data))),
                    'data_range': np.max(merged_stable_data) - np.min(merged_stable_data),
                    'duration': current_step['end'] - last_merged_step['start'],
                    'stable_duration': current_step['stable_end'] - last_merged_step['stable_start'],
                    'data': merged_data,
                    'stable_data': merged_stable_data,
                    'zero_crossings': len(merged_zeros),
                    'zero_positions': merged_zeros
                }
            else:
                # 不合并，添加为新台阶
                merged_steps.append(current_step)
        
        return merged_steps

    def _are_steps_similar_dtw(self, step1_data, step2_data, threshold=0.3, max_len=100):
        """使用DTW比较两个台阶的形状相似性"""
        try:
            # 如果两个台阶长度差异太大，可能不适合合并
            len_ratio = max(len(step1_data), len(step2_data)) / max(1, min(len(step1_data), len(step2_data)))
            if len_ratio > 5:  # 长度差异超过5倍
                return False
            
            # 确定重采样长度
            sample_len = min(max_len, max(len(step1_data), len(step2_data)))
            
            # 重采样到相同长度
            step1_resampled = signal.resample(step1_data, sample_len)
            step2_resampled = signal.resample(step2_data, sample_len)
            
            # Z-score归一化，专注于形状而非绝对值
            step1_mean = np.mean(step1_resampled)
            step2_mean = np.mean(step2_resampled)
            
            step1_norm = step1_resampled - step1_mean
            step2_norm = step2_resampled - step2_mean
            
            # 避免除以零
            std1 = np.std(step1_resampled)
            std2 = np.std(step2_resampled)
            
            if std1 > 1e-10:
                step1_norm = step1_norm / std1
            if std2 > 1e-10:
                step2_norm = step2_norm / std2
            
            # 确保是1D数组 - 这是关键修复
            if len(step1_norm.shape) > 1:
                step1_norm = step1_norm.flatten()
            if len(step2_norm.shape) > 1:
                step2_norm = step2_norm.flatten()
            
            # 计算DTW距离
            distance, _ = fastdtw(step1_norm, step2_norm, dist=euclidean)
            
            # 归一化距离，考虑序列长度
            normalized_distance = distance / sample_len
            
            return normalized_distance < threshold
        
        except Exception as e:
            print(f"DTW计算错误: {e}")
            # 出错时保守处理，不合并
            return False
        
    def merge_steps_adaptive_hybrid(self, step_levels, base_tolerance=0.05, noise_factor=2.0, min_confidence=0.3):
        """自适应混合合并方法，适用于复杂数据
        
        参数:
            step_levels: 台阶水平列表
            base_tolerance: 基础容差值
            noise_factor: 噪音影响因子
            min_confidence: 最小置信度，低于此值的台阶更容易被合并
            
        返回:
            合并后的台阶水平列表
        """
        if not step_levels or len(step_levels) < 2:
            return step_levels.copy()
        
        # 为每个台阶计算置信度分数
        for step in step_levels:
            step['confidence'] = self._calculate_step_confidence(step)
        
        # 初始化合并结果，从第一个台阶开始
        merged_steps = [step_levels[0]]
        
        for i in range(1, len(step_levels)):
            current_step = step_levels[i]
            last_merged_step = merged_steps[-1]
            
            # 1. 计算自适应容差
            current_noise = self._estimate_local_noise(current_step)
            last_noise = self._estimate_local_noise(last_merged_step)
            local_noise = max(current_noise, last_noise)
            
            # 调整容差 - 噪音越大，容差越大
            adaptive_tolerance = base_tolerance * (1.0 + noise_factor * local_noise)
            
            # 2. 考虑置信度 - 低置信度台阶更容易被合并
            confidence_factor = min(current_step['confidence'], last_merged_step['confidence'])
            if confidence_factor < min_confidence:
                # 低置信度增加容差
                adaptive_tolerance *= (min_confidence / confidence_factor)
            
            # 3. 合并判定标准 - 结合多种因素
            should_merge = False
            
            # 标准1: 水平值差异在容差范围内
            level_diff = abs(current_step['level'] - last_merged_step['level'])
            if level_diff <= adaptive_tolerance:
                should_merge = True
            
            # 标准2: 零交叉点特征分析
            if self._should_merge_by_zero_crossings(current_step, last_merged_step):
                should_merge = True
            
            # 标准3: 形状相似性检查（适用于较长台阶）
            if current_step['duration'] > 50 and last_merged_step['duration'] > 50:
                shape_similar = self._check_shape_similarity(current_step, last_merged_step)
                if shape_similar:
                    should_merge = True
            
            # 执行合并或添加新台阶
            if should_merge:
                # 合并台阶
                merged_data = np.concatenate([last_merged_step['data'], current_step['data']])
                merged_stable_data = np.concatenate([last_merged_step['stable_data'], current_step['stable_data']])
                
                # 计算新的统计值
                level = np.mean(merged_stable_data)
                rms = np.sqrt(np.mean(np.square(merged_stable_data - np.mean(merged_stable_data))))
                data_range = np.max(merged_stable_data) - np.min(merged_stable_data)
                
                # 合并零点信息
                merged_zeros = []
                if 'zero_positions' in last_merged_step and last_merged_step['zero_positions']:
                    merged_zeros.extend(last_merged_step['zero_positions'])
                if 'zero_positions' in current_step and current_step['zero_positions']:
                    merged_zeros.extend(current_step['zero_positions'])
                
                # 重新计算合并后台阶的置信度
                merged_step = {
                    'start': last_merged_step['start'],
                    'end': current_step['end'],
                    'stable_start': last_merged_step['stable_start'],
                    'stable_end': current_step['stable_end'],
                    'level': level,
                    'rms': rms,
                    'data_range': data_range,
                    'duration': current_step['end'] - last_merged_step['start'],
                    'stable_duration': current_step['stable_end'] - last_merged_step['stable_start'],
                    'data': merged_data,
                    'stable_data': merged_stable_data,
                    'zero_crossings': len(merged_zeros),
                    'zero_positions': merged_zeros
                }
                
                # 更新合并后的置信度
                merged_step['confidence'] = self._calculate_step_confidence(merged_step)
                
                merged_steps[-1] = merged_step
            else:
                # 不合并，添加为新台阶
                merged_steps.append(current_step)
        
        return merged_steps

    def _estimate_local_noise(self, step):
        """估计台阶的局部噪音水平，返回0-1范围内的值"""
        noise_indicators = []
        
        # 指标1: 使用RMS与水平值的比例
        if abs(step['level']) > 1e-10:
            rms_ratio = step['rms'] / abs(step['level'])
            noise_indicators.append(min(1.0, rms_ratio))
        else:
            noise_indicators.append(min(1.0, step['rms']))
        
        # 指标2: 数据极差与水平的比值
        if abs(step['level']) > 1e-10:
            range_ratio = step['data_range'] / abs(step['level'])
            noise_indicators.append(min(1.0, range_ratio / 2.0))
        
        # 指标3: 零交叉点权重的变异系数（如果有）
        if 'zero_positions' in step and step['zero_positions']:
            weights = [zc['weight'] for zc in step['zero_positions']]
            if weights and np.mean(weights) > 0:
                cv = np.std(weights) / np.mean(weights)
                noise_indicators.append(min(1.0, cv))
        
        # 综合多个指标，取最大值作为噪音评估
        return max(noise_indicators) if noise_indicators else 0.5

    def _calculate_step_confidence(self, step):
        """计算台阶的置信度分数（0-1范围）"""
        # 基础分数从1.0开始，根据各种因素扣分
        confidence = 1.0
        
        # 因素1: 持续时间 - 太短的台阶可信度低
        duration_score = min(1.0, step['duration'] / 100.0)
        confidence *= (0.5 + 0.5 * duration_score)
        
        # 因素2: 零交叉点 - 过少的零交叉点表示台阶定义不清晰
        if 'zero_crossings' in step:
            if step['zero_crossings'] <= 1:
                confidence *= 0.5
            else:
                zero_score = min(1.0, step['zero_crossings'] / 5.0)
                confidence *= (0.7 + 0.3 * zero_score)
        
        # 因素3: 信噪比(SNR) - 使用水平与RMS的比值
        if step['rms'] > 1e-10:
            snr = abs(step['level']) / step['rms']
            snr_score = min(1.0, snr / 10.0)
            confidence *= (0.6 + 0.4 * snr_score)
        
        # 因素4: 数据范围与水平值的比例 - 比例越小越好
        if abs(step['level']) > 1e-10:
            range_ratio = step['data_range'] / abs(step['level'])
            range_score = max(0.0, 1.0 - min(1.0, range_ratio / 2.0))
            confidence *= (0.8 + 0.2 * range_score)
        
        # 因素5: 稳定区域占比 - 稳定区域占比越大越好
        if step['duration'] > 0:
            stable_ratio = step['stable_duration'] / step['duration']
            confidence *= (0.7 + 0.3 * stable_ratio)
        
        return confidence

    def _should_merge_by_zero_crossings(self, step1, step2, min_weight_threshold=0.4):
        """基于零交叉点特征分析是否应该合并两个台阶"""
        # 检查是否任一台阶的零交叉点太少
        if step1.get('zero_crossings', 0) <= 1 or step2.get('zero_crossings', 0) <= 1:
            # 查看是否存在重要的零交叉点
            important_zeros1 = [zc for zc in step1.get('zero_positions', []) 
                            if zc['weight'] > min_weight_threshold]
            important_zeros2 = [zc for zc in step2.get('zero_positions', []) 
                            if zc['weight'] > min_weight_threshold]
            
            # 只有当两个台阶都没有重要零交叉点时才合并
            if len(important_zeros1) == 0 and len(important_zeros2) == 0:
                return True
        
        return False

    def _check_shape_similarity(self, step1, step2, similarity_threshold=0.4):
        """检查两个台阶的形状相似性，返回布尔值"""
        try:
            # 如果两个台阶长度差异太大，可能不适合合并
            len_ratio = max(len(step1['stable_data']), len(step2['stable_data'])) / max(1, min(len(step1['stable_data']), len(step2['stable_data'])))
            if len_ratio > 5:  # 长度差异超过5倍
                return False
            
            # 对较短的台阶进行重采样以匹配较长的台阶
            max_len = 50  # 限制计算量
            
            if len(step1['stable_data']) > len(step2['stable_data']):
                longer_data = step1['stable_data']
                shorter_data = step2['stable_data']
            else:
                longer_data = step2['stable_data']
                shorter_data = step1['stable_data']
            
            # 重采样较短的数据
            sample_len = min(max_len, len(longer_data))
            shorter_resampled = signal.resample(shorter_data, sample_len)
            longer_resampled = signal.resample(longer_data, sample_len)
            
            # 归一化处理，消除水平值差异的影响
            shorter_norm = shorter_resampled - np.mean(shorter_resampled)
            longer_norm = longer_resampled - np.mean(longer_resampled)
            
            std1 = np.std(shorter_norm)
            std2 = np.std(longer_norm)
            
            if std1 > 1e-10:
                shorter_norm = shorter_norm / std1
            if std2 > 1e-10:
                longer_norm = longer_norm / std2
            
            # 计算相关系数
            correlation = np.corrcoef(shorter_norm, longer_norm)[0, 1]
            
            # 计算均方误差
            mse = np.mean(np.square(shorter_norm - longer_norm))
            
            # 综合判断相似性
            return (correlation > 0.7) or (mse < similarity_threshold)
        
        except Exception as e:
            print(f"形状相似性计算错误: {e}")
            return False


class MatplotlibCanvas(FigureCanvas):
    """Qt应用中的Matplotlib画布"""
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MatplotlibCanvas, self).__init__(self.fig)


class StepDetailCanvas(FigureCanvas):
    """显示单个台阶详情的画布"""
    def __init__(self, parent=None, width=4, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(StepDetailCanvas, self).__init__(self.fig)


class MultiStepCanvas(FigureCanvas):
    """显示多个台阶的画布"""
    def __init__(self, parent=None, width=8, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MultiStepCanvas, self).__init__(self.fig)


class StepDetectorGUI(QMainWindow):
    """台阶检测GUI"""
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Step Detector Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化数据
        self.current_file_path = None
        self.dataset_name = None
        self.signal_data = None
        self.detector = StepDetector()
        self.step_boundaries = []
        self.step_levels = []
        self.merged_step_levels = []
        self.data_loaded = False
        self.current_step_index = -1  # 当前选中的台阶索引
        self.saved_steps = set()      # 记录已保存台阶
        self.marked_steps = set()      # Set to track marked steps
        self.viewing_marked_only = False  # Flag to track if we're viewing only marked steps
        
        # 设置UI
        self.setup_ui()
    
    def setup_ui(self):
        # 创建主窗口部件
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # 创建左右分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # 左侧控制面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 文件操作区域
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout()
        
        # 加载文件和数据集选择（水平）
        file_controls = QHBoxLayout()
        self.load_file_btn = QPushButton("Load H5 File")
        self.load_file_btn.clicked.connect(self.load_h5_file)
        file_controls.addWidget(self.load_file_btn)
        
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEnabled(False)
        self.dataset_combo.currentIndexChanged.connect(self.select_dataset)
        file_controls.addWidget(QLabel("Dataset:"))
        file_controls.addWidget(self.dataset_combo)
        file_layout.addLayout(file_controls)
        
        # 运行按钮（独占一行）
        self.run_btn = QPushButton("Detect Steps")
        self.run_btn.clicked.connect(self.detect_steps)
        self.run_btn.setEnabled(False)
        file_layout.addWidget(self.run_btn)
        
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)
        
        # 台阶检测参数区域
        detection_group = QGroupBox("Step Detection Parameters")
        detection_layout = QGridLayout()
        
        # 最小台阶高度
        detection_layout.addWidget(QLabel("Min Step Height:"), 0, 0)
        self.min_step_height_spin = QDoubleSpinBox()
        self.min_step_height_spin.setRange(0.01, 10.0)
        self.min_step_height_spin.setSingleStep(0.01)
        self.min_step_height_spin.setValue(0.1)
        self.min_step_height_spin.setToolTip("Minimum height for step detection")
        detection_layout.addWidget(self.min_step_height_spin, 0, 1)
        
        # 最小台阶宽度
        detection_layout.addWidget(QLabel("Min Step Width:"), 1, 0)
        self.min_step_width_spin = QSpinBox()
        self.min_step_width_spin.setRange(5, 500)
        self.min_step_width_spin.setSingleStep(5)
        self.min_step_width_spin.setValue(30)
        self.min_step_width_spin.setToolTip("Minimum width for step detection (in data points)")
        detection_layout.addWidget(self.min_step_width_spin, 1, 1)
        
        # 平滑宽度
        detection_layout.addWidget(QLabel("Smoothing Width:"), 2, 0)
        self.smoothing_width_spin = QSpinBox()
        self.smoothing_width_spin.setRange(1, 50)
        self.smoothing_width_spin.setSingleStep(1)
        self.smoothing_width_spin.setValue(10)
        self.smoothing_width_spin.setToolTip("Width of Gaussian smoothing filter")
        detection_layout.addWidget(self.smoothing_width_spin, 2, 1)
        
        # 检测阈值 - 数值微调框
        detection_layout.addWidget(QLabel("Detection Threshold:"), 3, 0)
        self.detection_threshold_spin = QDoubleSpinBox()
        self.detection_threshold_spin.setRange(0.1, 20.0)
        self.detection_threshold_spin.setSingleStep(0.1)
        self.detection_threshold_spin.setDecimals(2)
        self.detection_threshold_spin.setValue(3.0)
        self.detection_threshold_spin.setToolTip("Threshold for step detection (multiplier of gradient std)")
        detection_layout.addWidget(self.detection_threshold_spin, 3, 1)
        
        # 检测阈值 - 滑动条
        detection_layout.addWidget(QLabel("Threshold Adjust:"), 4, 0, 1, 2)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 200)  # 对应0.1到20.0
        self.threshold_slider.setValue(30)      # 对应3.0
        self.threshold_slider.setToolTip("Drag to adjust detection threshold")
        detection_layout.addWidget(self.threshold_slider, 5, 0, 1, 2)
        
        # 合并相似台阶参数
        detection_layout.addWidget(QLabel("Merge Similar Steps:"), 6, 0)
        self.merge_steps_checkbox = QCheckBox()
        self.merge_steps_checkbox.setChecked(True)
        self.merge_steps_checkbox.setToolTip("Check to merge adjacent steps with similar levels")
        detection_layout.addWidget(self.merge_steps_checkbox, 6, 1)

        # 合并方法选择
        detection_layout.addWidget(QLabel("Merge Method:"), 7, 0)
        self.merge_method_combo = QComboBox()
        self.merge_method_combo.addItems(["Adjacent Only", "Clustering", "DTW Shape", "Adaptive Hybrid"])  # 添加新选项
        self.merge_method_combo.setToolTip("Select how to merge similar steps")
        self.merge_method_combo.currentIndexChanged.connect(self.update_merge_method_ui)
        detection_layout.addWidget(self.merge_method_combo, 7, 1)

        # 水平容差参数（用于Adjacent Only方法）
        self.level_tolerance_label = QLabel("Level Tolerance:")
        detection_layout.addWidget(self.level_tolerance_label, 8, 0)
        self.level_tolerance_spin = QDoubleSpinBox()
        self.level_tolerance_spin.setRange(0.001, 1.0)
        self.level_tolerance_spin.setSingleStep(0.005)
        self.level_tolerance_spin.setValue(0.05)
        self.level_tolerance_spin.setToolTip("Tolerance for merging steps (adjacent steps with level difference below this will be merged)")
        detection_layout.addWidget(self.level_tolerance_spin, 8, 1)

        # 聚类参数（用于Clustering方法）
        self.cluster_param_label = QLabel("Cluster Distance Factor:")
        detection_layout.addWidget(self.cluster_param_label, 9, 0)
        self.eps_factor_spin = QDoubleSpinBox()
        self.eps_factor_spin.setRange(0.1, 2.0)
        self.eps_factor_spin.setSingleStep(0.1)
        self.eps_factor_spin.setValue(0.5)
        self.eps_factor_spin.setToolTip("Factor for DBSCAN eps parameter (higher values merge more steps)")
        detection_layout.addWidget(self.eps_factor_spin, 9, 1)

        # DTW参数（用于DTW Shape方法）
        self.dtw_param_label = QLabel("DTW Similarity Threshold:")
        detection_layout.addWidget(self.dtw_param_label, 10, 0)
        self.dtw_threshold_spin = QDoubleSpinBox()
        self.dtw_threshold_spin.setRange(0.1, 1.0)
        self.dtw_threshold_spin.setSingleStep(0.05)
        self.dtw_threshold_spin.setValue(0.3)
        self.dtw_threshold_spin.setToolTip("DTW distance threshold (lower values require more similar shapes)")
        detection_layout.addWidget(self.dtw_threshold_spin, 10, 1)

        # 添加自适应混合方法的参数控件
        self.adaptive_base_tolerance_label = QLabel("基础容差:")
        detection_layout.addWidget(self.adaptive_base_tolerance_label, 11, 0)
        self.adaptive_base_tolerance_spin = QDoubleSpinBox()
        self.adaptive_base_tolerance_spin.setRange(0.01, 0.5)
        self.adaptive_base_tolerance_spin.setSingleStep(0.01)
        self.adaptive_base_tolerance_spin.setValue(0.05)
        self.adaptive_base_tolerance_spin.setToolTip("噪音低的区域使用的基础容差")
        detection_layout.addWidget(self.adaptive_base_tolerance_spin, 11, 1)

        self.noise_factor_label = QLabel("噪音因子:")
        detection_layout.addWidget(self.noise_factor_label, 12, 0)
        self.noise_factor_spin = QDoubleSpinBox()
        self.noise_factor_spin.setRange(1.0, 10.0)
        self.noise_factor_spin.setSingleStep(0.5)
        self.noise_factor_spin.setValue(2.0)
        self.noise_factor_spin.setToolTip("控制噪音对容差的影响程度")
        detection_layout.addWidget(self.noise_factor_spin, 12, 1)

        self.min_confidence_label = QLabel("最小置信度:")
        detection_layout.addWidget(self.min_confidence_label, 13, 0)
        self.min_confidence_spin = QDoubleSpinBox()
        self.min_confidence_spin.setRange(0.1, 0.9)
        self.min_confidence_spin.setSingleStep(0.05)
        self.min_confidence_spin.setValue(0.3)
        self.min_confidence_spin.setToolTip("低于此置信度的台阶更容易被合并")
        detection_layout.addWidget(self.min_confidence_spin, 13, 1)

        # 初始化UI状态
        self.update_merge_method_ui(0)  # 默认选择Adjacent Only方法

        # 连接滑动条和微调框的信号
        self.threshold_slider.valueChanged.connect(self.update_threshold_from_slider)
        self.detection_threshold_spin.valueChanged.connect(self.update_slider_from_threshold)
        
        detection_group.setLayout(detection_layout)
        left_layout.addWidget(detection_group)
        
        # In the status_group's layout creation section:
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()

        # 台阶数量标签
        self.steps_label = QLabel("Detected Steps: 0")
        status_layout.addWidget(self.steps_label)

        # First create the save all results button (BEFORE trying to access it)
        self.save_all_results_btn = QPushButton("Save All Results")
        self.save_all_results_btn.clicked.connect(self.save_all_results)
        self.save_all_results_btn.setEnabled(False)

        # Filter layout
        filter_layout = QGridLayout()
        filter_layout.addWidget(QLabel("Filter for saving:"), 0, 0, 1, 4)

        # RMS filter inputs
        filter_layout.addWidget(QLabel("RMS Min:"), 1, 0)
        self.rms_min_filter = QDoubleSpinBox()
        self.rms_min_filter.setRange(0, 10.0)
        self.rms_min_filter.setSingleStep(0.001)
        self.rms_min_filter.setDecimals(6)
        self.rms_min_filter.setSpecialValueText("")  # Empty for no filter
        self.rms_min_filter.setToolTip("Minimum RMS value (empty for no limit)")
        filter_layout.addWidget(self.rms_min_filter, 1, 1)

        filter_layout.addWidget(QLabel("RMS Max:"), 1, 2)
        self.rms_max_filter = QDoubleSpinBox()
        self.rms_max_filter.setRange(0, 10.0)
        self.rms_max_filter.setSingleStep(0.001)
        self.rms_max_filter.setDecimals(6)
        self.rms_max_filter.setSpecialValueText("")  # Empty for no filter
        self.rms_max_filter.setToolTip("Maximum RMS value (empty for no limit)")
        filter_layout.addWidget(self.rms_max_filter, 1, 3)

        # Data Range filter inputs
        filter_layout.addWidget(QLabel("Data Range Min:"), 2, 0)
        self.data_range_min_filter = QDoubleSpinBox()
        self.data_range_min_filter.setRange(0, 10.0)
        self.data_range_min_filter.setSingleStep(0.001)
        self.data_range_min_filter.setDecimals(6)
        self.data_range_min_filter.setSpecialValueText("")  # Empty for no filter
        self.data_range_min_filter.setToolTip("Minimum data range value (empty for no limit)")
        filter_layout.addWidget(self.data_range_min_filter, 2, 1)

        filter_layout.addWidget(QLabel("Data Range Max:"), 2, 2)
        self.data_range_max_filter = QDoubleSpinBox()
        self.data_range_max_filter.setRange(0, 10.0)
        self.data_range_max_filter.setSingleStep(0.001)
        self.data_range_max_filter.setDecimals(6)
        self.data_range_max_filter.setSpecialValueText("")  # Empty for no filter
        self.data_range_max_filter.setToolTip("Maximum data range value (empty for no limit)")
        filter_layout.addWidget(self.data_range_max_filter, 2, 3)

        # Add filter layout to status layout
        status_layout.addLayout(filter_layout)

        # NOW create the mark/save layout and add both buttons to it
        mark_save_layout = QHBoxLayout()  # Use horizontal layout for the two buttons
        self.mark_all_btn = QPushButton("Mark All Filtered")
        self.mark_all_btn.clicked.connect(self.mark_filtered_steps)
        self.mark_all_btn.setEnabled(False)
        mark_save_layout.addWidget(self.mark_all_btn)
        # Now we can safely add the save_all_results_btn since it exists
        mark_save_layout.addWidget(self.save_all_results_btn)
        status_layout.addLayout(mark_save_layout)

        # Add checkbox for viewing only marked steps
        self.view_marked_only_checkbox = QCheckBox("Only View Marked Steps")
        self.view_marked_only_checkbox.setChecked(False)
        self.view_marked_only_checkbox.setEnabled(False)
        self.view_marked_only_checkbox.stateChanged.connect(self.toggle_marked_only_view)
        status_layout.addWidget(self.view_marked_only_checkbox)

        # 在view_marked_only_checkbox后添加显示控制选项
        self.show_dividers_checkbox = QCheckBox("Show Step Dividers")
        self.show_dividers_checkbox.setChecked(True)  # 默认选中
        self.show_dividers_checkbox.stateChanged.connect(self.update_display_settings)
        status_layout.addWidget(self.show_dividers_checkbox)

        self.show_step_numbers_checkbox = QCheckBox("Show Step Numbers")
        self.show_step_numbers_checkbox.setChecked(True)  # 默认选中
        self.show_step_numbers_checkbox.stateChanged.connect(self.update_display_settings)
        status_layout.addWidget(self.show_step_numbers_checkbox)

        # 状态标签
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)
        
        # 台阶信息区域
        step_info_group = QGroupBox("Step Information")
        step_info_layout = QVBoxLayout()
        
        # 台阶信息文本显示
        self.step_info_text = QTextEdit()
        self.step_info_text.setReadOnly(True)
        self.step_info_text.setMinimumHeight(100)
        step_info_layout.addWidget(self.step_info_text)
        
        # 跳转到指定台阶控件
        jump_layout = QHBoxLayout()
        jump_layout.addWidget(QLabel("Jump to Step:"))
        self.step_jump_spin = QSpinBox()
        self.step_jump_spin.setMinimum(1)
        self.step_jump_spin.setMaximum(1000)  # 默认最大值，会在检测到台阶后更新
        self.step_jump_btn = QPushButton("Jump")
        self.step_jump_btn.clicked.connect(self.goto_step)
        self.step_jump_btn.setEnabled(False)
        jump_layout.addWidget(self.step_jump_spin)
        jump_layout.addWidget(self.step_jump_btn)
        step_info_layout.addLayout(jump_layout)
        
        # 台阶导航按钮
        nav_buttons_layout = QHBoxLayout()
        
        self.prev_step_btn = QPushButton("Previous")
        self.prev_step_btn.clicked.connect(self.goto_previous_step)
        self.prev_step_btn.setEnabled(False)
        nav_buttons_layout.addWidget(self.prev_step_btn)
        
        self.next_step_btn = QPushButton("Next")
        self.next_step_btn.clicked.connect(self.goto_next_step)
        self.next_step_btn.setEnabled(False)
        nav_buttons_layout.addWidget(self.next_step_btn)
        
        step_info_layout.addLayout(nav_buttons_layout)
        
        # 保存和跳过按钮
        action_buttons_layout = QHBoxLayout()
        
        self.save_step_btn = QPushButton("Save Step")
        self.save_step_btn.clicked.connect(self.save_current_step)
        self.save_step_btn.setEnabled(False)
        action_buttons_layout.addWidget(self.save_step_btn)
        
        self.skip_step_btn = QPushButton("Skip Step")
        self.skip_step_btn.clicked.connect(self.skip_current_step)
        self.skip_step_btn.setEnabled(False)
        action_buttons_layout.addWidget(self.skip_step_btn)
        
        step_info_layout.addLayout(action_buttons_layout)
        
        step_info_group.setLayout(step_info_layout)
        left_layout.addWidget(step_info_group)

        # 添加一个新组：Nearby Steps 控制
        nearby_steps_group = QGroupBox("Nearby Steps Display")
        nearby_steps_layout = QHBoxLayout()

        # 添加输入框和标签，用于控制显示范围
        nearby_steps_layout.addWidget(QLabel("Display Range (±):"))
        self.nearby_steps_range_spin = QSpinBox()
        self.nearby_steps_range_spin.setRange(1, 50)  # 允许设置 1 到 50 的范围
        self.nearby_steps_range_spin.setValue(15)      # 默认值设为 15，与原始代码一致
        self.nearby_steps_range_spin.setToolTip("Number of steps to display before and after the current step")
        self.nearby_steps_range_spin.valueChanged.connect(self.update_nearby_steps_display)  # 连接信号
        nearby_steps_layout.addWidget(self.nearby_steps_range_spin)

        nearby_steps_group.setLayout(nearby_steps_layout)
        step_info_layout.addWidget(nearby_steps_group)  # 添加到 step_info_layout 中
        
        # 创建一个滚动区域来包含左侧面板
        left_scroll_area = QScrollArea()
        left_scroll_area.setWidget(left_panel)
        left_scroll_area.setWidgetResizable(True)  # 重要：允许小部件调整大小
        left_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll_area.setMinimumWidth(350)
        left_scroll_area.setMaximumWidth(450)
        
        # 将滚动区域添加到分割器，而不是直接添加左侧面板
        self.main_splitter.addWidget(left_scroll_area)
        
        # 右侧信息面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 右侧上下分割器
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)
        
        # 右上方 - 信号总览
        overview_group = QGroupBox("Signal Overview")
        overview_layout = QVBoxLayout()
        self.overview_canvas = MatplotlibCanvas(width=8, height=4)
        self.overview_toolbar = NavigationToolbar(self.overview_canvas, self)
        overview_layout.addWidget(self.overview_toolbar)
        overview_layout.addWidget(self.overview_canvas)
        overview_group.setLayout(overview_layout)
        
        # 添加信号总览到右侧分割器
        self.right_splitter.addWidget(overview_group)
        
        # 右下方面板 - 台阶详情
        bottom_panel = QWidget()
        bottom_layout = QHBoxLayout(bottom_panel)
        
        # 右下方左侧 - 当前台阶数据可视化
        step_detail_group = QGroupBox("Step Detail View")
        step_detail_layout = QVBoxLayout()
        self.step_detail_canvas = StepDetailCanvas(width=4, height=3)
        step_detail_layout.addWidget(self.step_detail_canvas)
        step_detail_group.setLayout(step_detail_layout)
        bottom_layout.addWidget(step_detail_group)
        
        # 右下方右侧 - 显示当前台阶附近的30个台阶
        nearby_steps_group = QGroupBox("Nearby Steps (±15 steps)")
        nearby_steps_layout = QVBoxLayout()
        self.nearby_steps_canvas = MultiStepCanvas(width=8, height=4)
        nearby_steps_layout.addWidget(self.nearby_steps_canvas)
        nearby_steps_group.setLayout(nearby_steps_layout)
        bottom_layout.addWidget(nearby_steps_group)
        
        # 设置底部面板的布局
        bottom_panel.setLayout(bottom_layout)
        
        # 添加右下方面板到右侧分割器
        self.right_splitter.addWidget(bottom_panel)
        
        # 设置分割器比例
        self.right_splitter.setSizes([500, 300])  # 上大下小
        
        # 添加右面板到主分割器
        self.main_splitter.addWidget(right_panel)
        
        # 设置主分割器比例
        self.main_splitter.setSizes([350, 850])  # 左小右大
        
        # 设置中心部件
        self.setCentralWidget(main_widget)

    def update_merge_method_ui(self, index):
        """根据选择的合并方法更新UI元素的可见性"""
        method = self.merge_method_combo.currentText()
        
        # 默认隐藏所有特定方法的参数
        self.level_tolerance_label.setVisible(False)
        self.level_tolerance_spin.setVisible(False)
        self.cluster_param_label.setVisible(False)
        self.eps_factor_spin.setVisible(False)
        self.dtw_param_label.setVisible(False)
        self.dtw_threshold_spin.setVisible(False)
        self.adaptive_base_tolerance_label.setVisible(False)
        self.adaptive_base_tolerance_spin.setVisible(False)
        self.noise_factor_label.setVisible(False)
        self.noise_factor_spin.setVisible(False)
        self.min_confidence_label.setVisible(False)
        self.min_confidence_spin.setVisible(False)
        
        # 根据选择的方法显示相应参数
        if method == "Adjacent Only":
            self.level_tolerance_label.setVisible(True)
            self.level_tolerance_spin.setVisible(True)
        elif method == "Clustering":
            self.cluster_param_label.setVisible(True)
            self.eps_factor_spin.setVisible(True)
        elif method == "DTW Shape":
            self.dtw_param_label.setVisible(True)
            self.dtw_threshold_spin.setVisible(True)
        elif method == "Adaptive Hybrid":
            self.adaptive_base_tolerance_label.setVisible(True)
            self.adaptive_base_tolerance_spin.setVisible(True)
            self.noise_factor_label.setVisible(True)
            self.noise_factor_spin.setVisible(True)
            self.min_confidence_label.setVisible(True)
            self.min_confidence_spin.setVisible(True)
    
    def load_h5_file(self):
        """加载H5文件并提取数据集信息"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select H5 File", "", "HDF5 Files (*.h5 *.hdf5)")
        
        if not file_path:
            return
        
        try:
            # 清除之前的数据和结果
            self.signal_data = None
            self.step_boundaries = []
            self.step_levels = []
            self.merged_step_levels = []
            self.data_loaded = False
            self.save_all_results_btn.setEnabled(False)
            self.save_step_btn.setEnabled(False)
            self.skip_step_btn.setEnabled(False)
            self.prev_step_btn.setEnabled(False)
            self.next_step_btn.setEnabled(False)
            self.step_jump_btn.setEnabled(False)  # 禁用跳转按钮

            self.mark_all_btn.setEnabled(False)
            self.view_marked_only_checkbox.setEnabled(False)
            self.view_marked_only_checkbox.setChecked(False)
            self.marked_steps.clear()
            self.viewing_marked_only = False

            self.current_step_index = -1
            self.saved_steps = set()
            self.steps_label.setText("Detected Steps: 0")
            self.step_info_text.clear()
            
            # 重置画布
            self.overview_canvas.axes.clear()
            self.overview_canvas.draw()
            self.step_detail_canvas.axes.clear()
            self.step_detail_canvas.draw()
            self.nearby_steps_canvas.axes.clear()
            self.nearby_steps_canvas.draw()
            
            # 打开H5文件
            with h5py.File(file_path, 'r') as f:
                # 清除之前的数据集
                self.dataset_combo.clear()
                
                # 递归查找所有数据集
                def find_datasets(name, obj):
                    if isinstance(obj, h5py.Dataset) and len(obj.shape) > 0:
                        # 只显示1D数据集
                        if len(obj.shape) == 1:
                            self.dataset_combo.addItem(name)
                
                # 访问H5文件中的所有对象
                f.visititems(find_datasets)
            
            # 保存当前文件路径
            self.current_file_path = file_path
            
            # 更新UI状态
            self.dataset_combo.setEnabled(True)
            if self.dataset_combo.count() > 0:
                self.status_label.setText(f"File loaded: {file_path}")
                # 自动选择第一个数据集
                if self.dataset_combo.count() > 0:
                    self.dataset_combo.setCurrentIndex(0)
                    # 关键修复：直接调用select_dataset函数，解决第一次加载不显示数据的问题
                    self.select_dataset(0)
            else:
                self.status_label.setText("No suitable datasets found in file")
        
        except Exception as e:
            self.status_label.setText(f"Error loading file: {str(e)}")
    
    def select_dataset(self, index):
        """选择数据集并加载数据"""
        if index < 0:
            return
        
        self.dataset_name = self.dataset_combo.currentText()
        
        try:
            # 打开H5文件
            with h5py.File(self.current_file_path, 'r') as f:
                # 加载数据集
                self.signal_data = f[self.dataset_name][:]
            
            # 标记数据已加载
            self.data_loaded = True
            
            # 绘制原始信号
            self.plot_signal()
            
            # 更新UI状态
            self.run_btn.setEnabled(True)
            self.status_label.setText(f"Dataset loaded: {self.dataset_name}, Length: {len(self.signal_data)}")
        
        except Exception as e:
            self.status_label.setText(f"Error loading dataset: {str(e)}")
            self.signal_data = None
            self.data_loaded = False
            self.run_btn.setEnabled(False)
    
    def plot_signal(self):
        """绘制原始信号"""
        if self.signal_data is None or not self.data_loaded:
            return
        
        # 清除之前的绘图
        self.overview_canvas.axes.clear()
        
        # 绘制时间序列数据
        t = np.arange(len(self.signal_data))
        self.overview_canvas.axes.plot(t, self.signal_data, 'k-')
        
        # 设置适当的x轴范围 - 解决home按钮问题
        self.overview_canvas.axes.set_xlim(0, len(self.signal_data))
        
        self.overview_canvas.axes.set_title(f"Signal Overview: {self.dataset_name}")
        self.overview_canvas.axes.set_xlabel("Time Points")
        self.overview_canvas.axes.set_ylabel("Amplitude")
        self.overview_canvas.fig.tight_layout()
        self.overview_canvas.draw()
    
    def detect_steps(self):
        """检测信号中的台阶"""
        if self.signal_data is None or not self.data_loaded:
            self.status_label.setText("Please load data first")
            return
        
        # 获取台阶检测参数
        detection_params = {
            'min_step_height': self.min_step_height_spin.value(),
            'min_step_width': self.min_step_width_spin.value(),
            'smoothing_width': self.smoothing_width_spin.value(),
            'detection_threshold': self.detection_threshold_spin.value()
        }
        
        try:
            # 检测台阶边界
            self.status_label.setText("Detecting step boundaries...")
            self.step_boundaries = self.detector.detect_steps(self.signal_data, detection_params)
            
            # 获取台阶水平
            self.step_levels = self.detector.get_step_levels(
                self.signal_data, 
                self.step_boundaries
            )
            
            # 判断是否需要合并相似台阶
            if self.merge_steps_checkbox.isChecked():
                merge_method = self.merge_method_combo.currentText()
                
                if merge_method == "Adjacent Only":
                    level_tolerance = self.level_tolerance_spin.value()
                    self.status_label.setText(f"Merging adjacent steps (tolerance: {level_tolerance})...")
                    self.merged_step_levels = self.detector.merge_similar_steps(self.step_levels, level_tolerance)
                    step_count_text = f"Detected Steps: {len(self.step_levels)} (After merging: {len(self.merged_step_levels)})"
                
                elif merge_method == "Clustering":
                    eps_factor = self.eps_factor_spin.value()
                    self.status_label.setText(f"Using clustering to merge steps (eps factor: {eps_factor})...")
                    self.merged_step_levels = self.detector.merge_steps_clustering(self.step_levels, eps_factor)
                    step_count_text = f"Detected Steps: {len(self.step_levels)} (After clustering: {len(self.merged_step_levels)})"
                
                elif merge_method == "DTW Shape":
                    dtw_threshold = self.dtw_threshold_spin.value()
                    self.status_label.setText(f"Using DTW to merge steps (similarity threshold: {dtw_threshold})...")
                    self.merged_step_levels = self.detector.merge_steps_dtw(self.step_levels, dtw_threshold)
                    step_count_text = f"Detected Steps: {len(self.step_levels)} (After DTW merging: {len(self.merged_step_levels)})"
                    
                elif merge_method == "Adaptive Hybrid":
                    base_tolerance = self.adaptive_base_tolerance_spin.value()
                    noise_factor = self.noise_factor_spin.value()
                    min_confidence = self.min_confidence_spin.value()
                    self.status_label.setText(f"Using adaptive hybrid method to merge steps...")
                    self.merged_step_levels = self.detector.merge_steps_adaptive_hybrid(
                        self.step_levels, 
                        base_tolerance=base_tolerance,
                        noise_factor=noise_factor,
                        min_confidence=min_confidence
                    )
                    step_count_text = f"Detected Steps: {len(self.step_levels)} (After adaptive merging: {len(self.merged_step_levels)})"
                
                current_steps = self.merged_step_levels
            else:
                self.merged_step_levels = []
                current_steps = self.step_levels
                step_count_text = f"Detected Steps: {len(self.step_levels)}"
            
            # 更新绘图
            self.plot_step_results(current_steps)
            
            # 更新状态
            self.steps_label.setText(step_count_text)
            self.status_label.setText(f"Analysis complete: {step_count_text}")
            
            # 重置当前台阶索引
            self.current_step_index = -1
            self.saved_steps = set()
            
            # 更新台阶跳转控件
            self.step_jump_spin.setMaximum(len(current_steps))
            self.step_jump_btn.setEnabled(len(current_steps) > 0)
            
           # 启用保存按钮
            self.save_all_results_btn.setEnabled(True)

            self.mark_all_btn.setEnabled(True)
            self.view_marked_only_checkbox.setEnabled(False)  # Disable until steps are marked
            self.marked_steps.clear()  # Clear any existing marks
            
            # 如果有台阶，自动选择第一个
            if current_steps:
                self.goto_next_step()
            
        except Exception as e:
            self.status_label.setText(f"Error during analysis: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def plot_step_results(self, step_levels):
        """绘制台阶检测结果，标记被筛选的台阶"""
        if not step_levels or not self.data_loaded:
            return
        
        # 清除之前的绘图
        self.overview_canvas.axes.clear()
        
        # 绘制时间序列数据
        t = np.arange(len(self.signal_data))
        self.overview_canvas.axes.plot(t, self.signal_data, 'k-', label='Original Signal')
        
        # 绘制检测到的台阶
        for i, step in enumerate(step_levels):
            start_idx = step['start']
            end_idx = step['end']
            level = step['level']
            
            # 确定颜色，被标记的台阶使用不同颜色
            is_marked = i in self.marked_steps
            line_color = 'orange' if is_marked else 'r'
            line_width = 2.5 if is_marked else 2
            line_style = '-' if is_marked else '--'
            
            # 绘制台阶水平线
            self.overview_canvas.axes.hlines(
                level, start_idx, end_idx, 
                colors=line_color, linestyles=line_style, linewidth=line_width
            )
            
            # 如果台阶被标记，在台阶区域添加颜色填充
            if is_marked:
                self.overview_canvas.axes.axvspan(
                    start_idx, end_idx, 
                    alpha=0.15, color='orange',
                    label='Marked Step' if i == 0 else ""  # 只在图例中添加一次
                )
            
            # 在台阶中心添加标签 - 只有在显示台阶序号的复选框被选中时才添加
            if self.show_step_numbers_checkbox.isChecked():
                mid_point = (start_idx + end_idx) // 2
                if end_idx - start_idx > 50:  # 只为较长台阶添加标签
                    label_text = f"{i+1}"
                    
                    # 如果只有一个零点或被标记，添加特殊标记
                    if step.get('zero_crossings', 0) <= 1:
                        label_text += "*"  # 标记只有一个零点的台阶
                    if is_marked:
                        label_text += " ◆"  # 标记被筛选的台阶
                    
                    self.overview_canvas.axes.text(
                        mid_point, level, 
                        label_text, 
                        horizontalalignment='center', 
                        verticalalignment='bottom',
                        color='blue' if not is_marked else 'darkorange',
                        fontsize=9,
                        fontweight='bold' if is_marked else 'normal'
                    )
        
        # 标记台阶边界 - 只有在显示分割线的复选框被选中时才添加，且使用更淡的样式
        if self.show_dividers_checkbox.isChecked():
            if self.merge_steps_checkbox.isChecked() and self.merged_step_levels:
                # 只绘制合并后的边界，使用更淡的线条
                for step in self.merged_step_levels:
                    self.overview_canvas.axes.axvline(step['start'], color='g', linestyle=':', alpha=0.3)  # 降低透明度，改为点线
                    self.overview_canvas.axes.axvline(step['end'], color='g', linestyle=':', alpha=0.3)    # 降低透明度，改为点线
            else:
                # 绘制所有原始边界，使用更淡的线条
                for boundary in self.step_boundaries:
                    self.overview_canvas.axes.axvline(boundary, color='g', linestyle=':', alpha=0.3)  # 降低透明度，改为点线
        
        # 设置标题根据是否合并台阶而不同
        title = f"Step Detection Results"
        if self.merge_steps_checkbox.isChecked() and step_levels == self.merged_step_levels:
            title += " (Similar steps have been merged)"
        if self.marked_steps:
            title += f" - {len(self.marked_steps)} steps marked"
        title += f": {self.dataset_name}"
        
        # 添加说明（只有在显示台阶序号时才需要）
        if self.show_step_numbers_checkbox.isChecked():
            y_pos = 0.02
            if any(step.get('zero_crossings', 0) <= 1 for step in step_levels):
                self.overview_canvas.fig.text(0.02, y_pos, "* Steps with only one zero crossing", fontsize=8)
                y_pos += 0.03
            
            if self.marked_steps:
                self.overview_canvas.fig.text(0.02, y_pos, "◆ Marked steps", fontsize=8)
        
        # 设置适当的x轴范围 - 解决home按钮问题
        self.overview_canvas.axes.set_xlim(0, len(self.signal_data))
        
        self.overview_canvas.axes.set_title(title)
        self.overview_canvas.axes.set_xlabel("Time Points")
        self.overview_canvas.axes.set_ylabel("Amplitude")
        self.overview_canvas.axes.legend()
        self.overview_canvas.fig.tight_layout()
        self.overview_canvas.draw()

    def update_threshold_from_slider(self, value):
        """从滑动条更新阈值微调框"""
        threshold = value / 10.0  # 将滑动条值转换为实际阈值
        # 避免信号循环
        self.detection_threshold_spin.blockSignals(True)
        self.detection_threshold_spin.setValue(threshold)
        self.detection_threshold_spin.blockSignals(False)

    def update_slider_from_threshold(self, value):
        """从微调框更新滑动条"""
        slider_value = int(value * 10)  # 将阈值转换为滑动条值
        # 避免信号循环
        self.threshold_slider.blockSignals(True)
        self.threshold_slider.setValue(slider_value)
        self.threshold_slider.blockSignals(False)

    def update_display_settings(self):
        """当显示设置改变时更新图表"""
        # 重新绘制当前视图
        steps = self.get_current_steps()
        if steps:
            self.plot_step_results(steps)
            if self.current_step_index >= 0:
                self.display_step_details(self.current_step_index)
    
    def get_current_steps(self):
        """获取当前使用的台阶集"""
        if self.merge_steps_checkbox.isChecked() and self.merged_step_levels:
            return self.merged_step_levels
        return self.step_levels
    
    def goto_step(self):
        """跳转到指定编号的台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            self.status_label.setText("No steps detected")
            return
        
        # 获取请求的台阶索引（索引从0开始，所以需要减1）
        requested_index = self.step_jump_spin.value() - 1
        
        # 检查请求的索引是否有效
        if 0 <= requested_index < len(steps):
            self.current_step_index = requested_index
            self.display_step_details(self.current_step_index)
            self.status_label.setText(f"Jumped to step {requested_index + 1}/{len(steps)}")
            
            # 更新按钮状态
            self.prev_step_btn.setEnabled(self.current_step_index > 0)
            self.next_step_btn.setEnabled(self.current_step_index < len(steps) - 1)
            self.save_step_btn.setEnabled(True)
            self.skip_step_btn.setEnabled(True)
        else:
            self.status_label.setText(f"Invalid step number. Valid range: 1-{len(steps)}")
    
    def goto_next_step(self):
        """跳转到下一个台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            return
        
        if self.current_step_index < len(steps) - 1:
            self.current_step_index += 1
            self.display_step_details(self.current_step_index)
            self.status_label.setText(f"Viewing step {self.current_step_index + 1} of {len(steps)}")
            
            # 更新按钮状态
            self.prev_step_btn.setEnabled(self.current_step_index > 0)
            self.next_step_btn.setEnabled(self.current_step_index < len(steps) - 1)
            self.save_step_btn.setEnabled(True)
            self.skip_step_btn.setEnabled(True)
        else:
            self.status_label.setText("Already at the last step")
    
    def goto_previous_step(self):
        """跳转到上一个台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            return
        
        if self.current_step_index > 0:
            self.current_step_index -= 1
            self.display_step_details(self.current_step_index)
            self.status_label.setText(f"Viewing step {self.current_step_index + 1} of {len(steps)}")
            
            # 更新按钮状态
            self.prev_step_btn.setEnabled(self.current_step_index > 0)
            self.next_step_btn.setEnabled(self.current_step_index < len(steps) - 1)
            self.save_step_btn.setEnabled(True)
            self.skip_step_btn.setEnabled(True)
        else:
            self.status_label.setText("Already at the first step")


    def mark_filtered_steps(self):
        """标记满足筛选条件的所有台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            self.status_label.setText("No steps to mark")
            return
        
        # Get filter values - empty text means no filter
        rms_min = self.rms_min_filter.value() if self.rms_min_filter.text() != "" else None
        rms_max = self.rms_max_filter.value() if self.rms_max_filter.text() != "" else None
        data_range_min = self.data_range_min_filter.value() if self.data_range_min_filter.text() != "" else None
        data_range_max = self.data_range_max_filter.value() if self.data_range_max_filter.text() != "" else None
        
        # Clear existing marks if any filters are active
        if any(x is not None for x in [rms_min, rms_max, data_range_min, data_range_max]):
            self.marked_steps.clear()
        
        # Count how many steps will be marked
        marked_count = 0
        
        # Mark steps that pass the filters
        for i, step in enumerate(steps):
            rms = step['rms']
            data_range = step.get('data_range', np.max(step['data']) - np.min(step['data']))
            
            # Check if step passes all filters
            passes_filters = True
            
            if rms_min is not None and rms < rms_min:
                passes_filters = False
            if rms_max is not None and rms > rms_max:
                passes_filters = False
            if data_range_min is not None and data_range < data_range_min:
                passes_filters = False
            if data_range_max is not None and data_range > data_range_max:
                passes_filters = False
            
            if passes_filters:
                self.marked_steps.add(i)
                marked_count += 1
        
        # Enable the view marked only checkbox if we have marked steps
        self.view_marked_only_checkbox.setEnabled(len(self.marked_steps) > 0)
        
        # Update the display to highlight marked steps
        self.plot_step_results(steps)
        
        # Show status message
        if marked_count > 0:
            self.status_label.setText(f"Marked {marked_count} steps based on filter criteria")
        else:
            self.status_label.setText("No steps match the filter criteria")

    def toggle_marked_only_view(self, state):
        """切换是否只显示标记的台阶"""
        self.viewing_marked_only = state == Qt.CheckState.Checked.value
        
        # If turning on marked only view, go to the first marked step
        if self.viewing_marked_only and self.marked_steps:
            # Find the first marked step
            self.goto_first_marked_step()
        else:
            # If turning off, redisplay current step
            if self.current_step_index >= 0:
                self.display_step_details(self.current_step_index)

    def goto_first_marked_step(self):
        """跳转到第一个标记的台阶"""
        if not self.marked_steps:
            return
        
        # Find the first marked step index (smallest index)
        first_marked = min(self.marked_steps)
        self.current_step_index = first_marked
        self.display_step_details(first_marked)
        self.status_label.setText(f"Viewing marked step {first_marked + 1}")
        
        # Update button states
        self.update_navigation_buttons()

    def goto_next_step(self):
        """跳转到下一个台阶，如果只查看标记台阶则只跳转到标记的台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            return
        
        if self.viewing_marked_only and self.marked_steps:
            # Find the next marked step after current
            next_marked = None
            for idx in sorted(self.marked_steps):
                if idx > self.current_step_index:
                    next_marked = idx
                    break
            
            if next_marked is not None:
                self.current_step_index = next_marked
                self.display_step_details(next_marked)
                self.status_label.setText(f"Viewing marked step {self.current_step_index + 1}")
            else:
                self.status_label.setText("Already at the last marked step")
        else:
            # Original behavior for all steps
            if self.current_step_index < len(steps) - 1:
                self.current_step_index += 1
                self.display_step_details(self.current_step_index)
                self.status_label.setText(f"Viewing step {self.current_step_index + 1} of {len(steps)}")
            else:
                self.status_label.setText("Already at the last step")
        
        # Update navigation button states
        self.update_navigation_buttons()

    def goto_previous_step(self):
        """跳转到上一个台阶，如果只查看标记台阶则只跳转到标记的台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            return
        
        if self.viewing_marked_only and self.marked_steps:
            # Find the previous marked step before current
            prev_marked = None
            for idx in sorted(self.marked_steps, reverse=True):
                if idx < self.current_step_index:
                    prev_marked = idx
                    break
            
            if prev_marked is not None:
                self.current_step_index = prev_marked
                self.display_step_details(prev_marked)
                self.status_label.setText(f"Viewing marked step {self.current_step_index + 1}")
            else:
                self.status_label.setText("Already at the first marked step")
        else:
            # Original behavior for all steps
            if self.current_step_index > 0:
                self.current_step_index -= 1
                self.display_step_details(self.current_step_index)
                self.status_label.setText(f"Viewing step {self.current_step_index + 1} of {len(steps)}")
            else:
                self.status_label.setText("Already at the first step")
        
        # Update navigation button states
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        """更新导航按钮的状态，考虑是否只查看标记台阶"""
        steps = self.get_current_steps()
        
        if not steps:
            self.prev_step_btn.setEnabled(False)
            self.next_step_btn.setEnabled(False)
            return
        
        if self.viewing_marked_only and self.marked_steps:
            # 检查是否有前一个标记的台阶
            has_prev = any(idx < self.current_step_index for idx in self.marked_steps)
            # 检查是否有后一个标记的台阶
            has_next = any(idx > self.current_step_index for idx in self.marked_steps)
            
            self.prev_step_btn.setEnabled(has_prev)
            self.next_step_btn.setEnabled(has_next)
        else:
            # 原始按钮状态逻辑
            self.prev_step_btn.setEnabled(self.current_step_index > 0)
            self.next_step_btn.setEnabled(self.current_step_index < len(steps) - 1)
        
    def display_step_details(self, step_index):
        """显示台阶详细信息"""
        if step_index < 0:
            return
        
        steps = self.get_current_steps()
        
        if not steps or step_index >= len(steps):
            return
        
        step = steps[step_index]
        
        # 高亮显示当前台阶在总览中
        self.highlight_current_step(step_index)
        
        # 显示台阶信息
        info_text = f"Step Number: {step_index + 1}\n"
        info_text += f"Start Index: {step['start']}\n"
        info_text += f"End Index: {step['end']}\n"
        info_text += f"Duration: {step['duration']} points\n"
        info_text += f"Stable Region: {step['stable_start']} - {step['stable_end']} ({step['stable_duration']} points)\n"
        info_text += f"Average Level: {step['level']:.6f}\n"
        info_text += f"RMS: {step['rms']:.6f}\n"
        info_text += f"Data Range: {step['data_range']:.6f}\n"  # 添加极差信息
        
        # 添加二阶导数零点信息
        if 'zero_crossings' in step:
            info_text += f"2nd Derivative Zero Crossings: {step['zero_crossings']}"
            if step['zero_crossings'] <= 1:
                info_text += " (will be merged)"
            info_text += "\n"
            
            # 显示重要零点位置及权重
            if 'zero_positions' in step and step['zero_positions']:
                info_text += "Important Zero Points:\n"
                for i, zc in enumerate(step['zero_positions']):
                    if i < 5:  # 最多显示5个重要零点
                        info_text += f"  - Position: {zc['position']}, Weight: {zc['weight']:.2f}\n"
                if len(step['zero_positions']) > 5:
                    info_text += f"  (plus {len(step['zero_positions']) - 5} more...)\n"
        
        info_text += f"Status: {'Saved' if step_index in self.saved_steps else 'Not Saved'}"
        
        self.step_info_text.setText(info_text)
        
        # 绘制台阶详情图
        self.plot_step_detail(step)
        
        # 绘制周围台阶图
        self.plot_nearby_steps(step_index)
    
    def highlight_current_step(self, step_index):
        """在总览中高亮显示当前台阶"""
        steps = self.get_current_steps()
        
        if not steps or step_index >= len(steps):
            return
        
        # 重绘总览图
        self.plot_step_results(steps)
        
        # 获取当前台阶信息
        step = steps[step_index]
        
        # 高亮显示当前台阶
        self.overview_canvas.axes.axvspan(
            step['start'], step['end'], 
            alpha=0.3, color='yellow'
        )
        self.overview_canvas.draw()
    
    def plot_step_detail(self, step):
        """Draw step detail view, merging data range and stable region display"""
        # Clear previous plot
        self.step_detail_canvas.axes.clear()
        
        # Select data range to display (add margins)
        start_idx = max(0, step['start'] - 10)
        end_idx = min(len(self.signal_data), step['end'] + 10)
        
        # Generate x coordinates
        t = np.arange(start_idx, end_idx)
        
        # Get data
        data = self.signal_data[start_idx:end_idx]
        
        # Draw data points
        self.step_detail_canvas.axes.plot(t, data, 'k.-', label='Signal')
        
        # Calculate and plot second derivative using LoG method
        if len(data) > 5:  # Ensure enough points for derivative calculation
            # Gaussian smoothing
            sigma = 2.0
            smoothed = ndimage.gaussian_filter1d(data, sigma)
            
            # Calculate second derivative (Laplacian)
            laplacian = ndimage.laplace(smoothed)
            
            # Normalize for display with original signal
            norm_factor = np.max(np.abs(data)) / np.max(np.abs(laplacian)) if np.max(np.abs(laplacian)) > 0 else 1
            norm_laplacian = laplacian * norm_factor
            
            # Plot second derivative
            self.step_detail_canvas.axes.plot(t, norm_laplacian, 'g-', alpha=0.6, linewidth=1, label='2nd Derivative (scaled)')
            
            # Find and mark zero crossings
            zero_crossings = []
            weights = []
            
            for i in range(1, len(laplacian)):
                if (laplacian[i-1] < 0 and laplacian[i] >= 0) or \
                (laplacian[i-1] >= 0 and laplacian[i] < 0):
                    # Calculate precise zero position (linear interpolation)
                    if laplacian[i] != laplacian[i-1]:
                        t_val = -laplacian[i-1] / (laplacian[i] - laplacian[i-1])
                        zero_pos = i-1 + t_val
                    else:
                        zero_pos = i-0.5
                    
                    # Use first derivative magnitude as weight
                    grad = np.gradient(smoothed)
                    local_range = slice(max(0, i-5), min(len(grad), i+5))
                    max_grad = np.max(np.abs(grad[local_range]))
                    
                    zero_crossings.append(int(zero_pos))
                    weights.append(max_grad)
            
            # Normalize weights
            if weights:
                max_weight = max(weights) if max(weights) > 0 else 1
                weights = [w / max_weight for w in weights]
            
            # Draw markers at zero crossings, larger markers for higher weights
            for i, (zc, weight) in enumerate(zip(zero_crossings, weights)):
                marker_size = 5 + 10 * weight  # Adjust marker size based on weight
                zc_t = t[min(zc, len(t)-1)]  # Ensure valid index
                self.step_detail_canvas.axes.axvline(zc_t, color='g', linestyle='--', alpha=0.4 * weight)
                self.step_detail_canvas.axes.plot(zc_t, norm_laplacian[min(zc, len(norm_laplacian)-1)], 'go', 
                                        markersize=marker_size, alpha=0.7)
                
                # Add weight label
                if weight > 0.5:  # Only label important zero points
                    y_pos = norm_laplacian[min(zc, len(norm_laplacian)-1)]
                    self.step_detail_canvas.axes.text(zc_t, y_pos, f"{weight:.2f}", 
                                            fontsize=8, color='green',
                                            horizontalalignment='left',
                                            verticalalignment='bottom')
            
            # 添加三阶导数的计算和绘制
            # 如果稳定区域有足够的数据点，计算并绘制三阶导数
            stable_start = step['stable_start'] 
            stable_end = step['stable_end']
            
            if stable_end > stable_start and stable_end - stable_start > 5:
                # 提取稳定区域数据
                stable_data = self.signal_data[stable_start:stable_end+1]
                stable_t = np.arange(stable_start, stable_end+1)
                
                # 应用高斯平滑
                stable_smoothed = ndimage.gaussian_filter1d(stable_data, sigma)
                
                # 计算三阶导数
                first_deriv = np.gradient(stable_smoothed)
                second_deriv = np.gradient(first_deriv)
                third_deriv = np.gradient(second_deriv)
                
                # 归一化三阶导数以便在同一个图上显示
                if np.max(np.abs(third_deriv)) > 0:
                    scale_factor = np.max(np.abs(data)) / np.max(np.abs(third_deriv)) * 0.5
                    scaled_third_deriv = third_deriv * scale_factor
                    
                    # 绘制三阶导数曲线
                    self.step_detail_canvas.axes.plot(stable_t, scaled_third_deriv + np.mean(stable_data), 
                                                    'r-', linewidth=1.5, label='3rd Derivative (scaled)')
                    
                    # 标记已存储的三阶导数零点
                    if 'third_zero_crossings' in step and step['third_zero_crossings']:
                        for zero_idx, zero_pos in enumerate(step['third_zero_crossings']):
                            if zero_idx == 1 or zero_idx == len(step['third_zero_crossings']) - 2:
                                # 用不同颜色标记第二个和倒数第二个零点（如果有4个以上的零点）
                                if len(step['third_zero_crossings']) >= 4:
                                    marker_color = 'yellow'
                                    marker_size = 8
                                    self.step_detail_canvas.axes.axvline(zero_pos, color='yellow', linestyle='-', alpha=0.5)
                                    label = "2nd" if zero_idx == 1 else "-2nd"
                                else:
                                    marker_color = 'red'
                                    marker_size = 6
                                    label = str(zero_idx + 1)
                            else:
                                marker_color = 'red'
                                marker_size = 6
                                label = str(zero_idx + 1)
                                
                            # 找到最接近的点来获取y值
                            if zero_pos >= stable_start and zero_pos <= stable_end:
                                rel_pos = zero_pos - stable_start
                                if rel_pos < len(scaled_third_deriv):
                                    zero_y = scaled_third_deriv[rel_pos] + np.mean(stable_data)
                                    self.step_detail_canvas.axes.plot(zero_pos, zero_y, 'o', 
                                                                    color=marker_color, markersize=marker_size)
                                    # 添加标签
                                    self.step_detail_canvas.axes.text(zero_pos, zero_y, label, 
                                                                    fontsize=8, color=marker_color,
                                                                    horizontalalignment='center',
                                                                    verticalalignment='bottom')
        
        # Draw step region
        self.step_detail_canvas.axes.axvspan(
            step['start'], step['end'], 
            alpha=0.2, color='green',
            label='Step Region'
        )
        
        # Calculate data range in stable region
        stable_min = np.min(step['stable_data'])
        stable_max = np.max(step['stable_data'])
        
        # Draw stable region (merged with data range display)
        # 根据是否使用了三阶导数优化来设置不同的颜色
        stable_color = 'purple' if step.get('third_deriv_refined', False) else 'blue'
        stable_label = 'Refined Stable Region (3rd deriv)' if step.get('third_deriv_refined', False) else 'Stable Region'
        
        rect = plt.Rectangle(
            (step['stable_start'], stable_min),  # Bottom-left corner
            step['stable_end'] - step['stable_start'],  # Width
            stable_max - stable_min,  # Height
            fill=True,
            color=stable_color,  # 根据是否经过三阶导数优化使用不同颜色
            alpha=0.3,
            label=stable_label  # 根据是否经过三阶导数优化使用不同标签
        )
        self.step_detail_canvas.axes.add_patch(rect)
        
        # Draw horizontal lines at min and max values
        self.step_detail_canvas.axes.hlines(
            stable_min, step['stable_start'], step['stable_end'],
            colors='orange', linestyles='-', linewidth=1.5
        )
        self.step_detail_canvas.axes.hlines(
            stable_max, step['stable_start'], step['stable_end'],
            colors='orange', linestyles='-', linewidth=1.5
        )
        
        # Add annotation text
        mid_x = (step['stable_start'] + step['stable_end']) / 2
        self.step_detail_canvas.axes.text(
            mid_x, stable_max,
            f"Max: {stable_max:.4f}",
            fontsize=8, color='orange',
            horizontalalignment='center',
            verticalalignment='bottom'
        )
        self.step_detail_canvas.axes.text(
            mid_x, stable_min,
            f"Min: {stable_min:.4f}",
            fontsize=8, color='orange',
            horizontalalignment='center',
            verticalalignment='top'
        )
        
        # Draw step mean level line
        self.step_detail_canvas.axes.hlines(
            step['level'], step['start'], step['end'], 
            colors='r', linestyles='--', linewidth=2,
            label=f'Mean Level: {step["level"]:.4f}'
        )
        
        # Add zero crossings info
        zero_crossings_info = ""
        if 'zero_crossings' in step:
            zero_crossings_info = f" (2nd Derivative Zero Crossings: {step['zero_crossings']})"
            if step['zero_crossings'] <= 1:
                zero_crossings_info += " *"
        
        # 添加三阶导数优化信息
        third_deriv_info = ""
        if step.get('third_deriv_refined', False):
            third_deriv_info = " - Using 3rd Derivative Refined Region"
        
        # Add title and axis labels
        self.step_detail_canvas.axes.set_title(f"Step {self.current_step_index + 1} Detail{zero_crossings_info}{third_deriv_info}")
        self.step_detail_canvas.axes.set_xlabel("Time Points")
        self.step_detail_canvas.axes.set_ylabel("Amplitude")
        
        # Add grid lines
        self.step_detail_canvas.axes.grid(True, linestyle='--', alpha=0.7)
        
        # Add legend
        self.step_detail_canvas.axes.legend(loc='best', fontsize=8)
        
        # Adjust layout
        self.step_detail_canvas.fig.tight_layout()
        self.step_detail_canvas.draw()
    
    def update_nearby_steps_display(self):
        """根据用户设置更新 nearby steps 的显示范围"""
        if self.current_step_index >= 0:
            self.display_step_details(self.current_step_index)


    # 修改 plot_nearby_steps 方法，使用 nearby_steps_range_spin 的值：
    def plot_nearby_steps(self, step_index):
        """显示当前台阶附近的台阶"""
        steps = self.get_current_steps()
        
        if not steps or step_index >= len(steps):
            return
        
        # 清除之前的绘图
        self.nearby_steps_canvas.axes.clear()
        
        # 使用输入框中的值确定显示范围
        display_range = self.nearby_steps_range_spin.value()
        
        # 确定附近台阶的显示范围
        total_steps = len(steps)
        start_step = max(0, step_index - display_range)
        end_step = min(total_steps, step_index + display_range + 1)
        
        # 平衡显示范围（如果可能）
        display_count = 2 * display_range + 1  # 理想显示数（前后范围加当前台阶）
        if start_step == 0 and end_step < total_steps:
            end_step = min(total_steps, start_step + display_count)
        elif end_step == total_steps and start_step > 0:
            start_step = max(0, end_step - display_count)
        
        # 显示所有台阶，如果总数小于显示范围
        if total_steps <= display_count:
            start_step = 0
            end_step = total_steps
        
        # 以下与原始函数相同
        # 定义绘图区域
        if end_step - start_step > 0:
            first_step = steps[start_step]
            last_step = steps[end_step - 1]
            
            # 稍微扩展视图
            start_idx = max(0, first_step['start'] - 20)
            end_idx = min(len(self.signal_data), last_step['end'] + 20)
            
            # 绘制原始信号
            t = np.arange(start_idx, end_idx)
            self.nearby_steps_canvas.axes.plot(t, self.signal_data[start_idx:end_idx], 'k-', label='Signal')
            
            # 绘制每个台阶
            for i in range(start_step, end_step):
                step = steps[i]
                
                # 根据零点数量确定颜色
                # 只有一个零点的台阶用淡紫色
                if step.get('zero_crossings', 0) <= 1:
                    color = 'purple' if i == step_index else 'magenta'
                else:
                    color = 'red' if i == step_index else 'blue'
                
                alpha = 0.8 if i == step_index else 0.5
                width = 2 if i == step_index else 1
                
                # 绘制台阶水平线
                self.nearby_steps_canvas.axes.hlines(
                    step['level'], step['start'], step['end'], 
                    colors=color, linestyles='--', linewidth=width, alpha=alpha
                )
                
                # 标记台阶边界
                self.nearby_steps_canvas.axes.axvline(step['start'], color='green', linestyle='-', alpha=0.3)
                self.nearby_steps_canvas.axes.axvline(step['end'], color='green', linestyle='-', alpha=0.3)
                
                # 高亮当前台阶
                if i == step_index:
                    self.nearby_steps_canvas.axes.axvspan(
                        step['start'], step['end'], 
                        alpha=0.2, color='yellow'
                    )
                
                # 标记每个台阶
                mid_point = (step['start'] + step['end']) // 2
                if step['end'] - step['start'] > 30:  # 只标记较长的台阶
                    # 构建标签文本
                    label_text = f"{i+1}"
                    
                    # 如果只有一个零点，添加特殊标记
                    if step.get('zero_crossings', 0) <= 1:
                        label_text += "*"  # 标记只有一个零点的台阶
                    
                    self.nearby_steps_canvas.axes.text(
                        mid_point, step['level'], 
                        label_text, 
                        horizontalalignment='center', 
                        verticalalignment='bottom',
                        color=color,
                        fontsize=8
                    )
                
                # 标记重要的零点
                if 'zero_positions' in step and step['zero_positions']:
                    for zc in step['zero_positions']:
                        if zc['weight'] > 0.5:  # 只显示权重大的零点
                            self.nearby_steps_canvas.axes.axvline(
                                zc['position'], color='green', linestyle=':', 
                                alpha=0.3 + 0.5 * zc['weight'], linewidth=1
                            )
            
            # 添加标题和坐标轴标签
            displayed_count = end_step - start_step
            title = f"Steps {start_step+1} to {end_step} ({displayed_count} steps, Current: {step_index+1})"
            
            self.nearby_steps_canvas.axes.set_title(title)
            self.nearby_steps_canvas.axes.set_xlabel("Time Points")
            self.nearby_steps_canvas.axes.set_ylabel("Amplitude")
            
            # 添加图例
            lines = []
            labels = []
            legend_items = [
                ('Signal', 'k-'),
                ('Current Step', 'r--'),
                ('Other Steps', 'b--'),
                ('Steps with ≤1 Zero Crossing', 'm--')
            ]
            
            for label, style in legend_items:
                if 'k' in style:
                    lines.append(plt.Line2D([0], [0], color='k', linestyle='-'))
                elif 'r' in style:
                    lines.append(plt.Line2D([0], [0], color='r', linestyle='--'))
                elif 'b' in style:
                    lines.append(plt.Line2D([0], [0], color='b', linestyle='--'))
                elif 'm' in style:
                    lines.append(plt.Line2D([0], [0], color='m', linestyle='--'))
                labels.append(label)
            
            self.nearby_steps_canvas.axes.legend(lines, labels, loc='best', fontsize=8)
            
            # 添加额外说明
            if any(step.get('zero_crossings', 0) <= 1 for step in steps[start_step:end_step]):
                y_pos = 0.02
                self.nearby_steps_canvas.fig.text(0.02, y_pos, "* Steps with only one zero crossing will be merged", fontsize=8)
            
            # 添加网格
            self.nearby_steps_canvas.axes.grid(True, linestyle='--', alpha=0.3)
            
            # 调整布局
            self.nearby_steps_canvas.fig.tight_layout()
            self.nearby_steps_canvas.draw()
    
    def save_current_step(self):
        """保存当前台阶信息"""
        if self.current_step_index < 0:
            self.status_label.setText("No step selected")
            return
        
        steps = self.get_current_steps()
        
        if not steps or self.current_step_index >= len(steps):
            self.status_label.setText("Invalid step index")
            return
        
        # 记录已保存台阶
        self.saved_steps.add(self.current_step_index)
        
        # 询问保存位置
        folder_path = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        
        if not folder_path:
            return
        
        try:
            step = steps[self.current_step_index]
            step_number = self.current_step_index + 1
            
            # 构建文件名基础部分
            base_filename = f"step_{step_number}"
            
            # 保存台阶信息到CSV
            info_file = os.path.join(folder_path, f"{base_filename}_info.csv")
            with open(info_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Parameter", "Value"])
                writer.writerow(["Step Number", step_number])
                writer.writerow(["Start Index", step['start']])
                writer.writerow(["End Index", step['end']])
                writer.writerow(["Duration", step['duration']])
                writer.writerow(["Average Level", step['level']])
                writer.writerow(["RMS", step['rms']])
                
                # 添加二阶导数零点信息
                if 'zero_crossings' in step:
                    writer.writerow(["2nd Derivative Zero Crossings", step['zero_crossings']])
                
                # 添加重要零点信息
                if 'zero_positions' in step and step['zero_positions']:
                    for i, zc in enumerate(step['zero_positions']):
                        writer.writerow([f"Zero Point {i+1} Position", zc['position']])
                        writer.writerow([f"Zero Point {i+1} Weight", zc['weight']])
            
            # 保存台阶原始数据到CSV
            data_file = os.path.join(folder_path, f"{base_filename}_data.csv")
            with open(data_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Step Number", "Data Point"])
                for value in step['data']:
                    writer.writerow([step_number, value])
            
            self.status_label.setText(f"Step {step_number} saved to {folder_path}")
            
            # 更新UI显示
            self.display_step_details(self.current_step_index)
        
        except Exception as e:
            self.status_label.setText(f"Error saving step: {str(e)}")
    
    def skip_current_step(self):
        """跳过当前台阶，移动到下一个"""
        if self.current_step_index < 0:
            return
        
        self.goto_next_step()
    
    def save_all_results(self):
        """保存所有检测到的台阶结果，可根据RMS和数据范围进行过滤"""
        steps = self.get_current_steps()
        
        if not steps:
            self.status_label.setText("No steps to save")
            return
        
        # Get filter values - empty text means no filter
        rms_min = self.rms_min_filter.value() if self.rms_min_filter.text() != "" else None
        rms_max = self.rms_max_filter.value() if self.rms_max_filter.text() != "" else None
        data_range_min = self.data_range_min_filter.value() if self.data_range_min_filter.text() != "" else None
        data_range_max = self.data_range_max_filter.value() if self.data_range_max_filter.text() != "" else None
        
        # Apply filters to steps
        filtered_steps = []
        for step in steps:
            rms = step['rms']
            data_range = step.get('data_range', np.max(step['data']) - np.min(step['data']))
            
            # Check if step passes all filters
            passes_filters = True
            
            if rms_min is not None and rms < rms_min:
                passes_filters = False
            if rms_max is not None and rms > rms_max:
                passes_filters = False
            if data_range_min is not None and data_range < data_range_min:
                passes_filters = False
            if data_range_max is not None and data_range > data_range_max:
                passes_filters = False
            
            if passes_filters:
                filtered_steps.append(step)
        
        # Check if any steps passed the filters
        if not filtered_steps:
            self.status_label.setText("No steps match the filter criteria")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Filtered Results", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Collect all current processing parameters
            detection_params = {
                'min_step_height': self.min_step_height_spin.value(),
                'min_step_width': self.min_step_width_spin.value(),
                'smoothing_width': self.smoothing_width_spin.value(),
                'detection_threshold': self.detection_threshold_spin.value(),
                'merge_steps': self.merge_steps_checkbox.isChecked()
            }
            
            # Add merge method parameters if merging is enabled
            if self.merge_steps_checkbox.isChecked():
                merge_method = self.merge_method_combo.currentText()
                detection_params['merge_method'] = merge_method
                
                if merge_method == "Adjacent Only":
                    detection_params['level_tolerance'] = self.level_tolerance_spin.value()
                elif merge_method == "Clustering":
                    detection_params['eps_factor'] = self.eps_factor_spin.value()
                elif merge_method == "DTW Shape":
                    detection_params['dtw_threshold'] = self.dtw_threshold_spin.value()
                elif merge_method == "Adaptive Hybrid":
                    detection_params['base_tolerance'] = self.adaptive_base_tolerance_spin.value()
                    detection_params['noise_factor'] = self.noise_factor_spin.value()
                    detection_params['min_confidence'] = self.min_confidence_spin.value()
            
            # 1. Save step information file
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write file header with metadata
                writer.writerow(["Step Detection Results - Step Information"])
                writer.writerow(["Generated on", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Source File", self.current_file_path or "Unknown"])
                writer.writerow(["Dataset", self.dataset_name or "Unknown"])
                writer.writerow(["Signal Length", len(self.signal_data) if self.signal_data is not None else 0])
                writer.writerow([])
                
                # Write detection parameters
                writer.writerow(["DETECTION PARAMETERS"])
                for param, value in detection_params.items():
                    writer.writerow([param, value])
                writer.writerow([])
                
                # Write filter parameters (if any)
                if any(x is not None for x in [rms_min, rms_max, data_range_min, data_range_max]):
                    writer.writerow(["FILTER PARAMETERS"])
                    if rms_min is not None:
                        writer.writerow(["RMS Min", rms_min])
                    if rms_max is not None:
                        writer.writerow(["RMS Max", rms_max])
                    if data_range_min is not None:
                        writer.writerow(["Data Range Min", data_range_min])
                    if data_range_max is not None:
                        writer.writerow(["Data Range Max", data_range_max])
                    writer.writerow([])
                
                writer.writerow(["STEP INFORMATION"])
                writer.writerow(["Total Steps Before Filtering", len(steps)])
                writer.writerow(["Steps After Filtering", len(filtered_steps)])
                writer.writerow([])
                
                # Write detailed step information header
                writer.writerow([
                    "Step Number", "Start Index", "End Index", "Duration", 
                    "Stable Start", "Stable End", "Stable Duration",
                    "Average Level", "RMS", "Data Range", "Zero Crossings",
                    "Third Deriv Refined"
                ])
                
                # Write each step's detailed information
                for i, step in enumerate(filtered_steps):
                    stable_duration = step['stable_end'] - step['stable_start'] + 1
                    
                    row = [
                        i+1, 
                        step['start'], 
                        step['end'], 
                        step['end'] - step['start'],
                        step['stable_start'],
                        step['stable_end'],
                        stable_duration,
                        step['level'], 
                        step['rms'],
                        step['data_range'],
                        step.get('zero_crossings', 0),
                        "Yes" if step.get('third_deriv_refined', False) else "No"
                    ]
                    writer.writerow(row)
            
            # 2. Save step original data file
            data_file_path = file_path.replace('.csv', '_data.csv')
            if data_file_path == file_path:
                data_file_path = file_path + '_data.csv'
            
            with open(data_file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write file header with metadata
                writer.writerow(["Step Detection Results - Original Step Data"])
                writer.writerow(["Generated on", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Source File", self.current_file_path or "Unknown"])
                writer.writerow(["Dataset", self.dataset_name or "Unknown"])
                writer.writerow(["Signal Length", len(self.signal_data) if self.signal_data is not None else 0])
                writer.writerow(["Step Information File", os.path.basename(file_path)])
                writer.writerow([])
                
                # Write step data header
                writer.writerow(["Step Number", "Data Point"])
                
                # Write each step's original data
                for i, step in enumerate(filtered_steps):
                    step_num = i + 1
                    for value in step['data']:
                        writer.writerow([step_num, value])
            
            # Prepare filter info for status message
            filter_info = []
            if rms_min is not None:
                filter_info.append(f"RMS ≥ {rms_min:.6f}")
            if rms_max is not None:
                filter_info.append(f"RMS ≤ {rms_max:.6f}")
            if data_range_min is not None:
                filter_info.append(f"Range ≥ {data_range_min:.6f}")
            if data_range_max is not None:
                filter_info.append(f"Range ≤ {data_range_max:.6f}")
            
            filter_str = ", ".join(filter_info) if filter_info else "no filters"
            results_type = "filtered" if filter_info else "all"
            
            # Update status message
            self.status_label.setText(f"Saved {len(filtered_steps)} {results_type} steps ({filter_str}) to files:\n"
                                    f"1. Step Info: {os.path.basename(file_path)}\n"
                                    f"2. Step Data: {os.path.basename(data_file_path)}")
        
        except Exception as e:
            self.status_label.setText(f"Error saving results: {str(e)}")
            import traceback
            print(traceback.format_exc())  # Print detailed error for debugging


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StepDetectorGUI()
    window.show()
    sys.exit(app.exec())