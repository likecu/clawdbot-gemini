#!/bin/bash

# 远程部署脚本
# 功能：连接远程服务器，拉取最新代码并重启 Docker 容器

REMOTE_USER="milk"
REMOTE_HOST="34.72.125.220"
SSH_KEY="$HOME/.ssh/milk"
REMOTE_PATH="/home/milk/clawdbot-gemini"

# 确保脚本在其所在目录运行
cd "$(dirname "$0")"
set -e

echo "🚀 开始远程部署流程..."

# 执行远程命令
ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST << EOF
    echo "📂 进入项目目录: $REMOTE_PATH"
    cd $REMOTE_PATH || { echo "❌ 目录不存在"; exit 1; }

    echo "📥 强制同步代码 (清理冲突)..."
    git fetch origin main
    git reset --hard origin/main
    git clean -fd || true

    echo "🔄 重启 Docker 容器..."
    # 使用 sudo 如果需要权限，或者确保用户在 docker 组
    docker-compose down
    docker-compose up -d --build

    echo "📋 检查容器状态..."
    docker ps
    
    echo "✅ 部署完成！"
EOF

if [ $? -eq 0 ]; then
    echo "✨ 远程部署脚本执行完毕。"
else
    echo "💥 部署过程中出现错误。"
    exit 1
fi
