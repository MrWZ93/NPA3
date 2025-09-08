#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fitting Manager - 拟合管理器
负责管理高斯拟合功能
"""

import numpy as np
from matplotlib.widgets import RectangleSelector
from scipy.optimize import curve_fit
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from .plot_utils import ColorManager, DataHasher


class FitDataManager:
    """拟合数据管理器，用于在不同的视图之间同步拟合结果"""
    
    def __init__(self):
        self.gaussian_fits = []
        self.fit_regions = []
        self.data_range = None
        self.data_hash = None
    
    def save_fits(self, fits, regions, data_range=None, data_hash=None):
        """保存拟合结果"""
        self.gaussian_fits = [self._copy_fit(fit) for fit in fits]
        self.fit_regions = [(r[0], r[1]) for r in regions if len(r) >= 2] if regions else []
        self.data_range = data_range
        self.data_hash = data_hash
        print(f"Saved {len(self.gaussian_fits)} fits")
    
    def get_fits(self):
        """获取拟合结果"""
        return self.gaussian_fits, self.fit_regions
    
    def has_fits(self):
        """检查是否有拟合结果"""
        has_fits = len(self.gaussian_fits) > 0
        print(f"[FitDataManager] has_fits() = {has_fits}, fit count = {len(self.gaussian_fits)}")
        return has_fits
    
    def clear_fits(self):
        """清除所有拟合结果"""
        print(f"[FitDataManager] Clearing {len(self.gaussian_fits)} fits")
        self.gaussian_fits.clear()
        self.fit_regions.clear()
        self.data_range = None
        self.data_hash = None
        print("[FitDataManager] All fits cleared")
    
    def is_compatible_with_data(self, data_range, data_hash):
        """检查拟合结果是否与当前数据兼容"""
        if self.data_hash is None or data_hash is None:
            return False
        return self.data_hash == data_hash
    
    def _copy_fit(self, fit):
        """复制拟合数据（不包括绘图对象）"""
        return {
            'popt': fit.get('popt'),
            'x_range': fit.get('x_range'),
            'color': fit.get('color')
        }


class FittingManager(QObject):
    """拟合管理器类"""
    
    # 定义信号
    region_selected = pyqtSignal(float, float)
    
    def __init__(self, plot_canvas):
        super().__init__()
        self.plot_canvas = plot_canvas
        
        # 拟合相关变量
        self.gaussian_fits = []
        self.fit_regions = []
        self.highlighted_fit_index = -1
        self.labels_visible = True
        self.fit_info_str = "No fits yet"
        
        # 矩形选择器优化定时器
        self.rect_select_timer = QTimer()
        self.rect_select_timer.setSingleShot(True)
        self.rect_select_timer.setInterval(800)
        self.rect_select_timer.timeout.connect(self._delayed_rect_select)
        self.pending_rect_coords = None
        
        # 拟合数据管理器
        self.shared_fit_data = None
    
    def setup_for_histogram_mode(self):
        """为直方图模式设置拟合功能"""
        if not hasattr(self.plot_canvas, 'ax'):
            return
            
        # 创建矩形选择器
        self.rect_selector = RectangleSelector(
            self.plot_canvas.ax,
            self.on_rect_select,
            useblit=True,
            button=[1],  # 只使用左键
            minspanx=10,
            minspany=10,
            spancoords='pixels',
            interactive=False,
            props=dict(facecolor='red', edgecolor='black', alpha=0.15, fill=True)
        )
    
    def set_shared_fit_data(self, shared_fit_data):
        """设置共享的拟合数据引用"""
        self.shared_fit_data = shared_fit_data
        print(f"Set shared fit data: {shared_fit_data}")
    
    def on_rect_select(self, eclick, erelease):
        """处理矩形选择器的框选区域"""
        try:
            x_min, x_max = sorted([eclick.xdata, erelease.xdata])
            
            # 使用延时定时器来减少卡顿
            self.pending_rect_coords = (x_min, x_max)
            self.rect_select_timer.start()
            
        except Exception as e:
            print(f"Error in rectangle selector: {e}")
            import traceback
            traceback.print_exc()
    
    def _delayed_rect_select(self):
        """延迟处理框选区域"""
        if not self.pending_rect_coords:
            return
            
        x_min, x_max = self.pending_rect_coords
        
        # 发送区域选择信号
        self.region_selected.emit(x_min, x_max)
        
        # 高亮选择区域
        self.highlight_selected_region(x_min, x_max)
        
        # 进行高斯拟合
        self.fit_gaussian_to_selected_region(x_min, x_max)
        
        # 重置坐标
        self.pending_rect_coords = None
    
    def highlight_selected_region(self, x_min, x_max):
        """高亮框选的区域"""
        region = self.plot_canvas.ax.axvspan(x_min, x_max, alpha=0.08, color='green', zorder=0)
        self.fit_regions.append((x_min, x_max, region))
    
    def fit_gaussian_to_selected_region(self, x_min, x_max):
        """对选择的区域进行高斯拟合"""
        try:
            # 获取直方图数据
            if not hasattr(self.plot_canvas, 'histogram_data'):
                print("No histogram data available for fitting")
                return
                
            # 获取数据在选择区域内的部分
            mask = (self.plot_canvas.histogram_data >= x_min) & (self.plot_canvas.histogram_data <= x_max)
            selected_data = self.plot_canvas.histogram_data[mask]
            
            if len(selected_data) < 10:
                print("Not enough data points for Gaussian fitting")
                return
            
            # 获取直方图bin信息
            if not hasattr(self.plot_canvas, 'hist_bin_centers'):
                print("No histogram bin centers available")
                return
                
            bin_mask = (self.plot_canvas.hist_bin_centers >= x_min) & (self.plot_canvas.hist_bin_centers <= x_max)
            x_data = self.plot_canvas.hist_bin_centers[bin_mask]
            y_data = self.plot_canvas.hist_counts[bin_mask]
            
            if len(x_data) < 3:
                print("Not enough histogram bins for Gaussian fitting")
                return
            
            # 高斯函数
            def gaussian(x, amp, mu, sigma):
                return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
            
            # 初始估计参数
            amp_init = y_data.max()
            mean_init = np.mean(selected_data)
            std_init = np.std(selected_data)
            
            # 添加边界约束
            bounds = (
                [0, x_min, 0],
                [amp_init*3, x_max, (x_max-x_min)]
            )
            
            p0 = [amp_init, mean_init, std_init]
            
            # 拟合高斯函数
            try:
                popt, _ = curve_fit(gaussian, x_data, y_data, p0=p0, bounds=bounds, maxfev=2000)
                
                # 选择拟合曲线颜色
                fit_color = ColorManager.get_color_by_index(len(self.gaussian_fits), 'fit')
                
                # 创建拟合曲线
                x_fit = np.linspace(x_min, x_max, 150)
                y_fit = gaussian(x_fit, *popt)
                line, = self.plot_canvas.ax.plot(x_fit, y_fit, '-', linewidth=1.0, color=fit_color, zorder=15)
                
                # 创建文本标签
                amp, mu, sigma = popt
                fit_num = len(self.gaussian_fits) + 1
                text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
                
                text_obj = self.plot_canvas.ax.text(mu, amp*1.05, text, ha='center', va='bottom', fontsize=9,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor=fit_color, boxstyle='round'),
                    color=fit_color, zorder=20)
                
                # 如果当前标签不可见，隐藏文本
                if not self.labels_visible:
                    text_obj.set_visible(False)
                
                # 将拟合参数添加到列表
                fit_data = {
                    'popt': popt,
                    'x_range': (x_min, x_max),
                    'line': line,
                    'text': text_obj,
                    'color': fit_color
                }
                self.gaussian_fits.append(fit_data)
                
                # 添加到拟合信息面板
                if (hasattr(self.plot_canvas, 'parent_dialog') and 
                    self.plot_canvas.parent_dialog and 
                    hasattr(self.plot_canvas.parent_dialog, 'fit_info_panel')):
                    
                    self.plot_canvas.parent_dialog.fit_info_panel.add_fit(
                        fit_num, amp, mu, sigma, (x_min, x_max), fit_color
                    )
                
                # 更新拟合信息字符串
                self.update_fit_info_string()
                
                # 重新绘制
                self.plot_canvas.draw()
                
                # 保存拟合结果并同步到主视图
                self.save_current_fits()
                self.immediate_sync_to_main_view()
                
            except RuntimeError as e:
                print(f"Error fitting Gaussian: {e}")
                
        except Exception as e:
            print(f"Error in Gaussian fitting: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_fits(self):
        """清除所有高斯拟合"""
        try:
            # 保存清空状态到共享数据
            if self.shared_fit_data is not None:
                self.shared_fit_data.clear_fits()
            
            # 删除所有拟合曲线和文本
            for fit in self.gaussian_fits:
                if 'line' in fit and fit['line']:
                    try:
                        if fit['line'] in self.plot_canvas.ax.lines:
                            fit['line'].remove()
                    except Exception as e:
                        print(f"Error removing line: {e}")
                        try:
                            fit['line'].set_visible(False)
                        except:
                            pass
                
                if 'text' in fit and fit['text']:
                    try:
                        if hasattr(self.plot_canvas.ax, 'texts') and fit['text'] in self.plot_canvas.ax.texts:
                            fit['text'].remove()
                        else:
                            fit['text'].set_visible(False)
                    except Exception as e:
                        print(f"Error removing text: {e}")
                        try:
                            fit['text'].set_visible(False)
                        except Exception as e2:
                            print(f"Error hiding text: {e2}")
                            pass
            
            self.gaussian_fits.clear()
            
            # 删除所有区域高亮
            for _, _, region in self.fit_regions:
                if region in self.plot_canvas.ax.patches:
                    region.remove()
            
            self.fit_regions.clear()
            
            # 重置状态
            self.fit_info_str = "No fits yet"
            self.highlighted_fit_index = -1
            
            # 清除拟合信息面板
            if (hasattr(self.plot_canvas, 'parent_dialog') and 
                self.plot_canvas.parent_dialog and 
                hasattr(self.plot_canvas.parent_dialog, 'fit_info_panel')):
                
                self.plot_canvas.parent_dialog.fit_info_panel.clear_all_fits()
            
            # 立即同步清空状态到主视图
            self.immediate_sync_to_main_view()
            
            # 重绘
            self.plot_canvas.draw()
            
        except Exception as e:
            print(f"Error clearing fits: {e}")
            import traceback
            traceback.print_exc()
    
    def delete_specific_fit(self, fit_index):
        """删除特定的拟合"""
        try:
            if not self.gaussian_fits:
                print("No fits to delete")
                return False
            
            # 直接使用索引匹配（fit_index从1开始，数组索引从0开始）
            target_index = fit_index - 1
            
            # 检查索引是否有效
            if target_index < 0 or target_index >= len(self.gaussian_fits):
                print(f"Invalid fit index {fit_index}, valid range: 1-{len(self.gaussian_fits)}")
                return False
            
            fit = self.gaussian_fits[target_index]
            print(f"Deleting fit {fit_index} (array index {target_index})")
            
            # 安全从图中移除元素
            if 'line' in fit and fit['line']:
                try:
                    if fit['line'] in self.plot_canvas.ax.lines:
                        fit['line'].remove()
                except Exception as e:
                    print(f"Error removing line: {e}")
                    try:
                        fit['line'].set_visible(False)
                    except:
                        pass
            
            if 'text' in fit and fit['text']:
                try:
                    if hasattr(self.plot_canvas.ax, 'texts') and fit['text'] in self.plot_canvas.ax.texts:
                        fit['text'].remove()
                    else:
                        fit['text'].set_visible(False)
                except Exception as e:
                    print(f"Error removing text: {e}")
                    try:
                        fit['text'].set_visible(False)
                    except Exception as e2:
                        print(f"Error hiding text: {e2}")
                        pass
            
            # 移除相关的区域高亮
            if target_index < len(self.fit_regions):
                try:
                    _, _, region = self.fit_regions[target_index]
                    if region and hasattr(self.plot_canvas.ax, 'patches') and region in self.plot_canvas.ax.patches:
                        region.remove()
                except Exception as e:
                    print(f"Error removing region: {e}")
                self.fit_regions.pop(target_index)
            
            # 从列表中移除
            self.gaussian_fits.pop(target_index)
            
            # 重新编号剩余的拟合并更新拟合信息面板
            self._renumber_fits_and_update_panel()
            
            # 重置高亮索引
            if self.highlighted_fit_index >= len(self.gaussian_fits):
                self.highlighted_fit_index = -1
            
            # 保存当前状态或清空共享数据
            if len(self.gaussian_fits) == 0:
                if self.shared_fit_data is not None:
                    self.shared_fit_data.clear_fits()
                    print("Cleared shared fit data after deleting last fit")
            else:
                self.save_current_fits()
            
            # 立即同步到主视图
            self.immediate_sync_to_main_view()
            
            # 重新绘制
            self.plot_canvas.draw()
            
            print(f"Successfully deleted fit {fit_index}, {len(self.gaussian_fits)} fits remaining")
            return True
            
        except Exception as e:
            print(f"Error deleting specific fit: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _renumber_fits(self):
        """重新编号拟合"""
        for i, fit in enumerate(self.gaussian_fits):
            amp, mu, sigma = fit['popt']
            fit_num = i + 1
            new_text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
            
            if 'text' in fit and fit['text']:
                try:
                    fit['text'].set_text(new_text)
                except Exception as e:
                    print(f"Error updating text for fit {fit_num}: {e}")
                    try:
                        fit['text'].set_visible(False)
                    except:
                        pass
    
    def _renumber_fits_and_update_panel(self):
        """重新编号拟合并更新信息面板"""
        print(f"Renumbering {len(self.gaussian_fits)} remaining fits and updating panel")
        
        # 首先清空拟合信息面板
        if (hasattr(self.plot_canvas, 'parent_dialog') and 
            self.plot_canvas.parent_dialog and 
            hasattr(self.plot_canvas.parent_dialog, 'fit_info_panel')):
            
            self.plot_canvas.parent_dialog.fit_info_panel.clear_all_fits()
            print("Cleared fit info panel")
        
        # 重新编号并重新添加所有拟合到信息面板
        for i, fit in enumerate(self.gaussian_fits):
            amp, mu, sigma = fit['popt']
            fit_num = i + 1
            x_range = fit['x_range']
            color = fit['color']
            
            # 更新文本标签
            new_text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
            if 'text' in fit and fit['text']:
                try:
                    fit['text'].set_text(new_text)
                except Exception as e:
                    print(f"Error updating text for fit {fit_num}: {e}")
                    try:
                        fit['text'].set_visible(False)
                    except:
                        pass
            
            # 重新添加到信息面板
            if (hasattr(self.plot_canvas, 'parent_dialog') and 
                self.plot_canvas.parent_dialog and 
                hasattr(self.plot_canvas.parent_dialog, 'fit_info_panel')):
                
                self.plot_canvas.parent_dialog.fit_info_panel.add_fit(
                    fit_num, amp, mu, sigma, x_range, color
                )
                print(f"Re-added fit {fit_num} to panel")
        
        # 更新拟合信息字符串
        self.update_fit_info_string()
        print("Renumbering and panel update completed")
    
    def update_fit_info_string(self):
        """更新拟合信息字符串"""
        if not self.gaussian_fits:
            self.fit_info_str = "No fits yet"
            return
        
        info_lines = ["===== Fitting Results ====="]
        for i, fit in enumerate(self.gaussian_fits):
            amp, mu, sigma = fit['popt']
            fwhm = 2.355 * sigma
            info_lines.append(f"Gaussian {i+1}:")
            info_lines.append(f"  Peak position: {mu:.4f}")
            info_lines.append(f"  Amplitude: {amp:.2f}")
            info_lines.append(f"  Sigma: {sigma:.4f}")
            info_lines.append(f"  FWHM: {fwhm:.4f}")
            info_lines.append(f"  Range: {fit['x_range'][0]:.3f}-{fit['x_range'][1]:.3f}")
            info_lines.append("")
        
        # 计算多峰分析
        if len(self.gaussian_fits) > 1:
            info_lines.append("==== Multi-Peak Analysis ====")
            peaks = [fit['popt'][1] for fit in self.gaussian_fits]
            sorted_peaks = sorted(peaks)
            for i in range(len(sorted_peaks)-1):
                delta = sorted_peaks[i+1] - sorted_peaks[i]
                info_lines.append(f"Peak{i+1} to Peak{i+2} distance: {delta:.4f}")
        
        self.fit_info_str = "\n".join(info_lines)
    
    def save_current_fits(self):
        """保存当前的拟合结果到共享数据"""
        try:
            # 计算数据哈希值
            data_hash = self._calculate_data_hash()
            data_range = (self.plot_canvas.histogram_data.min(), self.plot_canvas.histogram_data.max()) if hasattr(self.plot_canvas, 'histogram_data') and self.plot_canvas.histogram_data is not None else None
            
            # 获取当前的拟合结果
            current_fits = self.gaussian_fits if self.gaussian_fits else []
            current_regions = [(r[0], r[1]) for r in self.fit_regions if len(r) >= 2] if self.fit_regions else []
            
            # 保存到共享数据
            if self.shared_fit_data is not None:
                self.shared_fit_data.save_fits(current_fits, current_regions, data_range, data_hash)
                print(f"Saved {len(current_fits)} fits to shared data")
                
        except Exception as e:
            print(f"Error saving fits: {e}")
            import traceback
            traceback.print_exc()
    
    def immediate_sync_to_main_view(self):
        """立即同步拟合结果到主视图的subplot3"""
        try:
            if (hasattr(self.plot_canvas, 'parent_dialog') and 
                self.plot_canvas.parent_dialog and 
                hasattr(self.plot_canvas.parent_dialog, 'plot_canvas')):
                
                main_canvas = self.plot_canvas.parent_dialog.plot_canvas
                
                if not hasattr(main_canvas, '_ax3_fit_lines'):
                    main_canvas._ax3_fit_lines = []
                
                if hasattr(main_canvas, 'update_highlighted_plots'):
                    print(f"Triggering sync to main view - current fits: {len(self.gaussian_fits)}")
                    main_canvas.update_highlighted_plots()
                    main_canvas.draw()
                    print(f"Immediate sync to main view subplot3 completed")
        except Exception as e:
            print(f"Error in immediate sync to main view: {e}")
            import traceback
            traceback.print_exc()
    
    def restore_fits_from_shared_data(self):
        """从共享数据恢复拟合结果"""
        if self.shared_fit_data is None or not self.shared_fit_data.has_fits():
            print("[Restore] No shared fit data to restore")
            return False
            
        try:
            # 检查数据兼容性（放宽检查条件）
            data_hash = self._calculate_data_hash()
            if data_hash is None:
                print("[Restore] Cannot calculate data hash for compatibility check")
                # 放宽检查，允许恢复
            
            # 获取共享的拟合数据
            fits, regions = self.shared_fit_data.get_fits()
            
            if not fits:
                print("[Restore] No fits found in shared data")
                return False
            
            print(f"[Restore] Restoring {len(fits)} fits from shared data")
            
            # 应用到当前图表
            self.apply_fits_to_plot(fits, regions)
            
            print(f"[Restore] Successfully restored {len(fits)} fits from shared data")
            return True
            
        except Exception as e:
            print(f"[Restore] Error restoring fits from shared data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def apply_fits_to_plot(self, fits, regions):
        """将拟合结果应用到当前图表"""
        try:
            print(f"[Restore] Applying {len(fits)} fits to plot")
            
            # 清除现有的拟合
            self._clear_existing_fits()
            
            # 初始化拟合数据结构
            self.gaussian_fits.clear()
            self.fit_regions.clear()
            
            # 应用每个拟合
            for i, fit_data in enumerate(fits):
                if not fit_data or 'popt' not in fit_data:
                    print(f"[Restore] Skipping invalid fit data at index {i}")
                    continue
                    
                popt = fit_data['popt']
                x_range = fit_data['x_range']
                color = fit_data['color']
                
                print(f"[Restore] Drawing fit {i+1}: mu={popt[1]:.3f}, sigma={popt[2]:.3f}, color={color}")
                # 绘制拟合曲线
                self._draw_fit_curve(popt, x_range, color, i + 1)
                
            # 更新拟合信息面板
            if (hasattr(self.plot_canvas, 'parent_dialog') and 
                self.plot_canvas.parent_dialog and 
                hasattr(self.plot_canvas.parent_dialog, 'fit_info_panel')):
                
                print(f"[Restore] Updating fit info panel with {len(fits)} fits")
                self.plot_canvas.parent_dialog.fit_info_panel.clear_all_fits()
                for i, fit_data in enumerate(fits):
                    if fit_data and 'popt' in fit_data:
                        amp, mu, sigma = fit_data['popt']
                        self.plot_canvas.parent_dialog.fit_info_panel.add_fit(
                            i + 1, amp, mu, sigma, fit_data['x_range'], fit_data['color']
                        )
                        print(f"[Restore] Added fit {i+1} to info panel")
            else:
                print("[Restore] fit_info_panel not available for update")
            
            # 更新拟合信息字符串
            self.update_fit_info_string()
            print(f"[Restore] Updated fit info string")
                
        except Exception as e:
            print(f"[Restore] Error applying fits to plot: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_fit_curve(self, popt, x_range, color, fit_num):
        """绘制单个拟合曲线"""
        try:
            # 高斯函数
            def gaussian(x, amp, mu, sigma):
                return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))
            
            # 创建拟合曲线数据
            x_fit = np.linspace(x_range[0], x_range[1], 150)
            y_fit = gaussian(x_fit, *popt)
            
            # 绘制曲线
            line, = self.plot_canvas.ax.plot(x_fit, y_fit, '-', linewidth=1.0, color=color, zorder=15)
            
            # 创建文本标签
            amp, mu, sigma = popt
            text = f"G{fit_num}: μ={mu:.3f}, σ={sigma:.3f}"
            text_obj = self.plot_canvas.ax.text(mu, amp*1.05, text, ha='center', va='bottom', fontsize=9,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor=color, boxstyle='round'),
                color=color, zorder=20)
            
            # 检查标签可见性
            if hasattr(self, 'labels_visible'):
                text_obj.set_visible(self.labels_visible)
            
            # 添加到拟合列表
            fit_data = {
                'popt': popt,
                'x_range': x_range,
                'line': line,
                'text': text_obj,
                'color': color
            }
            self.gaussian_fits.append(fit_data)
            
            # 添加区域高亮
            region = self.plot_canvas.ax.axvspan(x_range[0], x_range[1], alpha=0.08, color='green', zorder=0)
            self.fit_regions.append((x_range[0], x_range[1], region))
                
        except Exception as e:
            print(f"Error drawing fit curve: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_existing_fits(self):
        """清除现有的拟合绘图对象"""
        try:
            for fit in self.gaussian_fits:
                if 'line' in fit and fit['line']:
                    try:
                        if fit['line'] in self.plot_canvas.ax.lines:
                            fit['line'].remove()
                    except Exception as e:
                        print(f"Error removing line: {e}")
                        try:
                            fit['line'].set_visible(False)
                        except:
                            pass
                
                if 'text' in fit and fit['text']:
                    try:
                        if hasattr(self.plot_canvas.ax, 'texts') and fit['text'] in self.plot_canvas.ax.texts:
                            fit['text'].remove()
                        else:
                            fit['text'].set_visible(False)
                    except Exception as e:
                        print(f"Error removing text: {e}")
                        try:
                            fit['text'].set_visible(False)
                        except Exception as e2:
                            print(f"Error hiding text: {e2}")
                            pass
            
            for region_data in self.fit_regions:
                if len(region_data) >= 3 and region_data[2]:
                    try:
                        if region_data[2] in self.plot_canvas.ax.patches:
                            region_data[2].remove()
                    except Exception as e:
                        print(f"Error removing region: {e}")
                        try:
                            region_data[2].set_visible(False)
                        except:
                            pass
                        
        except Exception as e:
            print(f"Error clearing existing fits: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_data_hash(self):
        """计算数据哈希值用于检测数据变化"""
        if hasattr(self.plot_canvas, 'histogram_data') and self.plot_canvas.histogram_data is not None:
            return DataHasher.calculate_data_hash(self.plot_canvas.histogram_data)
        return None
    
    def highlight_fit(self, fit_index):
        """高亮显示特定的拟合曲线（加粗）"""
        try:
            # 首先重置所有曲线的粗细
            for fit in self.gaussian_fits:
                if 'line' in fit and fit['line']:
                    try:
                        fit['line'].set_linewidth(1.0)  # 默认粗细
                    except:
                        pass
                        
            # 如果fit_index为-1或无效，只重置所有曲线
            if fit_index <= 0:
                self.plot_canvas.draw()
                return
            
            # 直接使用索引匹配（fit_index从1开始，数组索引从0开始）
            target_index = fit_index - 1
            
            # 检查索引是否有效
            if target_index < 0 or target_index >= len(self.gaussian_fits):
                print(f"Invalid fit index {fit_index}, valid range: 1-{len(self.gaussian_fits)}")
                self.plot_canvas.draw()
                return
            
            # 获取目标拟合并高亮显示
            target_fit = self.gaussian_fits[target_index]
            
            if 'line' in target_fit and target_fit['line']:
                try:
                    target_fit['line'].set_linewidth(3.0)  # 加粗显示
                    print(f"Highlighted fit {fit_index} (index {target_index}) with bold line")
                except Exception as e:
                    print(f"Error highlighting fit line: {e}")
            else:
                print(f"No line found for fit {fit_index}")
            
            # 重绘图表
            self.plot_canvas.draw()
            
        except Exception as e:
            print(f"Error highlighting fit {fit_index}: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_fit_labels(self, visible):
        """切换拟合标签可见性"""
        try:
            self.labels_visible = visible
            for fit in self.gaussian_fits:
                if 'text' in fit and fit['text']:
                    fit['text'].set_visible(visible)
            
            self.plot_canvas.draw()
            
        except Exception as e:
            print(f"Error toggling fit labels: {e}")
