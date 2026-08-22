#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matplotlib 画布交互控制器 (连贯渐变缩放与全新鼠标按键映射优化版)
封装高级鼠标交互：
- 左键拖拽：平移移动视图 (Left-Click Drag Pan)
- 右键拖拽：直接框选区域放大 (Right-Click Drag Rubberband Box Zoom)
- 单击右键：逐级撤销视图历史 (Right-Click Undo)
- 双击左键：恢复 Full View
- 滚轮：30 FPS 连贯渐变 X 轴缩放
- Shift+滚轮：Y 轴缩放
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
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
        
        # 防抖/延迟渲染控制
        self.draw_timer = QTimer()
        self.draw_timer.setSingleShot(True)
        self.draw_timer.timeout.connect(self._deferred_draw)
        self.last_scroll_render_time = 0
        
        # 交互状态 - 左键平移
        self.is_panning = False
        self.pan_start_event = None
        self.pan_start_pixel = None  # (pixel_x, pixel_y)
        self.pan_init_limits = {}
        self.pan_has_moved = False
        
        # 交互状态 - 右键直接框选放大
        self.is_rect_zooming = False
        self.rect_start_pos = None  # (xdata, ydata)
        self.rect_start_pixel = None  # (pixel_x, pixel_y)
        self.rect_ax = None
        self.rect_patch = None
        self.rect_has_moved = False  # 用于区分右键单击撤销与右键拖拽框选
        
        # 十字准星与坐标记录
        self.crosshair_lines = {}  # {ax: Line2D}
        self.last_cursor_time = None
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
        if not self.history_stack and self.visualizer.axes:
            self.push_view_history()

    def on_draw(self, event):
        """画布重绘后捕获背景图像用于 Blitting 准星绘制"""
        if event.canvas != self.fig.canvas:
            return
        self.bg = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        self._need_bg_update = False

    def _setup_crosshairs(self):
        """为所有 Subplot 初始化淡色垂直 Crosshair 虚线"""
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
        
        self._deferred_draw()
        return True

    def _deferred_draw(self):
        """触发图形重绘"""
        self._need_bg_update = True
        self.fig.canvas.draw_idle()

    def on_scroll(self, event):
        """鼠标滚轮事件处理：渐变连贯 X/Y 轴缩放"""
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

        # 基准单步缩放比例：4.0% (0.96)
        step_mag = min(abs(step), 2.0)
        if step > 0:
            scale_factor = 0.96 ** step_mag
        else:
            scale_factor = (1.0 / 0.96) ** step_mag

        if time.time() - self.last_history_push_time > 0.4:
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

        # 核心改进：30 FPS (33ms) 渐变连贯重绘！
        # 确保在连续滚动过程中画面平滑缩放，用户能清楚看见放大缩小的渐变过程
        now = time.time()
        if now - self.last_scroll_render_time >= 0.033:
            self.fig.canvas.draw_idle()
            self.last_scroll_render_time = now
            self.draw_timer.stop()
        else:
            self.draw_timer.start(35)

    def on_button_press(self, event):
        """按键按下处理：左键拖拽平移、右键框选放大、双击恢复全图"""
        if self.is_toolbar_active():
            return
        if event.inaxes is None:
            return

        # 1. 左键双击 (button == 1 & dblclick)：恢复 Full View
        if event.button == 1 and getattr(event, 'dblclick', False):
            self.reset_full_view(target_ax=event.inaxes)
            return

        # 2. 按住左键拖动：平移移动视图
        if event.button == 1:
            self.is_panning = True
            self.pan_start_event = event
            self.pan_start_pixel = (event.x, event.y)
            self.pan_init_limits = {sub_ax: (sub_ax.get_xlim(), sub_ax.get_ylim()) for sub_ax in self.visualizer.axes}
            self.pan_has_moved = False
            return

        # 3. 按住右键拖动：矩形框选放大区域
        if event.button == 3:
            self.is_rect_zooming = True
            self.rect_ax = event.inaxes
            self.rect_start_pos = (event.xdata, event.ydata)
            self.rect_start_pixel = (event.x, event.y)
            self.rect_has_moved = False

            if self.rect_patch and self.rect_patch.axes:
                self.rect_patch.remove()
            self.rect_patch = Rectangle(
                (event.xdata, event.ydata), 0, 0,
                fill=True, facecolor='#0078d7', edgecolor='#0078d7',
                alpha=0.25, linestyle='--'
            )
            self.rect_patch.set_animated(True)
            self.rect_ax.add_patch(self.rect_patch)
            return

    def on_motion_notify(self, event):
        """鼠标移动处理：左键绝对像素 Pan 平移、右键框选显示、Crosshair 准星 Blitting 绘制"""
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            self.on_leave(event)
            return

        self.last_cursor_time = event.xdata
        self.last_cursor_val = event.ydata
        self._update_readout_status(event)

        if self.is_toolbar_active():
            return

        canvas = self.fig.canvas

        # 1. 处理左键拖拽平移 (Left-Click Drag Pan)
        if self.is_panning and self.pan_start_pixel and self.pan_start_event:
            dx_pix = event.x - self.pan_start_pixel[0]
            dy_pix = event.y - self.pan_start_pixel[1]

            # 只要像素移动大于 3px，就认定为拖拽
            if abs(dx_pix) > 3 or abs(dy_pix) > 3:
                if not self.pan_has_moved:
                    self.pan_has_moved = True
                    self.push_view_history()

            pan_ax = self.pan_start_event.inaxes
            if pan_ax in self.pan_init_limits:
                bbox = pan_ax.get_window_extent()
                if bbox.width > 0 and bbox.height > 0:
                    orig_xlim, orig_ylim = self.pan_init_limits[pan_ax]
                    x_per_pix = (orig_xlim[1] - orig_xlim[0]) / bbox.width
                    y_per_pix = (orig_ylim[1] - orig_ylim[0]) / bbox.height

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
                    now = time.time()
                    if now - self.last_scroll_render_time >= 0.033:
                        canvas.draw_idle()
                        self.last_scroll_render_time = now
                    else:
                        if not self.draw_timer.isActive():
                            self.draw_timer.start(35)
            return

        # 2. 处理右键直接框选放大 (Right-Click Drag Rubberband Zoom)
        if self.is_rect_zooming and self.rect_patch and self.rect_start_pos:
            if self.rect_start_pixel:
                dx_pix = event.x - self.rect_start_pixel[0]
                dy_pix = event.y - self.rect_start_pixel[1]
                if abs(dx_pix) > 3 or abs(dy_pix) > 3:
                    self.rect_has_moved = True

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
                self.draw_timer.start(16)
            return

        # 3. 普通鼠标移动：Blitting 极速更新 Crosshair 准星
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
                self.draw_timer.start(16)

    def on_button_release(self, event):
        """按键释放处理：左键完成平移、右键完成框选放大或判断为单击右键撤销"""
        # 左键释放：完成平移
        if self.is_panning and event.button == 1:
            self.is_panning = False
            self._deferred_draw()
            self.pan_start_event = None
            self.pan_start_pixel = None
            self.pan_has_moved = False
            return

        # 右键释放：完成框选放大，若未拖拽（单击右键）则判定为撤销 (Undo)
        if self.is_rect_zooming and event.button == 3:
            self.is_rect_zooming = False
            if self.rect_patch:
                if self.rect_patch.axes:
                    self.rect_patch.remove()
                self.rect_patch = None

            did_zoom = False
            if self.rect_has_moved and self.rect_start_pos and event.xdata is not None and event.ydata is not None and self.rect_ax:
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
                    did_zoom = True

            self.rect_start_pos = None
            self.rect_start_pixel = None
            self.rect_ax = None

            if not did_zoom and not self.rect_has_moved:
                # 没移动，视为右键单击撤销
                self.pop_view_history()
            else:
                self._deferred_draw()
            return

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
            self._deferred_draw()
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

        self._deferred_draw()

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

        self._deferred_draw()
