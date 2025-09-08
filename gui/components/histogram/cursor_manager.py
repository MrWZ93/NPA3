#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cursor Manager - Cursor管理器
负责管理直方图中的cursor功能
"""

import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt, QObject
from .plot_utils import ColorManager, RecursionGuard


class CursorManager(QObject):
    """Cursor管理器类"""
    
    # 定义信号
    cursor_deselected = pyqtSignal()
    cursor_selected = pyqtSignal(int)
    
    def __init__(self, plot_canvas):
        super().__init__()
        self.plot_canvas = plot_canvas
        self.guard = RecursionGuard()
        
        # Cursor 功能相关变量
        self.cursors = []
        self.selected_cursor = None
        self.dragging = False
        self.drag_start_y = None
        self.cursor_counter = 0
        
        # 添加cursor可见性控制
        self.cursors_visible = True
        
        # 连接鼠标事件
        self.plot_canvas.mpl_connect('button_press_event', self.on_cursor_mouse_press)
        self.plot_canvas.mpl_connect('motion_notify_event', self.on_cursor_mouse_move)
        self.plot_canvas.mpl_connect('button_release_event', self.on_cursor_mouse_release)
        
        # 设置焦点策略以接收键盘事件
        self.plot_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def add_cursor(self, y_position=None, color=None):
        """添加一个cursor - 添加防护"""
        # 防止递归调用
        if self.guard.is_updating("add_cursor"):
            return None
            
        try:
            self.guard.set_updating("add_cursor", True)
            
            # 确定Y位置
            if y_position is None:
                if hasattr(self.plot_canvas, 'ax2') and len(self.plot_canvas.ax2.get_ylim()) == 2:
                    y_min, y_max = self.plot_canvas.ax2.get_ylim()
                    y_position = (y_min + y_max) / 2
                else:
                    y_position = 0
            
            # 选择颜色
            if color is None:
                color = ColorManager.get_color_by_index(len(self.cursors), 'cursor')
            
            # 创建唯一ID
            cursor_id = self.cursor_counter
            self.cursor_counter += 1
            
            # 在Fig2中创建横向线
            line_ax2 = None
            if hasattr(self.plot_canvas, 'ax2'):
                line_ax2 = self.plot_canvas.ax2.axhline(y=y_position, color=color, 
                                          linestyle='--', linewidth=0.8, 
                                          alpha=0.6, zorder=20,
                                          visible=self.cursors_visible)
            
            # 在Fig3中创建横向线
            line_ax3 = None
            if hasattr(self.plot_canvas, 'ax3'):
                line_ax3 = self.plot_canvas.ax3.axhline(y=y_position, color=color, 
                                          linestyle='--', linewidth=0.8, 
                                          alpha=0.6, zorder=20,
                                          visible=self.cursors_visible)
            
            # 创建cursor对象（在histogram模式下不创建可视化线）
            cursor = {
                'id': cursor_id,
                'y_position': y_position,
                'color': color,
                'line_ax2': line_ax2,
                'line_ax3': line_ax3,
                'selected': False,
                'histogram_line': None  # 在histogram模式下不创建可视化cursor
            }
            
            self.cursors.append(cursor)
            
            # 重绘
            if not self.guard.is_updating("draw"):
                self.plot_canvas.draw()
            
            print(f"Added cursor with ID {cursor_id} at position {y_position}")
            return cursor_id
            
        except Exception as e:
            print(f"Error adding cursor: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self.guard.set_updating("add_cursor", False)
    
    def set_cursors_visible(self, visible):
        """设置cursor的可见性"""
        try:
            self.cursors_visible = visible
            
            # 更新所有cursor的可见性
            for cursor in self.cursors:
                # 更新ax2中的线
                if 'line_ax2' in cursor and cursor['line_ax2']:
                    cursor['line_ax2'].set_visible(visible)
                
                # 更新ax3中的线
                if 'line_ax3' in cursor and cursor['line_ax3']:
                    cursor['line_ax3'].set_visible(visible)
                
                # 在直方图模式下不显示cursor，无论可见性设置如何
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    cursor['histogram_line'].set_visible(False)  # 在histogram模式下总是隐藏
            
            # 重绘
            if not self.guard.is_updating("draw"):
                self.plot_canvas.draw()
            
            print(f"Set cursors visibility to: {visible}")
            return True
            
        except Exception as e:
            print(f"Error setting cursor visibility: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def toggle_cursors_visibility(self):
        """切换cursor的可见性"""
        new_visibility = not self.cursors_visible
        success = self.set_cursors_visible(new_visibility)
        return new_visibility if success else self.cursors_visible
    
    def get_cursors_visible(self):
        """获取cursor的可见性状态"""
        return self.cursors_visible
    
    def remove_cursor(self, cursor_id):
        """删除指定的cursor"""
        try:
            for i, cursor in enumerate(self.cursors):
                if cursor['id'] == cursor_id:
                    # 移除绘图元素
                    if 'line_ax2' in cursor and cursor['line_ax2']:
                        cursor['line_ax2'].remove()
                    if 'line_ax3' in cursor and cursor['line_ax3']:
                        cursor['line_ax3'].remove()
                    if 'histogram_line' in cursor and cursor['histogram_line']:
                        cursor['histogram_line'].remove()
                    
                    # 从列表中移除
                    self.cursors.pop(i)
                    
                    # 如果删除的是选中的cursor，清除选择
                    if self.selected_cursor and self.selected_cursor['id'] == cursor_id:
                        self.selected_cursor = None
                    
                    # 重新编号cursor
                    self._reorder_cursor_ids()
                    
                    # 重绘
                    self.plot_canvas.draw()
                    
                    print(f"Removed cursor with ID {cursor_id}")
                    return True
            
            print(f"Cursor with ID {cursor_id} not found")
            return False
            
        except Exception as e:
            print(f"Error removing cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def clear_all_cursors(self):
        """清除所有cursor"""
        try:
            for cursor in self.cursors:
                if 'line_ax2' in cursor and cursor['line_ax2']:
                    try:
                        cursor['line_ax2'].remove()
                    except:
                        pass
                if 'line_ax3' in cursor and cursor['line_ax3']:
                    try:
                        cursor['line_ax3'].remove()
                    except:
                        pass
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    try:
                        cursor['histogram_line'].remove()
                    except:
                        pass
            
            self.cursors.clear()
            self.selected_cursor = None
            self.cursor_counter = 0
            
            # 重绘
            self.plot_canvas.draw()
            
            print("Cleared all cursors")
            return True
            
        except Exception as e:
            print(f"Error clearing cursors: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_cursor(self, cursor_id):
        """选中cursor - 添加递归防护"""
        # 防止递归调用
        if self.guard.is_updating("select_cursor"):
            return True
            
        try:
            self.guard.set_updating("select_cursor", True)
            
            # 先取消所有cursor的选中状态
            for cursor in self.cursors:
                cursor['selected'] = False
                # 恢复正常线宽
                for line_key in ['line_ax2', 'line_ax3', 'histogram_line']:
                    if line_key in cursor and cursor[line_key]:
                        cursor[line_key].set_linewidth(0.8)
                        cursor[line_key].set_alpha(0.6)
            
            # 设置选中的cursor
            if cursor_id is not None:
                for cursor in self.cursors:
                    if cursor['id'] == cursor_id:
                        cursor['selected'] = True
                        self.selected_cursor = cursor
                        # 高亮选中的cursor
                        for line_key in ['line_ax2', 'line_ax3', 'histogram_line']:
                            if line_key in cursor and cursor[line_key]:
                                cursor[line_key].set_linewidth(1.5)
                                cursor[line_key].set_alpha(0.9)
                        break
                        
                # 发送选中信号
                if not self.guard.is_signal_emitting("cursor_selected"):
                    self.guard.set_signal_emitting("cursor_selected", True)
                    try:
                        self.cursor_selected.emit(cursor_id)
                    finally:
                        self.guard.set_signal_emitting("cursor_selected", False)
            else:
                self.selected_cursor = None
                # 发送取消选中信号
                if not self.guard.is_signal_emitting("cursor_deselected"):
                    self.guard.set_signal_emitting("cursor_deselected", True)
                    try:
                        self.cursor_deselected.emit()
                    finally:
                        self.guard.set_signal_emitting("cursor_deselected", False)
            
            # 重绘
            if not self.guard.is_updating("draw"):
                self.plot_canvas.draw()
            
            return True
            
        except Exception as e:
            print(f"Error selecting cursor: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.guard.set_updating("select_cursor", False)
    
    def update_cursor_position(self, cursor_id, new_position):
        """更新cursor位置"""
        try:
            for cursor in self.cursors:
                if cursor['id'] == cursor_id:
                    cursor['y_position'] = new_position
                    
                    # 更新ax2中的线
                    if 'line_ax2' in cursor and cursor['line_ax2']:
                        cursor['line_ax2'].set_ydata([new_position, new_position])
                    
                    # 更新ax3中的线
                    if 'line_ax3' in cursor and cursor['line_ax3']:
                        cursor['line_ax3'].set_ydata([new_position, new_position])
                    
                    # 更新直方图模式中的线
                    if 'histogram_line' in cursor and cursor['histogram_line']:
                        cursor['histogram_line'].set_xdata([new_position, new_position])
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error updating cursor position: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_cursor_info(self):
        """获取所有cursor的信息"""
        try:
            cursor_info = []
            for cursor in self.cursors:
                info = {
                    'id': cursor['id'],
                    'y_position': cursor['y_position'],
                    'color': cursor['color'],
                    'selected': cursor.get('selected', False)
                }
                cursor_info.append(info)
            
            return cursor_info
            
        except Exception as e:
            print(f"Error getting cursor info: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def refresh_cursors_after_plot_update(self):
        """在主视图plot更新后刷新cursor显示 - 彻底清理旧线条"""
        try:
            # 添加防护，避免重复调用
            if self.guard.is_updating("refresh_cursors_after_plot_update"):
                return
                
            self.guard.set_updating("refresh_cursors_after_plot_update", True)
            
            # 第0步：使用强制清理方法彻底清理所有cursor线条
            self._clear_all_cursor_lines_from_axes()
            
            # 第1步：重新创建所有cursor线条
            for cursor in self.cursors:
                y_pos = cursor['y_position']
                color = cursor['color']
                is_selected = cursor.get('selected', False)
                
                # 在ax2中创建新线条
                if hasattr(self.plot_canvas, 'ax2'):
                    cursor['line_ax2'] = self.plot_canvas.ax2.axhline(
                        y=y_pos, color=color, 
                        linestyle='--', linewidth=1.5 if is_selected else 0.8, 
                        alpha=0.9 if is_selected else 0.6, zorder=20,
                        visible=self.cursors_visible
                    )
                
                # 在ax3中创建新线条
                if hasattr(self.plot_canvas, 'ax3'):
                    cursor['line_ax3'] = self.plot_canvas.ax3.axhline(
                        y=y_pos, color=color, 
                        linestyle='--', linewidth=1.5 if is_selected else 0.8, 
                        alpha=0.9 if is_selected else 0.6, zorder=20,
                        visible=self.cursors_visible
                    )
            
            print(f"Refreshed {len(self.cursors)} cursors after plot update (completely rebuilt)")
                    
        except Exception as e:
            print(f"Error refreshing cursors after plot update: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.guard.set_updating("refresh_cursors_after_plot_update", False)
    
    def _clear_all_cursor_lines_from_axes(self):
        """彻底清理axes中所有cursor线条 - 强制清理方法"""
        try:
            print("Starting complete cursor line cleanup...")
            
            # 清理ax2中的所有虚线
            if hasattr(self.plot_canvas, 'ax2') and hasattr(self.plot_canvas.ax2, 'lines'):
                lines_before = len(self.plot_canvas.ax2.lines)
                # 使用更强制的方式：直接遍历并移除所有虚线
                lines_to_remove = []
                for line in self.plot_canvas.ax2.lines:
                    if (hasattr(line, 'get_linestyle') and 
                        line.get_linestyle() in ['--', 'dashed'] and
                        hasattr(line, 'get_zorder') and 
                        line.get_zorder() >= 20):  # cursor线条通常有高zorder
                        lines_to_remove.append(line)
                
                for line in lines_to_remove:
                    try:
                        line.remove()
                    except:
                        pass
                
                # 直接操作lines列表
                self.plot_canvas.ax2.lines = [line for line in self.plot_canvas.ax2.lines 
                                              if line not in lines_to_remove]
                
                lines_after = len(self.plot_canvas.ax2.lines)
                print(f"ax2: Removed {lines_before - lines_after} cursor lines")
            
            # 清理ax3中的所有虚线
            if hasattr(self.plot_canvas, 'ax3') and hasattr(self.plot_canvas.ax3, 'lines'):
                lines_before = len(self.plot_canvas.ax3.lines)
                # 使用更强制的方式：直接遍历并移除所有虚线
                lines_to_remove = []
                for line in self.plot_canvas.ax3.lines:
                    if (hasattr(line, 'get_linestyle') and 
                        line.get_linestyle() in ['--', 'dashed'] and
                        hasattr(line, 'get_zorder') and 
                        line.get_zorder() >= 20):  # cursor线条通常有高zorder
                        lines_to_remove.append(line)
                
                for line in lines_to_remove:
                    try:
                        line.remove()
                    except:
                        pass
                
                # 直接操作lines列表
                self.plot_canvas.ax3.lines = [line for line in self.plot_canvas.ax3.lines 
                                              if line not in lines_to_remove]
                
                lines_after = len(self.plot_canvas.ax3.lines)
                print(f"ax3: Removed {lines_before - lines_after} cursor lines")
            
            # 清理cursor对象中的所有线条引用
            for cursor in self.cursors:
                cursor['line_ax2'] = None
                cursor['line_ax3'] = None
                cursor['histogram_line'] = None
            
            print("Complete cursor line cleanup finished")
            
        except Exception as e:
            print(f"Error in complete cursor line cleanup: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_cursors_for_histogram_mode(self):
        """在直方图模式下刷新cursor显示 - 修改为不显示cursor但保留数据"""
        try:
            for cursor in self.cursors:
                # 移除之前的线（如果存在）
                if 'histogram_line' in cursor and cursor['histogram_line']:
                    try:
                        cursor['histogram_line'].remove()
                    except:
                        pass
                    cursor['histogram_line'] = None
                
                # 在直方图模式下不创建可视化cursor，只保留数据
                # 这样cursor list中的信息会保留，但不会在histogram中显示
                print(f"Cursor {cursor['id']} data preserved in histogram mode but not displayed")
                        
        except Exception as e:
            print(f"Error refreshing cursors for histogram mode: {e}")
            import traceback
            traceback.print_exc()
    
    def _reorder_cursor_ids(self):
        """重新排序cursor ID"""
        if not self.cursors:
            self.cursor_counter = 0
            return
        
        # 按照当前ID排序，保持相对顺序
        cursors_sorted = sorted(self.cursors, key=lambda c: c.get('id', 0))
        
        # 重新分配连续的ID，从1开始
        for i, cursor in enumerate(cursors_sorted):
            old_id = cursor.get('id')
            new_id = i + 1
            cursor['id'] = new_id
            
            # 如果当前选中的cursor ID发生了变化，更新选中状态
            if self.selected_cursor and self.selected_cursor.get('id') == old_id:
                self.selected_cursor = cursor
        
        # 更新cursor列表顺序
        self.cursors = cursors_sorted
        
        # 重置cursor计数器为下一个可用ID
        self.cursor_counter = len(self.cursors)
        
        print(f"Reordered cursors: {[c['id'] for c in cursors_sorted]}")
    
    def on_cursor_mouse_press(self, event):
        """处理鼠标按下事件 - 添加防护，在histogram模式下不响应"""
        if not event.inaxes or self.guard.is_updating("mouse_press"):
            return
        
        # 在histogram模式下不响应cursor点击，因为cursor不可见
        if (hasattr(self.plot_canvas, 'is_histogram_mode') and 
            self.plot_canvas.is_histogram_mode and 
            hasattr(self.plot_canvas, 'ax') and 
            event.inaxes == self.plot_canvas.ax):
            print("Cursor interaction disabled in histogram mode")
            return
        
        try:
            self.guard.set_updating("mouse_press", True)
            
            # 检查是否点击在cursor附近
            clicked_cursor = self._find_cursor_near_click(event)
            
            if clicked_cursor:
                # 选中cursor并开始拖拽
                self.select_cursor(clicked_cursor['id'])
                self.dragging = True
                self.drag_start_y = event.ydata
            else:
                # 点击空白处，取消选择
                self.select_cursor(None)
                
        except Exception as e:
            print(f"Error in cursor mouse press: {e}")
        finally:
            self.guard.set_updating("mouse_press", False)
    
    def on_cursor_mouse_move(self, event):
        """处理鼠标移动事件 - 在histogram模式下不响应"""
        if not self.dragging or not self.selected_cursor or not event.inaxes:
            return
        
        # 在histogram模式下不响应cursor拖拽，因为cursor不可见
        if (hasattr(self.plot_canvas, 'is_histogram_mode') and 
            self.plot_canvas.is_histogram_mode and 
            hasattr(self.plot_canvas, 'ax') and 
            event.inaxes == self.plot_canvas.ax):
            return
        
        try:
            # 更新cursor位置
            new_y = event.ydata
            if new_y is not None:
                self.update_cursor_position(self.selected_cursor['id'], new_y)
                self.plot_canvas.draw()
                
        except Exception as e:
            print(f"Error in cursor mouse move: {e}")
    
    def on_cursor_mouse_release(self, event):
        """处理鼠标释放事件"""
        if self.dragging:
            self.dragging = False
            self.drag_start_y = None
    
    def _find_cursor_near_click(self, event):
        """查找点击位置附近的cursor（优化精度）"""
        if not event.xdata and not event.ydata:
            return None
        
        # 动态计算点击容忍度（相对于轴范围的百分比）
        try:
            # 判断是否为直方图模式（只有一个ax）
            is_histogram_mode = (hasattr(self.plot_canvas, 'is_histogram_mode') and 
                               self.plot_canvas.is_histogram_mode and 
                               hasattr(self.plot_canvas, 'ax') and 
                               event.inaxes == self.plot_canvas.ax)
            
            if is_histogram_mode:
                # 直方图模式：cursor是垂直线，检查x坐标
                if not event.xdata:
                    return None
                x_min, x_max = self.plot_canvas.ax.get_xlim()
                range_val = abs(x_max - x_min)
                click_pos = event.xdata
                
                closest_cursor = None
                closest_distance = float('inf')
                
                for cursor in self.cursors:
                    cursor_pos = cursor['y_position']  # 在直方图中，y_position存储的是x坐标值
                    distance = abs(click_pos - cursor_pos)
                    
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_cursor = cursor
                        
            else:
                # 主视图模式：cursor是水平线，检查y坐标
                if not event.ydata:
                    return None
                    
                if event.inaxes == getattr(self.plot_canvas, 'ax2', None):
                    y_min, y_max = self.plot_canvas.ax2.get_ylim()
                elif event.inaxes == getattr(self.plot_canvas, 'ax3', None):
                    y_min, y_max = self.plot_canvas.ax3.get_ylim()
                else:
                    return None
                
                range_val = abs(y_max - y_min)
                click_pos = event.ydata
                
                closest_cursor = None
                closest_distance = float('inf')
                
                for cursor in self.cursors:
                    cursor_pos = cursor['y_position']
                    distance = abs(click_pos - cursor_pos)
                    
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_cursor = cursor
            
            # 设置为轴范围的2%，更加精确
            click_tolerance = range_val * 0.02
            
            # 设置最小和最大容忍度以防止过小或过大
            min_tolerance = range_val * 0.005  # 0.5%
            max_tolerance = range_val * 0.05   # 5%
            click_tolerance = max(min_tolerance, min(click_tolerance, max_tolerance))
            
            # 检查最近的cursor是否在容忍范围内
            if closest_cursor and closest_distance < click_tolerance:
                mode = "histogram" if is_histogram_mode else "main view"
                print(f"Found cursor {closest_cursor['id']} in {mode} at distance {closest_distance:.4f} (tolerance: {click_tolerance:.4f})")
                return closest_cursor
            
        except Exception as e:
            print(f"Error calculating click tolerance: {e}")
            import traceback
            traceback.print_exc()
        
        return None
