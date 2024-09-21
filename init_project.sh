#!/bin/bash

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]
  then echo "请以root权限运行此脚本"
  exit
fi

# 更新包列表
echo "正在更新包列表..."
apt-get update

# 1. 安装ffmpeg
echo "正在安装ffmpeg..."
apt-get install -y ffmpeg

# 2. 安装Python依赖
echo "正在安装Python依赖..."
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "未找到requirements.txt文件，跳过此步骤"
fi

# 3. 下载并安装pget
echo "正在下载并安装pget..."
curl -o /usr/local/bin/pget -L "https://github.com/replicate/pget/releases/download/v0.8.1/pget_linux_x86_64" && chmod +x /usr/local/bin/pget

echo "初始化完成！"
