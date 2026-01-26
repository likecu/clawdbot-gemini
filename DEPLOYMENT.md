# Clawdbot + OpenCode 私有化部署指南

## 项目概述

本项目实现了一套基于 Docker 的私有化 AI 编程环境，包含两个核心服务：

- **Clawdbot（项目经理）**：飞书机器人，负责处理用户交互、消息分发
- **OpenCode（工程师）**：代码执行服务，集成 Google Gemini 模型进行智能代码生成和执行

### 关于 OpenCode 服务

本项目使用的是**自定义实现的 OpenCode 服务**，它：
- 提供 OpenAI 兼容的 API 接口
- 集成 Google Gemini 模型（gemma-3-27b-it）
- 支持 Python、JavaScript、Bash 代码的安全执行
- 通过 Bearer Token 进行 API 认证

> **注意**：还有一个官方的 OpenCode 项目（`opencode-ai/opencode`），它使用 Ollama 等本地推理引擎。如需使用官方镜像，请参考文末的"可选方案"部分。

## 系统架构

```
用户 ←→ 飞书 ←→ Clawdbot ←→ Docker 网络 ←→ OpenCode ←→ Gemini API
         :8125              :8080
```

### 服务通信

- **内部通信地址**：`http://opencode_service:8080`
- **认证方式**：Bearer Token（密码：`my_internal_secret_2024`）
- **网络模式**：Docker Bridge 网络（子网：172.28.0.0/16）

## 目录结构

```
clawdbot-gemini/
├── docker-compose.yml          # Docker Compose 配置
├── .env                        # 主服务环境变量
├── .env.opencode               # OpenCode 服务环境变量
├── .env.example                # 环境变量模板
├── Dockerfile                  # Clawdbot Dockerfile
├── requirements.txt            # Python 依赖
├── opencode/
│   ├── Dockerfile              # OpenCode Dockerfile
│   ├── opencode_requirements.txt
│   ├── opencode_server.py      # OpenCode 服务主程序
│   └── src/
│       ├── executor.py         # 代码执行器
│       └── llm.py              # Gemini 集成
├── src/
│   ├── bot.py                  # 飞书消息处理
│   ├── client.py               # 飞书客户端
│   ├── llm.py                  # Gemini 集成
│   ├── main.py                 # 主程序入口
│   ├── opencode.py             # OpenCode 客户端
│   └── utils.py                # 工具函数
└── test_*.py                   # 单元测试
```

## 快速部署

### 1. 环境准备

确保已安装：
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### 2. 配置环境变量

```bash
# 复制模板文件
cp .env.example .env
cp .env.example .env.opencode

# 注意：.env.opencode 需要单独配置，不要直接覆盖
# 保留 .env.opencode 中的 OPENCODE_API_KEY 设置
```

#### 主服务配置 (.env)

```env
# Feishu 应用配置
FEISHU_APP_ID=你的飞书App ID
FEISHU_APP_SECRET=你的飞书App Secret
FEISHU_ENCRYPT_KEY=飞书Encrypt Key
FEISHU_VERIFICATION_TOKEN=飞书Verification Token

# Gemini 配置
GOOGLE_API_KEY=你的Google API Key

# OpenCode 配置
OPENCODE_API_BASE_URL=http://opencode_service:8080/v1
OPENCODE_API_KEY=my_internal_secret_2024

# 日志级别
LOG_LEVEL=INFO
```

#### OpenCode 服务配置 (.env.opencode)

```env
# Gemini 配置（OpenCode 使用）
GOOGLE_API_KEY=你的Google API Key

# OpenCode 服务配置
OPENCODE_API_KEY=my_internal_secret_2024
OPENCODE_HOST=0.0.0.0
OPENCODE_PORT=8080
OPENCODE_DEBUG=false

# 日志配置
LOG_LEVEL=INFO
```

### 3. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4. 验证部署

#### 检查 OpenCode 服务

```bash
# 健康检查
curl http://localhost:8080/health
# 预期响应:
# {"status":"healthy","timestamp":"2024-01-01T00:00:00","version":"1.0.0"}

# 列出可用模型
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer my_internal_secret_2024"

# 测试聊天接口
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_internal_secret_2024" \
  -d '{
    "model": "opencode-1.0",
    "messages": [{"role": "user", "content": "你好，请介绍一下你自己"}]
  }'
```

#### 检查 Clawdbot 服务

```bash
# 查看服务日志
docker logs clawdbot_gemini --tail 100
```

## 测试

### 单元测试

```bash
# 安装测试依赖
pip3 install pytest pytest-cov

# 运行所有测试
python3 -m pytest test_opencode_client.py -v

# 运行覆盖率报告
python3 -m pytest test_opencode_client.py --cov=src --cov-report=html
```

### 测试结果

```
test_opencode_client.py: 8/8 测试通过
✓ 初始化测试
✓ 聊天功能测试
✓ 自定义参数测试
✓ 重试机制测试
✓ 健康检查测试
✓ 代码执行测试
```

## 常用操作

### 查看服务日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看 OpenCode 服务日志
docker logs clawdbot_opencode

# 实时查看日志
docker-compose logs -f
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启单个服务
docker-compose restart clawdbot
docker-compose restart opencode_service
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

### 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

## 故障排除

### 1. OpenCode 服务无法启动

```bash
# 检查端口占用
lsof -i :8080

# 查看详细错误
docker logs clawdbot_opencode

# 检查容器状态
docker ps -a | grep opencode
```

### 2. Clawdbot 无法连接 OpenCode

```bash
# 检查网络连接
docker exec clawdbot_gemini ping opencode_service

# 检查环境变量
docker exec clawdbot_gemini env | grep OPENCODE

# 检查容器是否在同一网络
docker network inspect clawdbot-gemini_clawdbot_network
```

### 3. Gemini API 调用失败

```bash
# 检查 API 密钥
docker exec clawdbot_gemini python3 -c "import os; print(os.getenv('GOOGLE_API_KEY'))"

# 测试 API 连通性
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(docker exec clawdbot_gemini python3 -c 'import os; print(os.getenv("GOOGLE_API_KEY"))')" \
  -d '{"contents": [{"parts": [{"text": "你好"}]}]}'
```

### 4. 代码执行超时

默认代码执行超时为 30 秒。如需调整，修改 `opencode/src/executor.py` 中的超时设置。

## 安全建议

1. **API 密钥管理**
   - 使用强密码作为 `OPENCODE_API_KEY`
   - 定期轮换密钥
   - 不要在代码中硬编码密钥

2. **网络隔离**
   - OpenCode 服务仅在 Docker 网络内部暴露（端口 8080）
   - 生产环境可考虑添加 SSL/TLS
   - 使用防火墙限制外部访问

3. **访问控制**
   - 飞书机器人验证请求来源
   - 实施消息频率限制

## 监控和日志

### 日志位置

- **Clawdbot 日志**：`./logs/clawdbot.log`
- **OpenCode 日志**：`./opencode_logs/`

### 监控指标

- 服务健康状态
- API 调用成功率
- 代码执行成功率
- 响应时间

## 可选方案：使用官方 OpenCode 镜像

如果您想使用官方的 OpenCode Docker 镜像（`opencode-ai/opencode`），可以替换 `docker-compose.yml` 中的服务配置：

```yaml
services:
  opencode_service:
    image: opencode-ai/opencode:latest
    container_name: clawdbot_opencode
    restart: always
    ports:
      - "8080:8080"
    volumes:
      - opencode_data:/home/op/.opencode
    command: ["serve", "--host", "0.0.0.0", "--port", "8080"]
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434  # 需要 Ollama 服务
      - OPENCODE_API_KEY=${OPENCODE_API_KEY}
```

**注意**：官方镜像需要配合 Ollama 或其他兼容的 LLM 服务使用，不直接支持 Gemini API。

## 扩展功能

### 添加新的代码执行语言

1. 在 `opencode/src/executor.py` 中添加语言检测逻辑
2. 实现对应的执行方法
3. 添加单元测试

### 集成其他 LLM

1. 在 `opencode/src/llm.py` 中添加新的模型集成
2. 更新配置说明
3. 添加对应的测试用例

## 许可证

MIT License
