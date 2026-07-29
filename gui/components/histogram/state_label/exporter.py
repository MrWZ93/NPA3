#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Label Exporter - 一键导出分析数据与图表模块
将原始数据、阶梯序列、HMM 统计指标与高分辨率图形一键保存至指定文件夹
"""

import os
import time
import numpy as np
import pandas as pd


class StateLabelExporter:
    """State Label 分析数据与图像导出器"""

    @staticmethod
    def export_all(target_dir, time_axis, raw_data, hmm_result, state_params, fig, metadata=None):
        """一键导出全部文件至指定文件夹
        
        Args:
            target_dir: 目标文件夹路径
            time_axis: 时间轴数组 (1D)
            raw_data: 原始物理信号数组 (1D)
            hmm_result: HMM 解码结果字典 {'path': ..., 'fitted_trace': ..., 'stats': ..., 'total_duration_sec': ..., 'sampling_rate': ...}
            state_params: 状态参数列表
            fig: matplotlib.figure.Figure 图形对象
            metadata: 额外元数据字典
            
        Returns:
            dict: 导出的文件列表与状态
        """
        if not target_dir:
            return {'success': False, 'message': 'Invalid target directory path.'}
            
        os.makedirs(target_dir, exist_ok=True)
        saved_files = []
        
        try:
            # 1. 导出 CSV 数据文件 (raw_and_fitted_data.csv)
            csv_data_path = os.path.join(target_dir, "raw_and_fitted_data.csv")
            
            df_dict = {
                'Time_s': time_axis,
                'Raw_Signal': raw_data
            }
            
            if hmm_result and 'path' in hmm_result and 'fitted_trace' in hmm_result:
                df_dict['HMM_State_Index'] = hmm_result['path']
                df_dict['HMM_Fitted_Level'] = hmm_result['fitted_trace']
                
            df_data = pd.DataFrame(df_dict)
            df_data.to_csv(csv_data_path, index=False, float_format='%.6f')
            saved_files.append(csv_data_path)
            
            # 2. 导出统计指标 CSV 文件 (state_statistics.csv)
            if hmm_result and 'stats' in hmm_result:
                csv_stats_path = os.path.join(target_dir, "state_statistics.csv")
                stats_list = hmm_result['stats']
                
                stats_rows = []
                for s in stats_list:
                    stats_rows.append({
                        'State_Name': s.get('name', f"State {s['id']+1}"),
                        'Mean_u': s['mean'],
                        'Std_sigma': s['std'],
                        'Total_Time_s': s.get('total_state_sec', 0.0),
                        'Total_Time_ms': s.get('total_state_ms', 0.0),
                        'Occupancy_pct': s.get('occupancy_pct', 0.0),
                        'Event_Count': s.get('num_events', 0),
                        'Avg_Dwell_Time_ms': s.get('avg_dwell_ms', 0.0)
                    })
                    
                df_stats = pd.DataFrame(stats_rows)
                df_stats.to_csv(csv_stats_path, index=False, float_format='%.6f')
                saved_files.append(csv_stats_path)
                
            # 3. 导出状态转换矩阵 CSV 文件 (transition_counts.csv & transition_rates_per_s.csv)
            if hmm_result and 'transition_counts' in hmm_result and 'transition_rates_per_s' in hmm_result:
                tc = hmm_result['transition_counts']
                tr = hmm_result['transition_rates_per_s']
                st_names = [s.get('name', f"State {s['id']+1}") for s in hmm_result.get('stats', [])]
                if len(st_names) == tc.shape[0]:
                    df_tc = pd.DataFrame(tc, index=st_names, columns=st_names)
                    tc_path = os.path.join(target_dir, "transition_counts.csv")
                    df_tc.to_csv(tc_path)
                    saved_files.append(tc_path)
                    
                    df_tr = pd.DataFrame(tr, index=st_names, columns=st_names)
                    tr_path = os.path.join(target_dir, "transition_rates_per_s.csv")
                    df_tr.to_csv(tr_path, float_format='%.4f')
                    saved_files.append(tr_path)
                
            # 3. 导出文本摘要报告 (analysis_summary.txt)
            summary_path = os.path.join(target_dir, "analysis_summary.txt")
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("====================================================\n")
                f.write("          STATE LABEL HMM ANALYSIS REPORT           \n")
                f.write("====================================================\n\n")
                f.write(f"Export Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                if metadata:
                    f.write(f"Source File      : {metadata.get('file_name', 'N/A')}\n")
                    f.write(f"Sampling Rate    : {metadata.get('sampling_rate', 'N/A')} Hz\n")
                    f.write(f"Total Points     : {metadata.get('total_points', 'N/A')}\n")
                    f.write(f"Time Range (s)   : {metadata.get('t_min', 0.0):.4f}s - {metadata.get('t_max', 0.0):.4f}s\n")
                    f.write(f"Param Origin     : {metadata.get('param_source', 'N/A')}\n")
                f.write("\n----------------------------------------------------\n")
                f.write("STATE STATISTICS SUMMARY:\n")
                f.write("----------------------------------------------------\n")
                
                if hmm_result and 'stats' in hmm_result:
                    for s in hmm_result['stats']:
                        f.write(f"[{s.get('name')}]\n")
                        f.write(f"  Mean (u)        : {s['mean']:.6f}\n")
                        f.write(f"  Std (sigma)     : {s['std']:.6f}\n")
                        f.write(f"  Total Time      : {s.get('total_state_sec', 0.0):.4f} s ({s.get('total_state_ms', 0.0):.2f} ms)\n")
                        f.write(f"  Occupancy (%)   : {s.get('occupancy_pct', 0.0):.2f} %\n")
                        f.write(f"  Events Count    : {s.get('num_events', 0)}\n")
                        f.write(f"  Avg Dwell Time  : {s.get('avg_dwell_ms', 0.0):.2f} ms\n\n")
                        
                f.write("====================================================\n")
            saved_files.append(summary_path)
            
            # 4. 导出高分辨率图像与矢量图 (state_label_plot.png & .pdf)
            if fig is not None and hasattr(fig, 'canvas') and fig.canvas is not None:
                png_path = os.path.join(target_dir, "state_label_plot.png")
                pdf_path = os.path.join(target_dir, "state_label_plot.pdf")
                
                fig.canvas.print_figure(png_path, dpi=300, bbox_inches='tight')
                fig.canvas.print_figure(pdf_path, bbox_inches='tight')
                fig.canvas.draw_idle()
                
                saved_files.append(png_path)
                saved_files.append(pdf_path)
                
            return {
                'success': True,
                'target_dir': target_dir,
                'saved_files': saved_files
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error during export execution: {str(e)}"
            }
