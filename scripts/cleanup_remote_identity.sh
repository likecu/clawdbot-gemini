#!/bin/bash
# 远程身份清理脚本
# 用于解决 "韩总" 身份混淆问题

# 设置远程服务器连接信息
REMOTE_HOST="milk@34.72.125.220"
REMOTE_KEY="~/.ssh/milk"
REMOTE_DIR="/home/milk/clawdbot-gemini"

echo "Using key: $REMOTE_KEY"

echo "=== 开始清理远程身份数据 ==="

# 1. 删除 memories 目录下的所有 log_*.md 文件
# 这些文件包含了详细的对话历史，可能含有 "韩总" 的错误称呼
echo "正在删除记忆日志文件..."
ssh -i "$REMOTE_KEY" "$REMOTE_HOST" "find $REMOTE_DIR/memories -name 'log_*.md' -type f -delete"
if [ $? -eq 0 ]; then
    echo "✅ 已删除 log_*.md 文件"
else
    echo "❌ 删除日志文件失败"
fi

# 2. 清理 opencode_data 卷中的数据
# 这里存放了生成的代码文件，如 novel.py
# 注意：这会删除所有生成的代码
echo "正在清理 opencode 数据..."
# 我们通过 docker volume 查找并清理，或者直接 exec 进容器清理
# 假设容器名为 clawdbot-gemini-opencode-1 或类似，我们可以通过 label 或 image 查找
ssh -i "$REMOTE_KEY" "$REMOTE_HOST" "docker run --rm -v clawdbot-gemini_opencode_data:/data alpine sh -c 'rm -rf /data/*'"

if [ $? -eq 0 ]; then
    echo "✅ 已清理 opencode_data 卷"
else
    echo "⚠️  清理卷失败 (可能卷名不匹配，请手动检查)"
fi

echo "=== 清理完成 ==="
echo "请记得重新部署并重建容器: docker-compose up -d --build"
