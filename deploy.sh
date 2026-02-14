#!/bin/bash

# 配置
REMOTE_USER="milk"
REMOTE_HOST="34.72.125.220"
REMOTE_PATH="/home/milk/clawdbot-gemini"
SSH_KEY="~/.ssh/milk" # 确保本地有这个私钥

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}>>> 开始部署到远程服务器: ${REMOTE_HOST}${NC}"

# 1. 同步环境变量 (可选)
if [[ "$*" == *"--env"* ]]; then
    echo -e "${GREEN}>>> 正在同步 .env 文件...${NC}"
    scp -i ${SSH_KEY} .env .env.opencode ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/
fi

# 2. 远程更新代码并重启容器
echo -e "${GREEN}>>> 正在远程操作...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} 'bash -s' << 'EOF'
    set -e # 遇到错误立即停止
    
    # 颜色定义 (远程)
    GREEN='\033[0;32m'
    NC='\033[0m'

    cd /home/milk/clawdbot-gemini || exit 1

    echo -e "${GREEN}>>> 1. 拉取最新代码...${NC}"
    git pull origin main

    echo -e "${GREEN}>>> 2. 清理旧的/冲突容器...${NC}"
    # 停止并删除错误的容器 (如果存在)
    if docker ps -a --format '{{.Names}}' | grep -q "^clawd-ai-tavern-1$"; then
        echo "Stopping and removing clawd-ai-tavern-1..."
        docker stop clawd-ai-tavern-1 || true
        docker rm clawd-ai-tavern-1 || true
    fi

    echo -e "${GREEN}>>> 3. 启动 NapCat (QQ 适配器)...${NC}"
    # 确保 napcat 正在运行，并且网络已创建
    docker compose -f napcat_compose.yml up -d

    echo -e "${GREEN}>>> 4. 启动 ClawdBots 服务...${NC}"
    # 重新构建并启动主服务
    docker compose up -d --build --remove-orphans

    echo -e "${GREEN}>>> 5. 清理没用的镜像...${NC}"
    docker image prune -f
EOF

# 3. 验证
echo -e "${GREEN}>>> 部署完成，正在检查服务状态...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

echo -e "${GREEN}>>> 部署流程执行完毕!${NC}"
