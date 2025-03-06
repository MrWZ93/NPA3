#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error Handler - 错误处理模块
提供集中化的错误处理功能
"""

import traceback
from PyQt6.QtWidgets import QMessageBox

class ErrorHandler:
    """集中化错误处理类"""
    
    @staticmethod
    def handle_error(parent, error, title="Error", show_traceback=True, show_message=True, 
                    log_error=True, status_bar=None):
        """集中处理错误
        
        Args:
            parent: 父窗口对象
            error: 错误对象或错误消息字符串
            title: 对话框标题
            show_traceback: 是否打印堆栈跟踪
            show_message: 是否显示消息框
            log_error: 是否记录错误到日志
            status_bar: 状态栏对象（可选）
        
        Returns:
            str: 格式化的错误消息
        """
        # 获取错误消息
        if isinstance(error, Exception):
            error_msg = str(error)
        else:
            error_msg = str(error)
        
        # 打印堆栈跟踪
        if show_traceback:
            traceback.print_exc()
        
        # 记录错误到日志
        if log_error:
            import logging
            logging.error(f"{title}: {error_msg}")
            if show_traceback:
                logging.error(traceback.format_exc())
        
        # 更新状态栏
        if status_bar:
            status_bar.showMessage(f"Error: {error_msg}")
        
        # 显示消息框
        if show_message and parent:
            QMessageBox.critical(
                parent,
                title,
                error_msg
            )
        
        return error_msg
    
    @staticmethod
    def show_warning(parent, message, title="Warning", status_bar=None):
        """显示警告消息
        
        Args:
            parent: 父窗口对象
            message: 警告消息
            title: 对话框标题
            status_bar: 状态栏对象（可选）
        """
        if status_bar:
            status_bar.showMessage(f"Warning: {message}")
            
        QMessageBox.warning(
            parent,
            title,
            message
        )
    
    @staticmethod
    def show_info(parent, message, title="Information", status_bar=None):
        """显示信息消息
        
        Args:
            parent: 父窗口对象
            message: 信息消息
            title: 对话框标题
            status_bar: 状态栏对象（可选）
        """
        if status_bar:
            status_bar.showMessage(message)
            
        QMessageBox.information(
            parent,
            title,
            message
        )
