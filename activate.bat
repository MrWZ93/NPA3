@echo off
REM 激活虚拟环境的辅助脚本

REM 检查虚拟环境是否存在
if not exist venv (
    echo 错误：未找到虚拟环境，请先运行 setup_venv.bat 创建虚拟环境
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

echo 已激活NPA虚拟环境
echo 可以通过输入'deactivate'命令来退出虚拟环境
echo 现在可以运行'python main.py'来启动应用
