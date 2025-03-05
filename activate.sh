#!/bin/bash
# 激活虚拟环境的辅助脚本

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "错误：未找到虚拟环境，请先运行 setup_venv.sh 创建虚拟环境"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

echo "已激活NPA虚拟环境"
echo "可以通过输入'deactivate'命令来退出虚拟环境"
echo "现在可以运行'python main.py'来启动应用"
