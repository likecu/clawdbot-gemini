# Gemini API Keys
# 推荐配置方式：
# 1. 在项目根目录 .env 文件中设置 GEMINI_API_KEY=xxx
# 2. docker-compose.yml 会自动将其注入到所有服务（clawdbot 和 opencode）
GEMINI_API_KEYS = [
    # 也可以在此处硬编码备用 Key，但首选环境变量
]
