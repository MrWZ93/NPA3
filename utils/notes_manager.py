#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
笔记管理模块 - 增强版
支持直接在文件中存储笔记和独立备份
"""

import os
import json
import hashlib
import h5py
import logging
from datetime import datetime

class NotesManager:
    """Enhanced Notes Management Class"""
    def __init__(self, notes_dir="./notes"):
        self.notes_dir = notes_dir
        # 确保笔记目录存在
        if not os.path.exists(notes_dir):
            os.makedirs(notes_dir)
        # 创建索引文件路径
        self.index_file = os.path.join(notes_dir, "notes_index.json")
        # 加载或创建索引
        self.notes_index = self._load_index()
        
        # 配置日志
        self.logger = logging.getLogger("NotesManager")
    
    def _load_index(self):
        """加载笔记索引，如果不存在则创建一个新的"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                # 如果文件损坏或找不到，创建一个新的索引
                return {}
        return {}
    
    def _save_index(self):
        """保存笔记索引到文件"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.notes_index, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save notes index: {str(e)}")
            return False
    
    def _generate_file_id(self, file_path):
        """
        生成文件的唯一标识符
        使用文件路径和修改时间创建哈希
        """
        try:
            file_stat = os.stat(file_path)
            # 使用文件路径、大小和修改时间生成哈希
            unique_str = f"{file_path}-{file_stat.st_size}-{file_stat.st_mtime}"
            file_id = hashlib.md5(unique_str.encode()).hexdigest()
            return file_id
        except FileNotFoundError:
            # 如果文件不存在，只使用路径
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def _get_backup_path(self, file_path):
        """获取备份笔记文件的路径"""
        file_id = self._generate_file_id(file_path)
        file_name = os.path.basename(file_path)
        # 创建包含文件ID的备份路径
        return os.path.join(self.notes_dir, f"{file_name}_{file_id}.txt")
    
    def _store_in_file(self, file_path, note_text):
        """尝试将笔记直接存储在文件中（如H5格式）"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            # 支持H5文件格式
            if ext == '.h5':
                with h5py.File(file_path, 'a') as h5file:
                    # 如果元数据组不存在则创建
                    if 'metadata' not in h5file:
                        metadata_group = h5file.create_group('metadata')
                    else:
                        metadata_group = h5file['metadata']
                    
                    # 存储笔记及其时间戳
                    if 'note' in metadata_group.attrs:
                        del metadata_group.attrs['note']
                    metadata_group.attrs['note'] = note_text
                    metadata_group.attrs['note_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return True
                
            # 可以添加对其他支持元数据的文件格式的支持
            
            # 如果不是支持的格式，返回False
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to store note in file {file_path}: {str(e)}")
            return False
    
    def _read_from_file(self, file_path):
        """尝试从文件中直接读取笔记（如H5格式）"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            # 支持H5文件格式
            if ext == '.h5':
                with h5py.File(file_path, 'r') as h5file:
                    if 'metadata' in h5file and 'note' in h5file['metadata'].attrs:
                        return h5file['metadata'].attrs['note']
            
            # 可以添加对其他支持元数据的文件格式的支持
            
            # 如果没有找到笔记，返回空字符串
            return ""
            
        except Exception as e:
            self.logger.warning(f"Failed to read note from file {file_path}: {str(e)}")
            return ""
    
    def load_note(self, file_path):
        """加载文件笔记，先尝试从文件自身读取，然后尝试从备份中读取"""
        # 首先尝试从文件自身读取
        note_text = self._read_from_file(file_path)
        if note_text:
            return note_text
        
        # 如果文件中没有笔记，尝试从备份中读取
        backup_path = self._get_backup_path(file_path)
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self.logger.error(f"Failed to read note from backup {backup_path}: {str(e)}")
        
        # 如果文件已经更新但使用了相同的名称，尝试查找索引
        file_id = self._generate_file_id(file_path)
        file_name = os.path.basename(file_path)
        
        # 检查索引中是否有该文件的记录
        if file_name in self.notes_index:
            # 尝试找到匹配的file_id
            for stored_id, note_path in self.notes_index[file_name].items():
                if stored_id == file_id and os.path.exists(note_path):
                    try:
                        with open(note_path, 'r', encoding='utf-8') as f:
                            return f.read()
                    except Exception as e:
                        self.logger.error(f"Failed to read note from indexed path {note_path}: {str(e)}")
        
        return ""
    
    def save_note(self, file_path, note_text):
        """保存文件笔记，同时尝试存储在文件自身和备份"""
        success = True
        
        # 获取文件ID和备份路径
        file_id = self._generate_file_id(file_path)
        backup_path = self._get_backup_path(file_path)
        file_name = os.path.basename(file_path)
        
        # 尝试直接存储到文件
        in_file_success = self._store_in_file(file_path, note_text)
        
        # 无论是否成功存储到文件，都创建备份
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(note_text)
            
            # 更新索引
            if file_name not in self.notes_index:
                self.notes_index[file_name] = {}
            
            self.notes_index[file_name][file_id] = backup_path
            self._save_index()
            
        except Exception as e:
            self.logger.error(f"Failed to save note backup for {file_path}: {str(e)}")
            success = False
        
        return success and (in_file_success or os.path.exists(backup_path))
    
    def delete_note(self, file_path):
        """删除文件的笔记"""
        success = True
        file_id = self._generate_file_id(file_path)
        file_name = os.path.basename(file_path)
        
        # 尝试从文件自身中删除笔记
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.h5':
                with h5py.File(file_path, 'a') as h5file:
                    if 'metadata' in h5file and 'note' in h5file['metadata'].attrs:
                        del h5file['metadata'].attrs['note']
        except Exception as e:
            self.logger.warning(f"Failed to delete note from file {file_path}: {str(e)}")
            # 这不会导致整个操作失败
        
        # 删除备份文件
        backup_path = self._get_backup_path(file_path)
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception as e:
                self.logger.error(f"Failed to delete note backup {backup_path}: {str(e)}")
                success = False
        
        # 从索引中删除
        if file_name in self.notes_index and file_id in self.notes_index[file_name]:
            del self.notes_index[file_name][file_id]
            if not self.notes_index[file_name]:  # 如果文件名下没有任何ID
                del self.notes_index[file_name]
            self._save_index()
        
        return success
    
    def list_all_notes(self):
        """列出所有笔记文件的索引"""
        return self.notes_index
