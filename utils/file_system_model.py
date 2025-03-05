#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件系统模型适配器
"""

import sys
from PyQt6.QtCore import QFileInfo

# 创建一个基于标准目录模型的自定义模型替代QFileSystemModel
class CustomDirectoryModel:
    def __init__(self):
        try:
            from PyQt6.QtWidgets import QFileSystemModel
            self.model = QFileSystemModel()
        except ImportError:
            try:
                from PyQt6.QtCore import QFileSystemModel
                self.model = QFileSystemModel()
            except ImportError:
                try:
                    from PyQt6.QtGui import QFileSystemModel
                    self.model = QFileSystemModel()
                except ImportError:
                    print("Error: QFileSystemModel class not found in PyQt6")
                    sys.exit(1)
    
    def setRootPath(self, path):
        return self.model.setRootPath(path)
    
    def setFilter(self, filters):
        self.model.setFilter(filters)
    
    def setNameFilters(self, filters):
        self.model.setNameFilters(filters)
    
    def setNameFilterDisables(self, disable):
        # This method might have been removed or renamed in PyQt6
        # We'll ignore errors if it happens
        try:
            self.model.setNameFilterDisables(disable)
        except AttributeError:
            print("Warning: setNameFilterDisables method not available in current PyQt6 version")
    
    def index(self, path):
        return self.model.index(path)
    
    def filePath(self, index):
        return self.model.filePath(index)
    
    def fileInfo(self, index):
        try:
            return self.model.fileInfo(index)
        except AttributeError:
            # Fallback implementation if fileInfo is not available
            return QFileInfo(self.filePath(index))
            
    def data(self, index, role):
        return self.model.data(index, role)
