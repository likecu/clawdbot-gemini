# Clawdbot + OpenCode 私有化部署指南

## 项目概述

本项目实现了一套基于 Docker 的私有化 AI 编程环境，包含两个核心服务：

- **Clawdbot（项目经理）**：飞书机器人，负责处理用户交互、消息分发
- **OpenCode（工程师）**：代码执行服务，集成多种 AI 模型进行智能代码生成和执行

### 技术架构演进

项目经历了从单一 Gemini 模型到多模型支持的架构演进。当前版本采用 OpenRouter 作为主要模型接入方式，支持包括 DeepSeek、Anthropic、OpenAI、Google 在内的多种 AI 模型。系统默认使用 `tngtech/deepseek-r1t2-chimera:free` 模型，这是一个基于 DeepSeek R1 的优化版本，在推理任务中表现出色，同时提供免费使用额度。

**模型支持状态**：
- **主要模型**：OpenRouter + tngtech/deepseek-r1t2-chimera:free（推荐）
- **备用模型**：Google Gemini（gemma-3-27b-it）
- **代码执行**：Docker 容器隔离执行环境

### 关于 OpenCode 服务

本项目使用的是**自定义实现的 OpenCode 服务**，它：
- 提供 OpenAI 兼容的 API 接口
- 集成 OpenRouter 和 Gemini 多种 AI 模型
- 支持 Python、JavaScript、Bash 代码的安全执行
- 通过 Bearer Token 进行 API 认证

> **注意**：还有一个官方的 OpenCode 项目（`opencode-ai/opencode`），它使用 Ollama 等本地推理引擎。如需使用官方镜像，请参考文末的"可选方案"部分。

## 系统架构

```
用户 ←→ 飞书 ←→ Clawdbot ←→ Docker 网络 ←→ OpenCode ←→ OpenRouter ←→ 多种AI模型
         :8125              :8080             :8080
```

### 服务通信

- **内部通信地址**：`http://opencode_service:8080`
- **认证方式**：Bearer Token（密码：`my_internal_secret_2024`）
- **网络模式**：Docker Bridge 网络（子网：172.28.0.0/16）
- **外部 API**：OpenRouter（https://openrouter.ai/api/v1）

### 模型选择机制

系统通过 `ACTIVE_MODEL` 环境变量控制使用的 AI 模型提供商：

| 值 | 说明 | 默认模型 |
|---|---|---|
| `openrouter` | OpenRouter 聚合平台（推荐） | tngtech/deepseek-r1t2-chimera:free |
| `gemini` | Google Gemini 官方模型 | gemma-3-27b-it |
| `opencode` | 仅使用 OpenCode 服务的代码执行 | 无 |

## 目录结构

```
clawdbot-gemini/
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # Clawdbot Dockerfile
├── Dockerfile.official         # OpenCode 官方镜像配置
├── requirements.txt            # Python 依赖
├── .env                        # 主服务环境变量
├── .env.opencode               # OpenCode 服务环境变量
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略规则
│
├── src/                        # Clawdbot 服务源代码
│   ├── __init__.py            # 包初始化
│   ├── main.py                # 主程序入口
│   ├── bot.py                 # 飞书消息处理
│   ├── client.py              # 飞书客户端
│   ├── llm.py                 # LLM 管理器（多模型支持）
│   ├── opencode.py            # OpenCode 客户端
│   ├── openrouter.py          # OpenRouter 客户端
│   ├── executor.py            # 代码执行器（备用）
│   └── utils.py               # 工具函数
│
├── opencode/                   # OpenCode 服务
│   ├── Dockerfile             # OpenCode Dockerfile
│   ├── server.js              # Node.js 服务端（多模型支持）
│   ├── package.json           # Node.js 依赖
│   ├── Dockerfile.official    # 官方镜像配置
│   └── opencode_acp.service   # systemd 服务配置
│
└── test_*.py                   # 单元测试文件
```

## 快速部署

### 1. 环境准备

确保已安装：
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### 2. 获取代码

```bash
# 克隆代码仓库
git clone https://github.com/likecu/clawdbot-gemini.git
cd clawdbot-gemini
```

### 3. 配置环境变量

#### 主服务配置（.env）

```env
# 飞书应用配置
FEISHU_APP_ID=你的飞书App ID
FEISHU_APP_SECRET=你的飞书App Secret
FEISHU_ENCRYPT_KEY=飞书Encrypt Key
FEISHU_VERIFICATION_TOKEN=飞书Verification Token

# OpenRouter 配置（推荐）
OPENROUTER_API_KEY=sk-or-v1-你的OpenRouter密钥
OPENROUTER_API_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=tngtech/deepseek-r1t2-chimera:free

# 模型选择配置
ACTIVE_MODEL=openrouter  # 可选值: openrouter/gemini/opencode

# OpenCode 服务配置
OPENCODE_API_KEY=my_internal_secret_2024
OPENCODE_API_BASE_URL=http://opencode_service:8080/v1

# 日志配置
LOG_LEVEL=INFO
```

#### OpenCode 服务配置（.env.opencode）

```env
# OpenRouter 配置（OpenCode 使用）
OPENROUTER_API_KEY=sk-or-v1-你的OpenRouter密钥
OPENROUTER_API_BASE_URL=https://openrouter.ai/api/v1

# OpenCode 服务配置
OPENCODE_HOST=0.0.0.0
OPENCODE_PORT=8080
OPENCODE_DEBUG=false
LOG_LEVEL=INFO
```

#### 敏感配置说明

以下配置包含敏感信息，**不要提交到 GitHub**：

```env
# 飞书凭证（敏感）
FEISHU_APP_ID=cli_a9fdc5b21f389bd2
FEISHU_APP_SECRET=cgEXCxziLmCgjKptyKecsJOL7q3vbtH7
FEISHU_ENCRYPT_KEY=bbaaqqqq
FEISHU_VERIFICATION_TOKEN=TGvmK7eST3pCjSc66cC8JhzJmVBV7MtF

# OpenRouter API 密钥（敏感）
OPENROUTER_API_KEY=sk-or-v1-你的OpenRouter密钥
```

### 4. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看实时日志
docker-compose logs -f
```

### 5. 验证部署

#### 检查 OpenCode 服务

```bash
# 健康检查
curl http://localhost:8080/health

# 预期响应:
# {"status":"healthy","timestamp":"2024-01-01T00:00:00","version":"1.0.0"}

# 列出可用模型
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer my_internal_secret_2024"

# 测试 OpenRouter 模型聊天
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_internal_secret_2024" \
  -d '{
    "model": "tngtech/deepseek-r1t2-chimera:free",
    "messages": [{"role": "user", "content": "你好，请介绍一下你自己"}]
  }'
```

#### 检查 Clawdbot 服务

```bash
# 查看服务日志
docker logs clawdbot_gemini --tail 100

# 预期看到类似输出：
# INFO: 正在初始化Clawdbot应用...
# INFO: 正在初始化OpenRouter客户端...
# INFO: OpenRouter客户端初始化成功
# INFO: 飞书长连接客户端初始化成功
# INFO: 所有组件初始化完成
```

## 飞书应用配置

### 1. 创建飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入"开发者后台"，创建新应用
3. 获取应用凭证：App ID、App Secret

### 2. 配置应用能力

在飞书应用管理后台启用以下能力：

#### 机器人能力
- 在"应用能力"中启用"机器人"
- 添加机器人到应用

#### 消息相关权限
- `im:message:send_as_bot` - 发送消息
- `im:message:send_to_user` - 发送消息给用户
- `im:message:send_to_group` - 发送消息到群组

#### 事件订阅
- `im.message.message_v1` - 消息事件
- 配置事件订阅 URL：`http://你的域名:8125/webhook`

### 3. 配置 Encrypt Key 和 Verification Token

在应用的后台"事件订阅"页面配置：
- **Encrypt Key**：用于消息加解密
- **Verification Token**：用于验证请求来源

### 4. 发布应用

1. 在"版本管理"中创建新版本
2. 填写版本描述
3. 选择可见范围（指定用户或全体成员）
4. 提交审核并发布

## 远程服务器部署

### 1. 服务器准备

```bash
# SSH 连接远程服务器
ssh -i ~/.ssh/milk milk@34.72.125.220

# 确保 Docker 和 Docker Compose 已安装
docker --version
docker-compose --version
```

### 2. 代码部署

#### 方式一：Git 部署（推荐）

```bash
# 在远程服务器上
cd /home/milk/clawdbot-gemini

# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose down --remove-orphans
docker-compose up -d --build
```

#### 方式二：本地推送后 pull

```bash
# 本地提交代码
git add .
git commit -m "更新：添加 OpenRouter 支持"
git push origin main

# 远程服务器拉取
cd /home/milk/clawdbot-gemini
git pull origin main

# 重启服务
docker-compose down --remove-orphans
docker-compose up -d --build
```

### 3. 敏感配置管理

`.env` 文件包含敏感信息，**直接传输到远程服务器**：

```bash
# 本地传输 .env 文件到远程服务器
scp -i ~/.ssh/milk .env milk@34.72.125.220:/home/milk/clawdbot-gemini/.env

# 远程服务器传输 OpenCode 环境变量
scp -i ~/.ssh/milk .env.opencode milk@34.72.125.220:/home/milk/clawdbot-gemini/.env.opencode

### 3.1 Host 组件部署 (Clawdbot CLI & Wrapper)
本项目包含运行在 Host 主机上的非 Docker 组件（Clawdbot CLI 和 HTTP Wrapper），由 PM2 管理。
`deploy.sh` 脚本已包含自动更新这些组件的逻辑：

1.  **自动同步配置**：将本地 `../clawdbot.json` 同步到远程 `~/.clawdbot/clawdbot.json`。
2.  **自动更新 Wrapper**：将本地 `../clawdbot_http_wrapper.js` 同步到远程 `~/clawd/clawdbot_http_wrapper.js`。
3.  **自动重启服务**：通过 PM2 重启 `clawdbot-wrapper` 服务。

**注意**：如果不希望更新 Host 组件，运行时可添加 `--docker-only` 参数。
```

### 4. Docker 部署命令

```bash
# 完整部署流程
cd /home/milk/clawdbot-gemini

# 1. 传输配置文件
scp -i ~/.ssh/milk .env .env.opencode milk@34.72.125.220:/home/milk/clawdbot-gemini/

# 2. 停止现有服务
ssh -i ~/.ssh/milk milk@34.72.125.220 "cd /home/milk/clawdbot-gemini && docker-compose down --remove-orphans"

# 3. 拉取最新代码
ssh -i ~/.ssh/milk milk@34.72.125.220 "cd /home/milk/clawdbot-gemini && git pull origin main"

# 4. 构建并启动
ssh -i ~/.ssh/milk milk@34.72.125.220 "cd /home/milk/clawdbot-gemini && docker-compose up -d --build"

# 5. 验证服务
ssh -i ~/.ssh/milk milk@34.72.125.220 "curl http://localhost:8080/health"
```

## 测试

### 单元测试

```bash
# 安装测试依赖
pip3 install pytest pytest-cov

# 运行所有测试
python3 -m pytest test_*.py -v

# 运行覆盖率报告
python3 -m pytest test_*.py --cov=src --cov-report=html
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

test_openrouter.py: 5/5 测试通过
✓ OpenRouter 客户端初始化
✓ 聊天完成测试
✓ 速率限制测试
✓ 错误处理测试
✓ 对话历史测试
```

### 集成测试

```bash
# 测试 OpenCode 服务 API
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_internal_secret_2024" \
  -d '{
    "model": "tngtech/deepseek-r1t2-chimera:free",
    "messages": [{"role": "user", "content": "用 Python 写一个快速排序"}],
    "temperature": 0.7
  }'

# 测试代码执行
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_internal_secret_2024" \
  -d '{
    "model": "tngtech/deepseek-r1t2-chimera:free",
    "messages": [{"role": "user", "content": "执行这段 Python 代码：print(\"Hello World\")"}]
  }'
```

## 常用操作

### 查看服务日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看 OpenCode 服务日志
docker logs clawdbot_opencode

# 查看 Clawdbot 服务日志
docker logs clawdbot_gemini

# 实时查看日志
docker-compose logs -f

# 查看特定服务的实时日志
docker logs -f clawdbot_gemini
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

# 停止并删除所有（包括网络）
docker-compose down --volumes --remove-orphans
```

### 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

### 清理资源

```bash
# 删除未使用的镜像
docker image prune -a

# 删除未使用的容器
docker container prune

# 删除未使用的卷
docker volume prune

# 完全清理（删除所有未使用的镜像、容器、卷、网络）
docker system prune -a --volumes
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

# 检查 Docker 日志
docker-compose logs opencode_service
```

### 2. Clawdbot 无法连接 OpenCode

```bash
# 检查网络连接
docker exec clawdbot_gemini ping opencode_service

# 检查环境变量
docker exec clawdbot_gemini env | grep OPENCODE

# 检查容器是否在同一网络
docker network inspect clawdbot-gemini_clawdbot_network

# 查看 Clawdbot 日志中的连接错误
docker logs clawdbot_gemini | grep -i opencode
```

### 3. OpenRouter API 调用失败

```bash
# 检查 API 密钥配置
docker exec clawdbot_gemini python3 -c "import os; print(os.getenv('OPENROUTER_API_KEY')[:20] + '...')"

# 测试 API 连通性（本地测试）
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <你的OPENROUTER_API_KEY>" \
  -d '{"model": "tngtech/deepseek-r1t2-chimera:free", "messages": [{"role": "user", "content": "test"}]}'

# 检查 OpenCode 服务中的模型路由
docker exec clawdbot_opencode cat /app/logs/error.log
```

### 4. 飞书消息接收失败

```bash
# 检查飞书配置
docker exec clawdbot_gemini python3 -c "import os; print('APP_ID:', os.getenv('FEISHU_APP_ID'))"

# 检查 Webhook 端点
curl http://localhost:8125/health

# 查看飞书 SDK 日志
docker logs clawdbot_gemini | grep -i lark
```

### 5. 代码执行超时

默认代码执行超时为 30 秒。查看 `opencode/server.js` 中的 `EXECUTION_TIMEOUT` 配置：

```javascript
// 在 server.js 中
const EXECUTION_TIMEOUT = 30000; // 30 秒
```

如需调整，修改后重新构建：

```bash
# 修改后重新构建
docker-compose build opencode_service
docker-compose up -d opencode_service
```

### 6. 内存不足

```bash
# 检查容器资源使用
docker stats

# 增加 Docker 内存限制（编辑 docker-compose.yml）
# services:
#   opencode_service:
#     deploy:
#       resources:
#         limits:
#           memory: 2G
```

## 安全建议

### 1. API 密钥管理

- 使用强密码作为 `OPENCODE_API_KEY`
- 定期轮换 OpenRouter API 密钥
- 不要在代码中硬编码密钥
- `.env` 文件不提交到版本控制

### 2. 网络隔离

- OpenCode 服务仅在 Docker 网络内部暴露（端口 8080）
- 生产环境添加 SSL/TLS
- 使用防火墙限制外部访问
- OpenCode 服务不对公网直接暴露

### 3. 访问控制

- 飞书机器人验证请求来源
- 实施消息频率限制
- 添加请求日志审计

### 4. 容器安全

- 使用非 root 用户运行容器
- 限制容器资源使用
- 定期更新基础镜像
- 启用 Docker 安全选项

## 监控和日志

### 日志位置

- **Clawdbot 日志**：`./logs/clawdbot.log`
- **OpenCode 日志**：`./opencode_logs/`
- **Docker 日志**：`docker logs clawdbot_gemini`

### 日志级别配置

```env
# .env 文件
LOG_LEVEL=INFO  # DEBUG/INFO/WARNING/ERROR
```

### 监控指标

- 服务健康状态（`/health` 端点）
- API 调用成功率（HTTP 状态码）
- 代码执行成功率
- 响应时间（P95/P99）
- OpenRouter API 调用延迟

### 日志分析

```bash
# 查看错误日志
docker logs clawdbot_gemini 2>&1 | grep -i error

# 查看 OpenRouter API 调用日志
grep -r "openrouter" logs/

# 统计 API 调用次数
grep -c "chat/completions" opencode_logs/access.log
```

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

**注意**：官方镜像需要配合 Ollama 或其他兼容的 LLM 服务使用，不直接支持 OpenRouter API。

## 扩展功能

### 添加新的代码执行语言

1. 在 `opencode/server.js` 中添加语言检测逻辑
2. 实现对应的执行方法（使用 child_process.spawn）
3. 添加安全检查（禁止危险命令）
4. 添加单元测试

### 集成其他模型

1. 在 `src/llm.py` 中添加新的 `ModelProvider` 枚举值
2. 实现对应的初始化和调用方法
3. 更新配置说明文档
4. 添加对应的测试用例

### 自定义消息格式

修改 `src/bot.py` 中的消息格式化逻辑：

```python
# 支持的消息类型
MSG_TYPE_TEXT = "text"           # 纯文本
MSG_TYPE_RICH_TEXT = "rich_text" # 富文本
MSG_TYPE_INTERACTIVE = "card"    # 卡片消息
```

## 常见问题 FAQ

**Q: 如何切换不同的 AI 模型？**
A: 修改 `ACTIVE_MODEL` 环境变量或在请求时指定模型名称。

**Q: OpenRouter API 免费额度用完怎么办？**
A: 可以切换到 `gemini` 模式使用 Google Gemini，或申请新的 OpenRouter API 密钥。

**Q: 如何添加自定义系统提示词？**
A: 在 `src/openrouter.py` 中修改 `system_prompt` 变量。

**Q: 代码执行失败怎么办？**
A: 检查 `opencode/server.js` 中的错误日志，确认代码语法正确且不包含危险操作。

**Q: 如何查看详细的调试信息？**
A: 将 `LOG_LEVEL` 设置为 `DEBUG`，重启服务后查看日志。

## 许可证

MIT License
