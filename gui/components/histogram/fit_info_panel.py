#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fit Info Panel - 拟合信息面板
提供拟合结果的显示和交互功能
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QListWidget, QListWidgetItem, 
                            QAbstractItemView, QMenu, QDialog, QFormLayout,
                            QDoubleSpinBox, QTabWidget, QGroupBox, QSplitter,
                            QFrame, QToolButton, QLineEdit, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint, QItemSelectionModel
from PyQt6.QtGui import QColor, QBrush, QFont, QAction, QIcon


class FitListItem(QListWidgetItem):
    """拟合项目列表项"""
    
    def __init__(self, fit_index, amp, mu, sigma, fwhm, x_range, color, parent=None):
        """初始化拟合列表项"""
        # 生成显示文本
        self.fit_index = fit_index
        self.popt = (amp, mu, sigma)
        self.fwhm = fwhm
        self.x_range = x_range
        self.color = color
        
        # 显示文本（添加sigma信息）
        display_text = f"Fit {fit_index}: μ={mu:.4f}, σ={sigma:.4f}, FWHM={fwhm:.4f}"
        
        # 初始化父类
        super(FitListItem, self).__init__(display_text, parent)
        
        # 设置颜色
        self.setForeground(QBrush(QColor(color)))
        
        # 设置提示文本
        tooltip = (f"Amplitude: {amp:.2f}\n"
                  f"Peak position (μ): {mu:.4f}\n"
                  f"Sigma (σ): {sigma:.4f}\n"
                  f"FWHM: {fwhm:.4f}\n"
                  f"Range: {x_range[0]:.3f} - {x_range[1]:.3f}")
        self.setToolTip(tooltip)
        
        # 显示置置一些调试信息
        print(f"Creating list item: {display_text}")
        
        # 存储额外数据
        self.setData(Qt.ItemDataRole.UserRole, {
            'fit_index': fit_index,
            'amp': amp,
            'mu': mu,
            'sigma': sigma,
            'fwhm': fwhm,
            'x_range': x_range,
            'color': color
        })


class FitEditDialog(QDialog):
    """拟合参数编辑对话框"""
    
    def __init__(self, fit_data, parent=None):
        super(FitEditDialog, self).__init__(parent)
        self.setWindowTitle("Edit Fit Parameters")
        self.resize(350, 200)
        
        # 存储初始数据
        self.fit_data = fit_data
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 参数编辑区
        param_group = QGroupBox("Parameters")
        form_layout = QFormLayout(param_group)
        
        # 振幅
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0.1, 1000000)
        self.amp_spin.setDecimals(2)
        self.amp_spin.setValue(fit_data['amp'])
        form_layout.addRow("Amplitude:", self.amp_spin)
        
        # 峰位置
        self.mu_spin = QDoubleSpinBox()
        self.mu_spin.setRange(-1000000, 1000000)
        self.mu_spin.setDecimals(4)
        self.mu_spin.setValue(fit_data['mu'])
        form_layout.addRow("Peak position (μ):", self.mu_spin)
        
        # Sigma
        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.0001, 1000000)
        self.sigma_spin.setDecimals(4)
        self.sigma_spin.setValue(fit_data['sigma'])
        form_layout.addRow("Sigma (σ):", self.sigma_spin)
        
        # FWHM（只读，自动计算）
        self.fwhm_label = QLineEdit()
        self.fwhm_label.setReadOnly(True)
        self.fwhm_label.setText(f"{fit_data['fwhm']:.4f}")
        form_layout.addRow("FWHM:", self.fwhm_label)
        
        # Sigma 改变时更新 FWHM
        self.sigma_spin.valueChanged.connect(self.update_fwhm)
        
        # 添加表单到布局
        layout.addWidget(param_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
    
    def update_fwhm(self):
        """更新 FWHM 值"""
        sigma = self.sigma_spin.value()
        fwhm = 2.355 * sigma
        self.fwhm_label.setText(f"{fwhm:.4f}")
    
    def get_edited_data(self):
        """获取编辑后的数据"""
        # 复制原始数据
        data = self.fit_data.copy()
        
        # 更新编辑的值
        data['amp'] = self.amp_spin.value()
        data['mu'] = self.mu_spin.value()
        data['sigma'] = self.sigma_spin.value()
        data['fwhm'] = 2.355 * data['sigma']
        
        return data


class FitInfoPanel(QWidget):
    """拟合信息面板"""
    
    # 定义信号
    fit_selected = pyqtSignal(int)  # 选中拟合项时发送索引
    fit_deleted = pyqtSignal(int)   # 删除拟合项时发送索引
    fits_deleted = pyqtSignal(list)  # 删除多个拟合项时发送索引列表
    fit_edited = pyqtSignal(int, dict)  # 编辑拟合项时发送索引和新参数
    export_all_fits = pyqtSignal()  # 导出所有拟合数据
    copy_all_fits = pyqtSignal()    # 复制所有拟合数据
    toggle_fit_labels = pyqtSignal(bool)  # 切换拟合标签的可见性
    
    def __init__(self, parent=None):
        super(FitInfoPanel, self).__init__(parent)
        
        # 打印调试信息
        print("Initializing FitInfoPanel")
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("Fit Results")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        
        # Copy按钮
        self.copy_btn = QToolButton()
        self.copy_btn.setText("Copy")
        self.copy_btn.setToolTip("Copy all fit data to clipboard")
        
        # μσ复制按钮
        self.copy_mu_sigma_btn = QToolButton()
        self.copy_mu_sigma_btn.setText("μσ")
        self.copy_mu_sigma_btn.setToolTip("Copy μ and σ values to clipboard for Excel")
        
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.copy_btn)
        title_layout.addWidget(self.copy_mu_sigma_btn)
        
        layout.addLayout(title_layout)
        
        # 提示信息
        self.info_label = QLabel("No fits yet. Select regions for Gaussian fitting.")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.info_label)
        
        # 拟合列表
        self.fit_list = QListWidget()
        self.fit_list.setAlternatingRowColors(True)
        self.fit_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.fit_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        layout.addWidget(self.fit_list)
        
        # 添加按钮区域
        button_layout = QHBoxLayout()
        
        # 删除选中项按钮
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setToolTip("Delete selected fit(s)")
        self.delete_selected_btn.setEnabled(False)  # 初始禁用
        
        # 切换拟合标签可见性按钮
        self.toggle_labels_btn = QPushButton("Hide Labels")
        self.toggle_labels_btn.setToolTip("Hide/Show fit labels in the plot")
        self.toggle_labels_btn.setCheckable(True)
        
        # 添加按钮到布局
        button_layout.addWidget(self.delete_selected_btn)
        button_layout.addWidget(self.toggle_labels_btn)
        
        layout.addLayout(button_layout)
        
        # 统计信息区域
        self.stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(self.stats_group)
        
        self.stats_label = QLabel("Select a fit to view its details")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(self.stats_group)
        
        # 隐藏列表和统计信息，直到有拟合结果
        self.fit_list.hide()
        self.stats_group.hide()
        
        # 打印调试信息
        print("Connecting signals in FitInfoPanel")
        
        # 连接信号
        self.fit_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.fit_list.customContextMenuRequested.connect(self.show_context_menu)
        self.copy_btn.clicked.connect(self.copy_all_fits.emit)
        self.copy_mu_sigma_btn.clicked.connect(self.copy_mu_sigma_values)
        self.delete_selected_btn.clicked.connect(self.delete_selected_fits)
        self.toggle_labels_btn.clicked.connect(self.on_toggle_labels)
        
        # 打印调试信息
        print("FitInfoPanel initialized")
    
    def add_fit(self, fit_index, amp, mu, sigma, x_range, color):
        """添加拟合项目到列表"""
        # 计算FWHM
        fwhm = 2.355 * sigma
        
        # 创建列表项
        item = FitListItem(fit_index, amp, mu, sigma, fwhm, x_range, color)
        
        # 添加到列表
        self.fit_list.addItem(item)
        
        # 如果是第一个项目，显示列表和统计信息区域
        if self.fit_list.count() == 1:
            self.info_label.hide()
            self.fit_list.show()
            self.stats_group.show()
            # 不自动选择任何项目，允许所有曲线都不被选中
            # 更新统计信息显示为未选择状态
            self.stats_label.setText("No fits selected. All curves have the same thickness.")
        
        # 打印调试信息
        print(f"Added fit to panel: {fit_index}, {amp:.2f}, {mu:.4f}, {sigma:.4f}, FWHM={fwhm:.4f}")
        print(f"Current fit count: {self.fit_list.count()}")
    
    def update_fit(self, fit_index, amp, mu, sigma, x_range, color):
        """更新拟合项目"""
        # 计算FWHM
        fwhm = 2.355 * sigma
        
        # 查找对应项目
        for i in range(self.fit_list.count()):
            item = self.fit_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data['fit_index'] == fit_index:
                # 更新项目数据
                new_data = data.copy()
                new_data.update({
                    'amp': amp,
                    'mu': mu,
                    'sigma': sigma,
                    'fwhm': fwhm,
                    'x_range': x_range,
                    'color': color
                })
                
                # 更新显示文本（添加sigma信息）
                item.setText(f"Fit {fit_index}: μ={mu:.4f}, σ={sigma:.4f}, FWHM={fwhm:.4f}")
                
                # 更新提示文本
                tooltip = (f"Amplitude: {amp:.2f}\n"
                          f"Peak position (μ): {mu:.4f}\n"
                          f"Sigma (σ): {sigma:.4f}\n"
                          f"FWHM: {fwhm:.4f}\n"
                          f"Range: {x_range[0]:.3f} - {x_range[1]:.3f}")
                item.setToolTip(tooltip)
                
                # 更新存储数据
                item.setData(Qt.ItemDataRole.UserRole, new_data)
                
                # 如果当前选中的是此项目，更新统计信息
                if self.fit_list.currentRow() == i:
                    self.update_stats_info(new_data)
                
                break
    
    def remove_fit(self, fit_index):
        """从列表中移除拟合项目"""
        for i in range(self.fit_list.count()):
            item = self.fit_list.item(i)
            if item is None:
                continue
                
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data['fit_index'] == fit_index:
                # 从列表中移除项目
                taken_item = self.fit_list.takeItem(i)
                
                # 如果列表为空，显示提示信息并隐藏列表和统计区域
                if self.fit_list.count() == 0:
                    self.info_label.show()
                    self.fit_list.hide()
                    self.stats_group.hide()
                
                print(f"Removed fit {fit_index} from panel")
                return True
        
        print(f"Could not find fit {fit_index} to remove from panel")
        return False
    
    def clear_all_fits(self):
        """清除所有拟合项目"""
        self.fit_list.clear()
        self.info_label.show()
        self.fit_list.hide()
        self.stats_group.hide()
        # 确保在清除所有拟合后，取消任何高亮状态
        self.fit_selected.emit(-1)
    
    def on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.fit_list.selectedItems()
        
        # 根据选择状态启用/禁用删除按钮
        self.delete_selected_btn.setEnabled(len(selected_items) > 0)
        
        if len(selected_items) == 1:
            # 单选情况：更新统计信息并发送选中信号
            item = selected_items[0]
            data = item.data(Qt.ItemDataRole.UserRole)
            
            # 更新统计信息
            self.update_stats_info(data)
            
            # 发送选中信号
            self.fit_selected.emit(data['fit_index'])
        elif len(selected_items) > 1:
            # 多选情况：显示多选状态的统计信息
            self.stats_label.setText(f"<b>{len(selected_items)} fits selected</b><br>Select a single fit to view details")
            # 取消所有高亮，允许所有曲线都不被选中
            self.fit_selected.emit(-1)
        else:
            # 未选择任何项时，允许所有曲线都不被选中
            self.stats_label.setText("No fits selected. All curves have the same thickness.")
            # 取消所有高亮，所有曲线保持相同粗细
            self.fit_selected.emit(-1)
    
    def update_stats_info(self, data):
        """更新统计信息区域"""
        amp = data['amp']
        mu = data['mu']
        sigma = data['sigma']
        fwhm = data['fwhm']
        x_min, x_max = data['x_range']
        
        # 设置统计信息文本
        stats_text = (f"<b>Amplitude:</b> {amp:.2f}<br>"
                     f"<b>Peak position (μ):</b> {mu:.4f}<br>"
                     f"<b>Sigma (σ):</b> {sigma:.4f}<br>"
                     f"<b>FWHM:</b> {fwhm:.4f}<br>"
                     f"<b>Range:</b> {x_min:.3f} - {x_max:.3f}")
        
        self.stats_label.setText(stats_text)
    
    def show_context_menu(self, pos):
        """显示上下文菜单"""
        item = self.fit_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            
            # 编辑操作
            edit_action = QAction("Edit Parameters", self)
            edit_action.triggered.connect(lambda: self.edit_fit_parameters(item))
            
            # 删除操作
            delete_action = QAction("Delete Fit", self)
            delete_action.triggered.connect(lambda: self.delete_fit(item))
            
            # 添加操作到菜单
            menu.addAction(edit_action)
            menu.addAction(delete_action)
            
            # 显示菜单
            menu.exec(self.fit_list.mapToGlobal(pos))
    
    def edit_fit_parameters(self, item):
        """编辑拟合参数"""
        data = item.data(Qt.ItemDataRole.UserRole)
        
        # 创建编辑对话框
        dialog = FitEditDialog(data, self)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            # 获取编辑后的数据
            edited_data = dialog.get_edited_data()
            
            # 发送编辑信号
            self.fit_edited.emit(data['fit_index'], edited_data)
    
    def delete_fit(self, item):
        """删除单个拟合项目"""
        data = item.data(Qt.ItemDataRole.UserRole)
        
        # 发送删除信号
        self.fit_deleted.emit(data['fit_index'])
        
    def delete_selected_fits(self):
        """删除所有选中的拟合项目"""
        selected_items = self.fit_list.selectedItems()
        if not selected_items:
            return
            
        # 收集所有选中项的索引
        fit_indices = []
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            fit_indices.append(data['fit_index'])
        
        # 如果只选择了一个项目，使用单项删除信号
        if len(fit_indices) == 1:
            self.fit_deleted.emit(fit_indices[0])
        else:
            # 发送多项删除信号
            self.fits_deleted.emit(fit_indices)
            
    def on_toggle_labels(self, checked):
        """切换拟合标签的可见性"""
        # 更新按钮文本
        self.toggle_labels_btn.setText("Show Labels" if checked else "Hide Labels")
        
        # 发送信号通知控制器
        self.toggle_fit_labels.emit(not checked)  # 传递相反的值，因为checked=True表示按钮被按下，即隐藏标签
    
    def copy_mu_sigma_values(self):
        """复制所有拟合结果的μ和σ值到剪贴板，适合Excel格式"""
        if self.fit_list.count() == 0:
            return
        
        # 收集所有拟合的μ和σ值，每行一个拟合结果
        rows = []
        
        for i in range(self.fit_list.count()):
            item = self.fit_list.item(i)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    # 每行格式：μ值 \t σ值
                    row = f"{data['mu']:.4f}\t{data['sigma']:.4f}"
                    rows.append(row)
        
        # 创建适合Excel的格式（每行包含一个拟合的μ和σ值）
        clipboard_text = "\n".join(rows)
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)
        
        print(f"Copied μ and σ values to clipboard: {len(rows)} fits")
