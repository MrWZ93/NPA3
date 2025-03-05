# NPA3 - 神经物理数据可视化与分析工具 | Neural Physics Data Visualization and Analysis Tool

## 项目概述 | Project Overview

NPA3是一个多格式神经物理数据可视化与分析工具，支持读取多种实验数据文件格式（TDMS、H5、ABF、CSV等），提供图形化界面，集成了数据可视化、分析和处理功能。

NPA3 is a multi-format neural physics data visualization and analysis tool that supports reading various experimental data file formats (TDMS, H5, ABF, CSV, etc.), providing a graphical interface with integrated data visualization, analysis, and processing capabilities.

## 主要特性 | Key Features

- **多格式支持**: 支持TDMS、H5、ABF和CSV等多种数据格式的读取和可视化
- **强大的CSV支持**: 优化的CSV加载器，支持示波器CSV格式和大文件处理
- **图形化界面**: 直观的三区域布局，包括文件浏览器、可视化区域和处理文件区域
- **数据处理功能**: 多种数据处理工具，包括低通/高通滤波、基线校正、数据裁剪等
- **高级分析工具**: 包括PSD分析器、曲线拟合工具和峰值检测器
- **文件管理**: 处理后文件的保存和管理
- **笔记功能**: 为数据文件添加笔记和注释
- **可视化控制**: 细粒度控制可视化参数，包括采样率、通道选择、图表高度等
- **侧边栏折叠**: 支持折叠左右侧边栏以专注于可视化

---

- **Multi-format Support**: Read and visualize data in TDMS, H5, ABF, and CSV formats
- **Robust CSV Support**: Optimized CSV loader with oscilloscope CSV format support and large file handling
- **Graphical Interface**: Intuitive three-area layout with file browser, visualization area, and processed files area
- **Data Processing**: Various data processing tools including low-pass/high-pass filtering, baseline correction, and data trimming
- **Advanced Analysis Tools**: Including PSD analyzer, curve fitting tool, and spike detector
- **File Management**: Save and manage processed files
- **Notes Feature**: Add notes and annotations to data files
- **Visualization Controls**: Fine-grained control of visualization parameters including sampling rate, channel selection, and chart heights
- **Collapsible Sidebars**: Ability to collapse left and right sidebars to focus on visualization

## 安装指南 | Installation Guide

### 使用虚拟环境（推荐）| Using Virtual Environment (Recommended)

#### Unix/macOS系统 | Unix/macOS Systems:

```bash
# 创建并配置虚拟环境 | Create and configure virtual environment
./setup_venv.sh

# 激活虚拟环境 | Activate virtual environment
source activate.sh

# 运行应用程序 | Run the application
python main.py
```

#### Windows系统 | Windows Systems:

```cmd
# 创建并配置虚拟环境 | Create and configure virtual environment
setup_venv.bat

# 激活虚拟环境 | Activate virtual environment
activate.bat

# 运行应用程序 | Run the application
python main.py
```

### 手动安装依赖 | Manual Dependency Installation

如果不使用虚拟环境，可以直接安装依赖：

If you prefer not to use a virtual environment, you can install dependencies directly:

```bash
pip install -r requirements.txt
```

## 依赖项 | Dependencies

主要依赖项包括：

Main dependencies include:

- PyQt6: 用于图形用户界面 | For graphical user interface
- numpy, pandas: 用于数据处理 | For data processing
- matplotlib: 用于数据可视化 | For data visualization
- scipy: 用于信号处理 | For signal processing
- h5py: 用于HDF5文件支持 | For HDF5 file support

### 可选依赖 | Optional Dependencies

- nptdms: 用于支持TDMS文件格式 | For TDMS file format support
- pyabf: 用于支持ABF文件格式 | For ABF file format support

## 项目结构 | Project Structure

```
NPA3/
├── main.py                   # 程序入口点 | Program entry point
├── core/                     # 核心功能模块 | Core functionality modules
│   ├── data_processor.py     # 数据处理功能 | Data processing functionality
│   ├── data_visualizer.py    # 数据可视化组件 | Data visualization component
│   ├── load_oscilloscope_csv.py # 示波器CSV加载器 | Oscilloscope CSV loader
│   └── oscilloscope_loader.py   # 示波器数据加载功能 | Oscilloscope data loading functionality
├── gui/                      # 界面组件 | GUI components
│   ├── main_window.py        # 主窗口 | Main window
│   ├── main_window_extension.py # 主窗口扩展 | Main window extensions
│   ├── tabs.py               # 标签页组件 | Tab components
│   ├── processed_files_widget.py # 处理文件组件 | Processed files component
│   ├── styles.py             # 样式定义 | Style definitions
│   └── components/           # 其他UI组件 | Other UI components
│       ├── psd_analyzer.py   # PSD分析器 | PSD analyzer
│       ├── fitter_dialog.py  # 曲线拟合工具 | Curve fitting tool
│       └── spikes_detector.py # 峰值检测器 | Spike detector
└── utils/                    # 工具模块 | Utility modules
    ├── config_manager.py     # 配置管理 | Configuration management
    ├── notes_manager.py      # 笔记管理功能 | Notes management functionality
    └── file_system_model.py  # 文件系统模型 | File system model
```

## 使用方法 | Usage Instructions

1. **浏览数据文件夹** | **Browse Data Folder**:
   - 点击"Open Folder"按钮或使用"Browse..."浏览并选择包含数据文件的文件夹
   - Click the "Open Folder" button or use "Browse..." to browse and select a folder containing data files

2. **加载数据文件** | **Load Data File**:
   - 从文件列表中选择要分析的文件
   - Select a file to analyze from the file list

3. **数据可视化** | **Data Visualization**:
   - 查看中央面板中的图表可视化
   - 使用可视化控制面板调整采样率、选择要显示的通道等
   - View chart visualization in the central panel
   - Use the visualization control panel to adjust sampling rate, select channels to display, etc.

4. **数据处理** | **Data Processing**:
   - 在"Data Processing"标签页中选择处理操作（如滤波、基线校正等）
   - 设置处理参数并点击"Process"按钮
   - Select processing operations (like filtering, baseline correction, etc.) in the "Data Processing" tab
   - Set processing parameters and click the "Process" button

5. **保存结果** | **Save Results**:
   - 处理完成后点击"Save Results"按钮保存处理后的数据
   - 保存的文件将出现在右侧的处理文件面板中
   - After processing, click the "Save Results" button to save the processed data
   - Saved files will appear in the processed files panel on the right

6. **高级分析** | **Advanced Analysis**:
   - 使用工具栏中的"PSD Analyzer"、"Curve Fit"和"Spikes Detector"按钮访问高级分析工具
   - Use the "PSD Analyzer", "Curve Fit", and "Spikes Detector" buttons in the toolbar to access advanced analysis tools

7. **添加笔记** | **Add Notes**:
   - 在"Notes"标签页中为数据文件添加笔记和注释
   - Add notes and annotations to data files in the "Notes" tab

## 提示与技巧 | Tips and Tricks

- 使用左右侧边栏的折叠按钮（◀/▶）可以扩大可视化区域
- 在可视化控制面板中调整子图高度以便更好地查看多通道数据
- 使用"Sync X-Axis"选项可以在多通道数据中同步X轴缩放和平移

- Use the left and right sidebar collapse buttons (◀/▶) to expand the visualization area
- Adjust subplot heights in the visualization control panel for better viewing of multi-channel data
- Use the "Sync X-Axis" option to synchronize X-axis zooming and panning in multi-channel data

## 版本信息 | Version Information

当前版本：3.1

Current Version: 3.1

## 许可证 | License

[项目许可证信息 | Project License Information]
