# NPA - 数据可视化和分析工具

## 项目概述

NPA是一个多格式数据可视化与分析工具，支持读取多种实验数据文件格式（TDMS、H5、ABF、CSV等），提供数据可视化、分析和处理功能。

## 特性

- 支持多种数据格式的读取和可视化
- 直观的图形用户界面
- 数据处理功能（滤波、基线校正、裁剪等）
- 处理结果保存与管理
- 文件笔记功能

## 安装指南

### 使用虚拟环境（推荐）

#### Unix/macOS系统:

```bash
# 创建并配置虚拟环境
./setup_venv.sh

# 激活虚拟环境
source activate.sh

# 运行应用程序
python main.py
```

#### Windows系统:

```cmd
# 创建并配置虚拟环境
setup_venv.bat

# 激活虚拟环境
activate.bat

# 运行应用程序
python main.py
```

### 手动安装依赖

如果不使用虚拟环境，可以直接安装依赖：

```bash
pip install -r requirements.txt
```

## 项目结构

```
NPA/
├── main.py           # 程序入口点
├── core/             # 核心功能模块
│   ├── data_processor.py     # 数据处理功能
│   └── data_visualizer.py    # 数据可视化组件
├── gui/              # 界面组件
│   ├── main_window.py        # 主窗口
│   ├── tabs.py               # 标签页组件
│   └── processed_files_widget.py # 处理文件组件
└── utils/            # 工具模块
    ├── notes_manager.py      # 笔记管理功能
    └── file_system_model.py  # 文件系统模型
```

## 可选依赖

- `nptdms`: 用于支持TDMS文件格式
- `pyabf`: 用于支持ABF文件格式

## 使用方法

1. 通过"Browse..."按钮浏览并选择包含数据文件的文件夹
2. 从文件列表中选择要分析的文件
3. 查看文件详情和图表可视化
4. 使用处理标签页进行数据处理
5. 保存处理结果并在右侧面板查看

## 许可证

[项目许可证信息]
