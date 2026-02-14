#!/bin/bash

# Clawdbot 自动化部署脚本
# 功能：代码同步、配置更新、Docker 容器重启

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

# 1. 同步环境变量 (强制)
echo -e "${GREEN}>>> 正在同步环境变量...${NC}"
if [ -f ".env" ]; then
    scp -i ${SSH_KEY} .env ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/.env
else
    echo -e "${GREEN}>>> 本地 .env 不存在，使用 .env.opencode 作为远程 .env...${NC}"
    scp -i ${SSH_KEY} .env.opencode ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/.env
fi
# 总是同步 .env.opencode，因为它也被 docker-compose 引用
scp -i ${SSH_KEY} .env.opencode ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/.env.opencode

# 2. 远程更新代码并重启容器
echo -e "${GREEN}>>> 正在远程操作...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} 'bash -s' << 'EOF'
    set -e # 遇到错误立即停止
    
    # 颜色定义 (远程)
    GREEN='\033[0;32m'
    NC='\033[0m'

    cd /home/milk/clawdbot-gemini || exit 1

    echo -e "${GREEN}>>> 1. 强制同步代码 (清理冲突)...${NC}"
    git fetch origin main
    git reset --hard origin/main
    git clean -fd || true

    echo -e "${GREEN}>>> 2. 清理旧的/冲突容器...${NC}"
    # 停止并删除错误的容器 (如果存在)
    if docker ps -a --format '{{.Names}}' | grep -q "^clawd-ai-tavern-1$"; then
        echo "Stopping and removing clawd-ai-tavern-1..."
        docker stop clawd-ai-tavern-1 || true
        docker rm clawd-ai-tavern-1 || true
    fi

    echo -e "${GREEN}>>> 3.1 确保 NapCat 容器存在...${NC}"
    # 先启动一次以确保容器存在
    docker-compose -f napcat_compose.yml up -d

    echo -e "${GREEN}>>> 3.2 更新 NapCat 配置 (docker exec)...${NC}"
    # 写入配置到临时文件，然后移动到容器内
    cat > /tmp/napcat_onebot11.json << 'JSON'
{
  "http": {
    "enable": false,
    "host": "0.0.0.0",
    "port": 3000,
    "access_token": "",
    "secret": "",
    "enableHeart": false,
    "enablePost": false,
    "postUrls": []
  },
  "ws": {
    "enable": false,
    "host": "0.0.0.0",
    "port": 8080,
    "access_token": ""
  },
  "network": {
    "httpServers": [
        {
            "name": "http",
            "enable": true,
            "host": "0.0.0.0",
            "port": 3000,
            "accessToken": "",
            "enableMsg": true,
            "enableEvent": true
        }
    ],
    "httpSseServers": [],
    "httpClients": [],
    "websocketServers": [
        {
            "name": "ws",
            "enable": true,
            "host": "0.0.0.0",
            "port": 8080,
            "accessToken": "",
            "enableMsg": true,
            "enableEvent": true
        }
    ],
    "websocketClients": [],
    "plugins": []
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": false,
  "parseMultMsg": false
}
JSON
    # 使用 docker exec 写入配置 (root 权限)
    docker cp /tmp/napcat_onebot11.json napcatqq:/app/napcat/config/onebot11_2745708378.json
    docker cp /tmp/napcat_onebot11.json napcatqq:/app/napcat/config/onebot11.json
    rm /tmp/napcat_onebot11.json
    
    # 重启 napcat 以应用配置
    docker restart napcatqq || true

    echo -e "${GREEN}>>> 4. 启动 ClawdBots 服务...${NC}"
    # 重新构建并启动主服务
    docker-compose up -d --build

    echo -e "${GREEN}>>> 5. 同步 Host 端 Wrapper (Git 优先)...${NC}"
    # 从仓库的 deployment 目录同步到运行目录
    if [ -f "deployment/clawdbot_http_wrapper.js" ]; then
        echo "Syncing clawdbot_http_wrapper.js from repo..."
        cp deployment/clawdbot_http_wrapper.js /home/milk/clawd/clawdbot_http_wrapper.js
        
        echo "Restarting clawdbot-wrapper via PM2..."
        /home/milk/.npm-global/bin/pm2 restart clawdbot-wrapper || echo "PM2 restart failed, is it running?"
    fi

    echo -e "${GREEN}>>> 7. 清理没用的镜像...${NC}"
    docker image prune -f
EOF

# 2.1 更新 Host 上的 Clawdbot 配置 (保持 scp 用于敏感配置，或根据用户需求调整)
# 注意：clawdbot.json 包含敏感 Key，暂不放入 Git，维持现状或通过其他安全方式
if [[ "$*" != *"--docker-only"* ]]; then
    echo -e "${GREEN}>>> 正在同步敏感配置 (非 Git)...${NC}"
    
    # 确保本地文件存在
    if [ -f "../clawdbot.json" ]; then
        echo "Uploading clawdbot.json via scp..."
        scp -i ${SSH_KEY} ../clawdbot.json ${REMOTE_USER}@${REMOTE_HOST}:/home/${REMOTE_USER}/.clawdbot/clawdbot.json
    fi
fi

# 3. 验证
echo -e "${GREEN}>>> 部署完成，正在检查服务状态...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

echo -e "${GREEN}>>> 部署流程执行完毕!${NC}"
