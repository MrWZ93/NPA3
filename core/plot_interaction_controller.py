#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matplotlib 画布交互控制器 (高性能 Blitting 与绝对像素平移优化版)
封装高级鼠标交互：滚轮缩放、左键 Pan、Shift+左键框选、右键视图撤销、Crosshair 准星与 View Window 控制
使用 Matplotlib Blitting 技术与绝对屏幕像素坐标平移，确保无闪烁、无震荡、高平滑度体验
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QApplication

class PlotInteractionController(QObject):
    """Matplotlib 画布交互控制器类"""
    
    def __init__(self, visualizer):
        super().__init__()
        self.visualizer = visualizer  # DataVisualizer (FigureCanvas)
        self.fig = visualizer.fig
        self.toolbar = None
        
        # 视图历史栈: 存放 snapshot [(ax, xlim, ylim), ...]
        self.history_stack = []
        self.max_history = 50
        self.last_history_push_time = 0
        
        # 交互状态
        self.is_panning = False
        self.pan_start_event = None
        self.pan_start_pixel = None  # (pixel_x, pixel_y) 拖拽起点绝对屏幕像素坐标
        self.pan_init_limits = {}  # {ax: (xlim, ylim)}
        
        self.is_rect_zooming = False
        self.rect_start_pos = None  # (xdata, ydata)
        self.rect_ax = None
        self.rect_patch = None
        
        # 十字准星与坐标记录
        self.crosshair_lines = {}  # {ax: Line2D}
        self.last_cursor_time = None  # 最近鼠标悬停的 X 坐标 (s)
        self.last_cursor_val = None
        
        # Blitting 背景缓存
        self.bg = None
        self._need_bg_update = True
        
        # 绑定的 matplotlib 事件 cid
        self.cids = []
        self._connect_events()

    def set_toolbar(self, toolbar):
        """设置绑定的 NavigationToolbar"""
        self.toolbar = toolbar

    def _connect_events(self):
        """连接 Matplotlib 事件"""
        canvas = self.fig.canvas
        self.cids.append(canvas.mpl_connect('draw_event', self.on_draw))
        self.cids.append(canvas.mpl_connect('scroll_event', self.on_scroll))
        self.cids.append(canvas.mpl_connect('button_press_event', self.on_button_press))
        self.cids.append(canvas.mpl_connect('motion_notify_event', self.on_motion_notify))
        self.cids.append(canvas.mpl_connect('button_release_event', self.on_button_release))
        self.cids.append(canvas.mpl_connect('axes_leave_event', self.on_leave))
        self.cids.append(canvas.mpl_connect('figure_leave_event', self.on_leave))

    def is_toolbar_active(self):
        """判断 Matplotlib Toolbar 是否启用了 Zoom 或 Pan 工具"""
        if self.toolbar is None:
            return False
        mode = getattr(self.toolbar, 'mode', '')
        return bool(mode)

    def on_plot_updated(self):
        """当 DataVisualizer 绘制了新的数据/Subplots 时调用"""
        self._setup_crosshairs()
        self._need_bg_update = True
        # 清空/更新初始视图栈
        if not self.history_stack and self.visualizer.axes:
            self.push_view_history()

    def on_draw(self, event):
        """画布重绘后捕获背景图像用于 Blitting 准星绘制"""
        if event.canvas != self.fig.canvas:
            return
        self.bg = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        self._need_bg_update = False

    def _setup_crosshairs(self):
        """为所有 Subplot 初始化淡色垂直 Crosshair 虚线 (使用 animated=True)"""
        self.crosshair_lines.clear()
        for ax in self.visualizer.axes:
            line = ax.axvline(x=0, color='#888888', linestyle='--', linewidth=0.8, alpha=0.6, visible=False)
            line.set_animated(True)
            self.crosshair_lines[ax] = line

    def push_view_history(self):
        """保存当前所有 Subplot 的 xlim 和 ylim 到历史栈中"""
        if not self.visualizer.axes:
            return
        snapshot = []
        for ax in self.visualizer.axes:
            snapshot.append((ax, ax.get_xlim(), ax.get_ylim()))
        
        if self.history_stack:
            top_snapshot = self.history_stack[-1]
            is_same = True
            if len(top_snapshot) == len(snapshot):
                for (ax1, xlim1, ylim1), (ax2, xlim2, ylim2) in zip(top_snapshot, snapshot):
                    if ax1 != ax2 or xlim1 != xlim2 or ylim1 != ylim2:
                        is_same = False
                        break
            else:
                is_same = False
            if is_same:
                return

        self.history_stack.append(snapshot)
        if len(self.history_stack) > self.max_history:
            self.history_stack.pop(0)
        self.last_history_push_time = time.time()

    def pop_view_history(self):
        """弹出并恢复上一级视图历史"""
        if not self.history_stack:
            return False
        
        snapshot = self.history_stack.pop()
        for ax, xlim, ylim in snapshot:
            if ax in self.visualizer.axes:
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
        
        self._need_bg_update = True
        self.fig.canvas.draw_idle()
        return True

    def on_scroll(self, event):
        """鼠标滚轮事件处理：超细粒度平滑 X 轴缩放 / Shift+滚轮 Y 轴缩放"""
        if self.is_toolbar_active():
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return

        shift_pressed = False
        if event.key and 'shift' in event.key:
            shift_pressed = True
        else:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                shift_pressed = True

        step = getattr(event, 'step', 0)
        if step == 0:
            step = 1.0 if event.button == 'up' else -1.0

        # 精细化微调缩放步幅：基准比例设为 3.5% (0.965)，防调过头
        step_mag = min(abs(step), 2.0)
        if step > 0:
            scale_factor = 0.965 ** step_mag
        else:
            scale_factor = (1.0 / 0.965) ** step_mag

        # 连续快速滚动时合并历史压栈
        if time.time() - self.last_history_push_time > 0.3:
            self.push_view_history()

        ax = event.inaxes
        if shift_pressed:
            cur_ylim = ax.get_ylim()
            y_center = event.ydata
            new_ymin = y_center - (y_center - cur_ylim[0]) * scale_factor
            new_ymax = y_center + (cur_ylim[1] - y_center) * scale_factor
            ax.set_ylim(new_ymin, new_ymax)
        else:
            cur_xlim = ax.get_xlim()
            x_center = event.xdata
            new_xmin = x_center - (x_center - cur_xlim[0]) * scale_factor
            new_xmax = x_center + (cur_xlim[1] - x_center) * scale_factor

            if self.visualizer.sync_mode:
                for sub_ax in self.visualizer.axes:
                    sub_ax.set_xlim(new_xmin, new_xmax)
            else:
                ax.set_xlim(new_xmin, new_xmax)

        self._need_bg_update = True
        self.fig.canvas.draw_idle()

    def on_button_press(self, event):
        """鼠标按键按下处理：Pan、Shift+矩形缩放、双击全图、右键撤销"""
        if self.is_toolbar_active():
            return
        if event.inaxes is None:
            return

        shift_pressed = False
        if event.key and 'shift' in event.key:
            shift_pressed = True
        else:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                shift_pressed = True

        if event.button == 3:
            self.pop_view_history()
            return

        if event.button == 1 and getattr(event, 'dblclick', False):
            self.reset_full_view(target_ax=event.inaxes)
            return

        if event.button == 1:
            if shift_pressed:
                self.is_rect_zooming = True
                self.rect_ax = event.inaxes
                self.rect_start_pos = (event.xdata, event.ydata)
                
                if self.rect_patch and self.rect_patch.axes:
                    self.rect_patch.remove()
                self.rect_patch = Rectangle(
                    (event.xdata, event.ydata), 0, 0,
                    fill=True, facecolor='#0078d7', edgecolor='#0078d7',
                    alpha=0.25, linestyle='--'
                )
                self.rect_patch.set_animated(True)
                self.rect_ax.add_patch(self.rect_patch)
            else:
                self.is_panning = True
                self.pan_start_event = event
                # 关键修复：记录初始屏幕像素坐标 (event.x, event.y)，避免数据坐标更新导致的闪烁反馈环
                self.pan_start_pixel = (event.x, event.y)
                self.pan_init_limits = {sub_ax: (sub_ax.get_xlim(), sub_ax.get_ylim()) for sub_ax in self.visualizer.axes}
                self.push_view_history()

    def on_motion_notify(self, event):
        """鼠标移动处理：绝对像素 Pan 平移与 Crosshair/矩形框 Blitting 极速绘制"""
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            self.on_leave(event)
            return

        self.last_cursor_time = event.xdata
        self.last_cursor_val = event.ydata
        self._update_readout_status(event)

        if self.is_toolbar_active():
            return

        canvas = self.fig.canvas

        # 1. 处理 Pan 拖拽平移 (基准屏幕绝对像素位移，无震荡闪烁)
        if self.is_panning and self.pan_start_pixel and self.pan_start_event:
            pan_ax = self.pan_start_event.inaxes
            if pan_ax in self.pan_init_limits:
                # 计算屏幕像素位移
                dx_pix = event.x - self.pan_start_pixel[0]
                dy_pix = event.y - self.pan_start_pixel[1]

                bbox = pan_ax.get_window_extent()
                if bbox.width > 0 and bbox.height > 0:
                    orig_xlim, orig_ylim = self.pan_init_limits[pan_ax]
                    x_per_pix = (orig_xlim[1] - orig_xlim[0]) / bbox.width
                    y_per_pix = (orig_ylim[1] - orig_ylim[0]) / bbox.height

                    # 鼠标向右拖 (+dx_pix) -> 视图向左移 (-dx_pix * x_per_pix)
                    # 鼠标向上拖 (+dy_pix) -> 视图向下移 (-dy_pix * y_per_pix)
                    pan_ax.set_ylim(orig_ylim[0] - dy_pix * y_per_pix, orig_ylim[1] - dy_pix * y_per_pix)

                    if self.visualizer.sync_mode:
                        for sub_ax in self.visualizer.axes:
                            if sub_ax in self.pan_init_limits:
                                sub_xlim, _ = self.pan_init_limits[sub_ax]
                                sub_x_per_pix = (sub_xlim[1] - sub_xlim[0]) / bbox.width
                                sub_ax.set_xlim(sub_xlim[0] - dx_pix * sub_x_per_pix, sub_xlim[1] - dx_pix * sub_x_per_pix)
                    else:
                        pan_ax.set_xlim(orig_xlim[0] - dx_pix * x_per_pix, orig_xlim[1] - dx_pix * x_per_pix)

                    self._need_bg_update = True
                    canvas.draw_idle()
            return

        # 2. 处理 Shift + 左键矩形选择框 (Blitting 高速渲染)
        if self.is_rect_zooming and self.rect_patch and self.rect_start_pos:
            start_x, start_y = self.rect_start_pos
            width = event.xdata - start_x
            height = event.ydata - start_y

            rect_x = min(start_x, event.xdata)
            rect_y = min(start_y, event.ydata)
            rect_w = abs(width)
            rect_h = abs(height)

            self.rect_patch.set_xy((rect_x, rect_y))
            self.rect_patch.set_width(rect_w)
            self.rect_patch.set_height(rect_h)

            if self.bg is not None and not self._need_bg_update:
                canvas.restore_region(self.bg)
                self.rect_ax.draw_artist(self.rect_patch)
                canvas.blit(self.fig.bbox)
            else:
                canvas.draw_idle()
            return

        # 3. 普通鼠标移动：Blitting 极速更新 Crosshair 准星 (不触发完整数据重绘)
        if self.crosshair_lines:
            cur_x = event.xdata
            if self.bg is not None and not self._need_bg_update:
                canvas.restore_region(self.bg)
                for ax, line in self.crosshair_lines.items():
                    if ax in self.visualizer.axes:
                        line.set_xdata([cur_x, cur_x])
                        line.set_visible(True)
                        ax.draw_artist(line)
                canvas.blit(self.fig.bbox)
            else:
                for ax, line in self.crosshair_lines.items():
                    if ax in self.visualizer.axes:
                        line.set_xdata([cur_x, cur_x])
                        line.set_visible(True)
                canvas.draw_idle()

    def on_button_release(self, event):
        """鼠标按键释放处理：完成 Pan 或矩形选择缩放"""
        if self.is_panning:
            self.is_panning = False
            self.pan_start_event = None
            self.pan_start_pixel = None
            self._need_bg_update = True
            self.fig.canvas.draw_idle()

        if self.is_rect_zooming:
            self.is_rect_zooming = False
            if self.rect_patch:
                if self.rect_patch.axes:
                    self.rect_patch.remove()
                self.rect_patch = None

            if self.rect_start_pos and event.xdata is not None and event.ydata is not None and self.rect_ax:
                start_x, start_y = self.rect_start_pos
                end_x, end_y = event.xdata, event.ydata

                if abs(end_x - start_x) > 1e-6 and abs(end_y - start_y) > 1e-6:
                    self.push_view_history()
                    x_min, x_max = min(start_x, end_x), max(start_x, end_x)
                    y_min, y_max = min(start_y, end_y), max(start_y, end_y)

                    self.rect_ax.set_ylim(y_min, y_max)

                    if self.visualizer.sync_mode:
                        for sub_ax in self.visualizer.axes:
                            sub_ax.set_xlim(x_min, x_max)
                    else:
                        self.rect_ax.set_xlim(x_min, x_max)

            self.rect_start_pos = None
            self.rect_ax = None
            self._need_bg_update = True
            self.fig.canvas.draw_idle()

    def on_leave(self, event):
        """鼠标离开 subplot/figure 时隐藏 Crosshairs"""
        canvas = self.fig.canvas
        if self.bg is not None and not self._need_bg_update:
            canvas.restore_region(self.bg)
            for line in self.crosshair_lines.values():
                line.set_visible(False)
            canvas.blit(self.fig.bbox)
        else:
            for line in self.crosshair_lines.values():
                line.set_visible(False)
            canvas.draw_idle()
        if self.toolbar:
            self.toolbar.set_message("")

    def _update_readout_status(self, event):
        """更新格式化的 Time 与 Value 信息到 Toolbar 消息区域"""
        if not self.toolbar or event.xdata is None or event.ydata is None:
            return
        
        t_sec = event.xdata
        val = event.ydata
        
        if abs(t_sec) < 1.0:
            time_str = f"{t_sec * 1000.0:.2f} ms"
        else:
            time_str = f"{t_sec:.4f} s ({t_sec * 1000.0:.1f} ms)"
            
        msg = f"Time: {time_str} | Value: {val:.4g}"
        self.toolbar.set_message(msg)

    def reset_full_view(self, target_ax=None):
        """重置恢复 Full View"""
        if not self.visualizer.axes:
            return
        
        self.push_view_history()
        
        full_x_min, full_x_max = float('inf'), float('-inf')
        if hasattr(self.visualizer, 'current_time_axis') and self.visualizer.current_time_axis is not None:
            t_axis = self.visualizer.current_time_axis
            full_x_min, full_x_max = np.min(t_axis), np.max(t_axis)

        for ax in self.visualizer.axes:
            ax.autoscale(enable=True, axis='y')
            if full_x_min != float('inf') and full_x_max != float('-inf'):
                ax.set_xlim(full_x_min, full_x_max)
            else:
                ax.autoscale(enable=True, axis='x')

        self._need_bg_update = True
        self.fig.canvas.draw_idle()

    def set_view_window(self, window_sec):
        """快捷按指定时间跨度窗口 (sec) 查看数据"""
        if not self.visualizer.axes:
            return

        if window_sec is None or window_sec == "full":
            self.reset_full_view()
            return

        self.push_view_history()

        center_t = self.last_cursor_time
        primary_ax = self.visualizer.axes[0]
        cur_xlim = primary_ax.get_xlim()

        if center_t is None or center_t < cur_xlim[0] or center_t > cur_xlim[1]:
            center_t = (cur_xlim[0] + cur_xlim[1]) / 2.0

        half_w = float(window_sec) / 2.0
        new_xmin = center_t - half_w
        new_xmax = center_t + half_w

        if self.visualizer.sync_mode:
            for ax in self.visualizer.axes:
                ax.set_xlim(new_xmin, new_xmax)
        else:
            primary_ax.set_xlim(new_xmin, new_xmax)

        self._need_bg_update = True
        self.fig.canvas.draw_idle()
