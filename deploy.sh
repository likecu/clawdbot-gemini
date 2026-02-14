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

# 2. 定位 SOUL.md 本地路径
SOUL_MD_LOCAL=""
if [ -f "../SOUL.md" ]; then
    SOUL_MD_LOCAL="../SOUL.md"
elif [ -f "SOUL.md" ]; then
    SOUL_MD_LOCAL="SOUL.md"
fi

# 3. 远程更新代码
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

    echo -e "${GREEN}>>> 3. 确保 NapCat 容器存在...${NC}"
    docker-compose -f napcat_compose.yml up -d

    echo -e "${GREEN}>>> 4. 更新 NapCat 配置 (docker exec)...${NC}"
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
    docker cp /tmp/napcat_onebot11.json napcatqq:/app/napcat/config/onebot11_2745708378.json
    docker cp /tmp/napcat_onebot11.json napcatqq:/app/napcat/config/onebot11.json
    rm /tmp/napcat_onebot11.json

    # 清理 SOUL.md 目录冲突 (Docker 可能自动创建了目录)
    echo -e "${GREEN}>>> 5. 清理 SOUL.md 目录冲突...${NC}"
    if [ -d "SOUL.md" ]; then
        echo "检测到 SOUL.md 是目录，正在删除..."
        rm -rf SOUL.md
    fi
EOF

# 4. 上传 SOUL.md（必须在 docker-compose up 之前，否则 Docker 会将其创建为目录）
if [ -n "$SOUL_MD_LOCAL" ]; then
    echo -e "${GREEN}>>> 正在同步 SOUL.md (docker-compose up 之前)...${NC}"
    scp -i ${SSH_KEY} "$SOUL_MD_LOCAL" ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/SOUL.md
else
    echo -e "${RED}>>> ⚠️ 未找到 SOUL.md，跳过人格设定同步${NC}"
fi

# 5. 启动服务和后续清理（新的远程 SSH 块）
echo -e "${GREEN}>>> 正在启动服务...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} 'bash -s' << 'EOF'
    set -e
    GREEN='\033[0;32m'
    NC='\033[0m'
    cd /home/milk/clawdbot-gemini || exit 1

    echo -e "${GREEN}>>> 6. 重建并启动 ClawdBots 服务...${NC}"
    # 先删旧容器，清除可能缓存的错误 mount 信息
    docker-compose rm -sf clawdbot || true
    docker-compose up -d --build

    echo -e "${GREEN}>>> 7. 同步 Host 端 Wrapper (Git 优先)...${NC}"
    if [ -f "deployment/clawdbot_http_wrapper.js" ]; then
        echo "Syncing clawdbot_http_wrapper.js from repo..."
        cp deployment/clawdbot_http_wrapper.js /home/milk/clawd/clawdbot_http_wrapper.js
        
        echo "Restarting clawdbot-wrapper via PM2..."
        /home/milk/.npm-global/bin/pm2 restart clawdbot-wrapper || echo "PM2 restart failed, is it running?"
    fi

    echo -e "${GREEN}>>> 8. 清理没用的镜像...${NC}"
    docker image prune -f
EOF


# 5. 同步敏感配置 (非 Git)
if [[ "$*" != *"--docker-only"* ]]; then
    echo -e "${GREEN}>>> 正在同步敏感配置 (非 Git)...${NC}"
    
    if [ -f "../clawdbot.json" ]; then
        echo "Uploading clawdbot.json via scp..."
        scp -i ${SSH_KEY} ../clawdbot.json ${REMOTE_USER}@${REMOTE_HOST}:/home/${REMOTE_USER}/.clawdbot/clawdbot.json
    fi
fi

# 6. 验证
echo -e "${GREEN}>>> 部署完成，正在检查服务状态...${NC}"
ssh -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

echo -e "${GREEN}>>> 部署流程执行完毕!${NC}"
