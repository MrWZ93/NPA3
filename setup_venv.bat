@echo off
echo 开始创建NPA项目的Python虚拟环境...

REM 创建venv目录
python -m venv venv

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖包
echo 安装必要的依赖包...
pip install --upgrade pip
pip install numpy pandas matplotlib scipy h5py PyQt6

REM 尝试安装可选依赖
echo 尝试安装可选依赖...
pip install nptdms || echo nptdms安装失败，TDMS支持将不可用
pip install pyabf || echo pyabf安装失败，ABF支持将不可用

echo 创建requirements.txt文件...
pip freeze > requirements.txt

echo 虚拟环境创建完成！
echo 使用activate.bat激活虚拟环境
