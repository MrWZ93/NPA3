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
                            QFrame, QToolButton, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor, QBrush, QFont, QAction


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
        
        # 显示文本
        display_text = f"Fit {fit_index}: μ={mu:.4f}, FWHM={fwhm:.4f}"
        
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
    fit_edited = pyqtSignal(int, dict)  # 编辑拟合项时发送索引和新参数
    export_all_fits = pyqtSignal()  # 导出所有拟合数据
    copy_all_fits = pyqtSignal()    # 复制所有拟合数据
    
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
        
        # 添加工具按钮
        self.export_btn = QToolButton()
        self.export_btn.setText("Export")
        self.export_btn.setToolTip("Export all fit data to CSV")
        
        self.copy_btn = QToolButton()
        self.copy_btn.setText("Copy")
        self.copy_btn.setToolTip("Copy all fit data to clipboard")
        
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.export_btn)
        title_layout.addWidget(self.copy_btn)
        
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
        self.fit_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.fit_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        layout.addWidget(self.fit_list)
        
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
        self.export_btn.clicked.connect(self.export_all_fits.emit)
        self.copy_btn.clicked.connect(self.copy_all_fits.emit)
        
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
            
            # 自动选择第一个项目
            self.fit_list.setCurrentRow(0)
        
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
                
                # 更新显示文本
                item.setText(f"Fit {fit_index}: μ={mu:.4f}, FWHM={fwhm:.4f}")
                
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
            data = item.data(Qt.ItemDataRole.UserRole)
            if data['fit_index'] == fit_index:
                # 从列表中移除项目
                self.fit_list.takeItem(i)
                
                # 如果列表为空，显示提示信息并隐藏列表和统计区域
                if self.fit_list.count() == 0:
                    self.info_label.show()
                    self.fit_list.hide()
                    self.stats_group.hide()
                
                break
    
    def clear_all_fits(self):
        """清除所有拟合项目"""
        self.fit_list.clear()
        self.info_label.show()
        self.fit_list.hide()
        self.stats_group.hide()
    
    def on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.fit_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            data = item.data(Qt.ItemDataRole.UserRole)
            
            # 更新统计信息
            self.update_stats_info(data)
            
            # 发送选中信号
            self.fit_selected.emit(data['fit_index'])
    
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
        """删除拟合项目"""
        data = item.data(Qt.ItemDataRole.UserRole)
        
        # 发送删除信号
        self.fit_deleted.emit(data['fit_index'])
