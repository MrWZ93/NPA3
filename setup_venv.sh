#!/bin/bash
# 创建虚拟环境设置脚本

# 设置脚本停止条件（任何命令失败则退出）
set -e

echo "开始创建NPA项目的Python虚拟环境..."

# 创建venv目录
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖包
echo "安装必要的依赖包..."
pip install --upgrade pip
pip install numpy pandas matplotlib scipy h5py PyQt6

# 尝试安装可选依赖
echo "尝试安装可选依赖..."
pip install nptdms || echo "nptdms安装失败，TDMS支持将不可用"
pip install pyabf || echo "pyabf安装失败，ABF支持将不可用"

echo "创建requirements.txt文件..."
pip freeze > requirements.txt

echo "虚拟环境创建完成！"
echo "使用以下命令激活虚拟环境:"
echo "  source venv/bin/activate"

# 生成激活说明文件
echo "为了方便使用，还创建了activate.sh脚本"
