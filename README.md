# Clawdbot-Gemini 项目文档

## 项目概述

本项目是一套基于 Docker 的私有化 AI 编程环境，实现了飞书机器人与 AI 代码执行服务的深度集成。该系统采用双服务架构设计，将项目管理职能与代码执行职能分离，通过 Docker 容器化技术实现服务的独立部署与灵活扩展。项目核心价值在于为团队提供一个安全、可控的 AI 编程助手平台，所有服务均部署在私有环境中，确保数据安全性的同时充分利用 Google Gemini 模型的强大能力。

项目采用分层架构设计，将用户交互层、业务逻辑层和服务执行层清晰分离。这种设计不仅提升了系统的可维护性，还为后续功能扩展预留了充足的空间。Clawdbot 作为项目经理角色，负责处理用户交互、消息分发和任务协调；OpenCode 作为工程师角色，负责代码生成、AI 意图分析以及安全代码执行。两者通过 Docker 网络进行内部通信，形成一个完整的 AI 编程助手生态系统。

系统的核心设计理念是将复杂的人工智能能力封装为易用的 API 接口，使非技术背景的用户也能通过飞书这样熟悉的通讯工具来调用强大的 AI 编程能力。通过 Bearer Token 认证机制和飞书应用加密验证，系统在提供便利性的同时保障了访问安全。所有配置均通过环境变量管理，支持在不同部署环境中快速切换，无需修改代码即可适应新的运行场景。

## 系统架构

### 整体架构设计

系统采用双服务微服务架构，通过 Docker Compose 进行统一编排管理。这种架构设计将不同职责的服务解耦，使得每个服务可以独立开发、测试和部署，同时通过 Docker 网络实现安全高效的内部通信。整体架构分为五个层次：用户接入层、飞书平台层、业务服务层、代码执行层和外部依赖层，每一层都有明确的职责边界和交互协议。

用户通过飞书应用向系统发送消息，消息首先经过飞书开放平台的安全验证，包括签名验证和加密解密处理。验证通过后，消息通过 Webhook 方式推送到 Clawdbot 服务。Clawdbot 作为系统的统一入口，负责消息的接收、解析和路由转发，它会根据消息内容判断是需要简单的 AI 对话还是需要执行代码任务，然后相应地调用 Gemini 模型或 OpenCode 服务。

对于需要执行代码的请求，Clawdbot 会将请求转发给 OpenCode 服务。OpenCode 负责与 Gemini 模型交互，生成符合要求的代码，并使用安全的代码执行环境来运行代码。执行结果会被格式化后返回给 Clawdbot，最终通过飞书平台呈现给用户。整个流程的设计充分考虑了异常处理和错误恢复，确保系统在各种边界条件下都能提供稳定的服务。

### 服务通信架构

系统使用 Docker Bridge 网络模式，子网地址为 172.28.0.0/16。Clawdbot 服务通过服务名 `opencode_service` 在 Docker 内部网络中访问 OpenCode 服务，通信地址为 `http://opencode_service:8080/v1`。这种设计避免了使用 localhost 或 IP 地址带来的网络配置问题，同时提供了服务发现和负载均衡的基础能力。

两个服务之间的通信采用 HTTP RESTful API 风格，OpenCode 服务提供 OpenAI 兼容的 API 接口。请求认证使用 Bearer Token 方式，内部通信密钥配置为 `my_internal_secret_2024`。为了保障服务的高可用性，Docker Compose 配置中为 OpenCode 服务添加了健康检查机制，通过定期探测 `/health` 端点来监控服务状态，只有健康的服务才会接收业务请求。

## 技术栈

### 后端服务技术选型

系统后端采用 Python 3.10 作为主要开发语言，选择 slim 基础镜像以减小容器体积。Python 凭借其丰富的生态系统、简洁的语法和强大的第三方库支持，非常适合快速开发和迭代 AI 相关应用。项目选用的核心依赖包括 lark-oapi（飞书 SDK）、google-genai（Google Gemini 官方 SDK）、Flask（轻量级 Web 框架）以及 python-dotenv（环境变量管理），这些库都经过生产环境验证，具有良好的稳定性和性能表现。

Flask 作为 Web 框架被选用的原因是其轻量级和灵活性，能够满足系统对 HTTP 接口的需求，同时不会引入过重的框架负担。Flask-CORS 扩展用于处理跨域请求问题，虽然系统内部通信不存在跨域场景，但该扩展为将来可能的 Web 前端集成预留了扩展能力。requests 库用于发起 HTTP 请求，其简洁的 API 设计大大简化了客户端开发工作。

飞书 SDK（lark-oapi）提供了完整的飞书开放平台能力封装，包括事件订阅、消息收发、卡片消息等功能。该 SDK 支持事件回调和主动推送两种消息获取方式，本项目采用事件回调模式，通过长连接接收飞书推送的实时消息。Google Gemini SDK（google-genai）封装了 Gemini API 的所有功能，支持对话生成、代码生成、流式输出等能力，项目主要使用其对话生成功能来提供 AI 智能回复。

### 容器化与部署技术

项目采用 Docker 作为容器化解决方案，使用 Docker Compose 进行多服务编排。Docker 技术的引入解决了环境一致性问题，确保开发、测试和生产环境具有相同的依赖和配置。每个服务都有独立的 Dockerfile，通过多阶段构建和依赖缓存机制优化镜像构建速度。Docker Compose 3.8 版本的使用确保了与现代 Docker 引擎的兼容性，同时支持复杂的网络配置和服务依赖管理。

服务配置采用环境变量注入方式，主服务使用 `.env` 文件，OpenCode 服务使用 `.env.opencode` 文件。这种配置管理方式遵循了十二因子应用原则，使得应用可以在不同环境中无缝迁移，无需修改代码即可调整配置。日志管理方面，系统将日志输出到 Docker 日志驱动，采用 JSON 格式便于后续的日志收集和分析，日志文件大小限制为 50MB，保留最近 5 个日志文件。

Node.js 环境作为备用技术栈保留在项目中，主要用于运行基于 Express 的服务器实现。当 Python 服务出现兼容性问题或需要利用 Node.js 生态优势时，可以快速切换到 Node.js 方案。这种双技术栈设计为系统提供了更高的灵活性，但当前生产环境主要使用 Python 方案。

## 目录结构

项目目录结构设计遵循清晰的职责划分原则，每个目录和文件都有明确的用途：

```
clawdbot-gemini/
├── docker-compose.yml           # Docker Compose 编排配置，定义服务、网络和存储
├── Dockerfile                   # Clawdbot 服务镜像定义，基于 Python 3.10 slim
├── requirements.txt             # Python 依赖清单，包含 6 个核心包
├── .env                         # 主服务环境变量文件，存储敏感配置
├── .env.opencode               # OpenCode 服务专用环境变量
├── .env.example                # 环境变量模板，便于新环境部署
├── DEPLOYMENT.md               # 部署指南文档
│
├── src/                        # Clawdbot 服务源代码目录
│   ├── __init__.py            # Python 包初始化文件
│   ├── main.py                # 应用入口，负责初始化和事件处理
│   ├── bot.py                 # 消息处理器，实现消息分发和回复逻辑
│   ├── client.py              # 飞书 API 客户端封装
│   ├── llm.py                 # Gemini 模型交互封装
│   ├── opencode.py            # OpenCode 服务客户端封装
│   ├── utils.py               # 工具函数集合
│   └── executor.py            # 代码执行器（备用方案）
│
├── opencode/                   # OpenCode 服务目录（官方版本）
│   ├── Dockerfile.official    # 官方 OpenCode 镜像定义
│   ├── server.js              # Node.js 服务端实现
│   ├── package.json           # Node.js 依赖定义
│   ├── opencode.json          # OpenCode 配置文件
│   ├── opencode.service       # systemd 服务配置
│   └── opencode_acp.service   # systemd ACP 服务配置
│
└── test_*.py                   # 单元测试文件，用于功能验证
```

目录结构的设计遵循了高内聚低耦合的原则，每个模块的源代码集中放置，便于维护和理解。配置文件与源代码分离，通过环境变量进行配置注入，使得同一套代码可以运行在不同的部署环境中。测试文件独立于源代码之外，但在包结构上保持一致，便于找到对应的测试用例。

## 核心组件详解

### Clawdbot 服务组件

#### 主程序入口（main.py）

主程序文件是整个 Clawdbot 服务的入口点，负责应用程序的初始化、事件处理和生命周期管理。程序采用面向对象设计，通过 `ClawdbotApplication` 类封装所有应用逻辑。主要功能包括：加载环境变量配置、初始化飞书客户端、初始化 Gemini 模型、注册事件处理回调、启动 Web 服务以及优雅关闭处理。

程序启动时会先加载 `.env` 文件中的环境变量，包括飞书应用配置、Gemini API 密钥和 OpenCode 服务地址等。随后初始化日志系统，设置日志级别并创建日志文件。接下来依次初始化各个组件：创建飞书客户端实例、初始化 Gemini 模型实例、创建 OpenCode 客户端实例，最后将事件处理器注册到飞书 SDK 的事件回调中。

事件处理采用异步模式，飞书 SDK 在后台线程中持续监听事件推送。主程序通过信号处理机制捕获系统关闭信号，执行优雅退出逻辑，包括关闭数据库连接、保存运行时状态和清理临时文件等。消息去重机制通过维护一个 `processed_messages` 集合来实现，避免因网络重试导致的重复处理。

#### 消息处理器（bot.py）

消息处理器是 Clawdbot 服务处理业务逻辑的核心组件，负责解析飞书消息、判断消息类型并执行相应的处理策略。`MessageHandler` 类封装了所有消息处理相关的功能，包括私聊消息处理、群组消息处理、消息编辑处理和消息删除处理等场景。

私聊消息处理流程首先提取消息内容中的文本信息，然后根据文本内容判断用户意图。对于简单的问答类请求，处理器直接调用 Gemini 模型获取回复；对于涉及代码执行的需求，处理器将请求转发给 OpenCode 服务。群组消息处理需要额外处理 @消息的场景，识别消息中是否包含对机器人的提及，并提取有效的用户输入。

消息回复通过调用飞书消息 API 实现，支持文本消息、富文本消息和卡片消息等多种消息类型。处理器会根据消息内容的复杂度选择合适的回复类型：简单问答使用文本消息，复杂代码结果使用富文本消息或卡片消息。错误处理机制确保即使在异常情况下也能向用户返回友好的错误提示。

#### 飞书客户端（client.py）

飞书客户端模块封装了所有与飞书开放平台交互的功能，提供了高层次的 API 供上层业务逻辑调用。`FeishuBot` 类封装了应用凭证管理、签名验证、请求签名和 API 调用等底层细节，对外暴露简单易用的消息收发接口。

客户端初始化时需要提供 App ID、App Secret、Encrypt Key 和 Verification Token，这些凭证从环境变量中读取。SDK 会自动处理凭证的刷新逻辑，当访问令牌过期时自动申请新的令牌。消息接收支持事件回调和轮询两种模式，本项目采用事件回调模式，通过长连接实时接收飞书推送的事件。

API 调用封装覆盖了项目所需的所有飞书能力，包括发送消息（支持文本、富文本、卡片等多种类型）、回复消息、获取用户信息、获取群组信息等。每个 API 方法都进行了异常处理封装，将飞书 SDK 的异常转换为统一的业务异常格式，便于上层业务逻辑处理。

#### OpenCode 服务

本项目使用官方 OpenCode 服务，通过 Docker 容器部署在 `opencode_service:8080`。服务通过 `/v1/chat/completions` 端点提供 OpenAI 兼容的 API 接口，支持 Gemini 模型调用。

#### Gemini 集成模块（llm.py）

Gemini 集成模块封装了 Google Gemini API 的所有功能，为项目提供统一的模型调用接口。模块采用工厂模式设计，通过 `init_gemini` 函数创建模型实例，通过 `get_response` 函数获取模型回复。这种设计使得模型调用逻辑与业务逻辑分离，便于后续的模型升级和替换。

模块使用的 Google Gen AI SDK（google-genai）是 Google 官方提供的 Gemini API 封装库，支持最新的 Gemini 模型功能。默认使用的模型为 `gemma-3-27b-it`，这是一款专为对话场景优化的模型，具有良好的指令遵循能力和代码生成能力。模块还支持自定义模型选择，通过 `model` 参数可以指定不同的模型版本。

API 调用采用同步方式，通过 `model.models.generate_content` 方法发起请求。响应处理提取文本内容并返回，异常处理捕获 API 调用过程中的各类错误，包括网络错误、认证错误和速率限制等。模块还预留了流式输出的扩展接口，未来的版本可以支持流式响应以提升用户体验。

### OpenCode 服务组件

本项目使用官方 OpenCode 服务，所有服务配置和维护由官方镜像处理。

## 部署指南

### 环境准备

部署前需要确保目标环境满足以下要求。首先需要安装 Docker Engine 20.10 或更高版本，以及 Docker Compose 2.0 或更高版本。可以通过官方文档中的安装指南完成 Docker 的安装和配置。安装完成后运行 `docker --version` 和 `docker-compose --version` 验证安装是否成功。

其次需要准备 Git 用于代码克隆和版本管理。确保目标服务器可以通过 SSH 或 HTTPS 方式访问代码仓库。对于远程部署场景，还需要配置 SSH 密钥认证以便从本地推送代码到远程服务器。最后检查目标服务器的磁盘空间，确保有足够的空间存储 Docker 镜像和运行时数据。

### 配置环境变量

项目使用两个环境变量文件分别配置两个服务。创建 `.env` 文件配置主服务参数：

```bash
# 飞书应用配置
FEISHU_APP_ID=你的飞书App ID
FEISHU_APP_SECRET=你的飞书App Secret
FEISHU_ENCRYPT_KEY=飞书Encrypt Key
FEISHU_VERIFICATION_TOKEN=飞书Verification Token

# Gemini API 配置
GOOGLE_API_KEY=你的Google API Key

# OpenCode 服务配置
OPENCODE_API_BASE_URL=http://opencode_service:8080/v1
OPENCODE_API_KEY=my_internal_secret_2024

# 日志级别
LOG_LEVEL=INFO
```

创建 `.env.opencode` 文件配置 OpenCode 服务参数：

```bash
# Gemini API 配置（OpenCode 使用）
GOOGLE_API_KEY=你的Google API Key

# OpenCode 服务配置
OPENCODE_API_KEY=my_internal_secret_2024
OPENCODE_HOST=0.0.0.0
OPENCODE_PORT=8080
OPENCODE_DEBUG=false
LOG_LEVEL=INFO
```

注意两个文件中的 `GOOGLE_API_KEY` 需要设置为相同的值，确保两个服务都能正确访问 Gemini API。

### 启动服务

使用 Docker Compose 命令构建并启动所有服务：

```bash
# 构建镜像并启动服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看实时日志
docker-compose logs -f
```

服务启动顺序由 `depends_on` 配置控制，Clawdbot 服务会等待 OpenCode 服务健康检查通过后才启动。首次启动会自动拉取基础镜像并构建应用镜像，这个过程可能需要几分钟时间。后续启动会使用缓存的镜像，启动速度会快很多。

### 验证部署

服务启动后需要进行功能验证确保部署成功。首先检查 OpenCode 服务的健康状态：

```bash
curl http://localhost:8080/health
```

正常响应应该包含健康状态和版本信息：

```json
{"status":"healthy","timestamp":"2024-01-01T00:00:00","version":"1.0.0"}
```

然后验证 OpenCode 服务的模型列表 API：

```bash
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer my_internal_secret_2024"
```

最后验证聊天完成 API：

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_internal_secret_2024" \
  -d '{
    "model": "opencode-1.0",
    "messages": [{"role": "user", "content": "你好，请介绍一下你自己"}]
  }'
```

如果所有 API 调用都返回了预期结果，说明服务部署成功。可以在飞书应用中向机器人发送消息进行端到端测试。

## 安全机制

### API 认证

系统实现了多层 API 认证机制，确保只有授权的请求才能访问服务功能。OpenCode 服务采用 Bearer Token 认证方式，所有 API 请求都需要在请求头中携带有效的认证令牌。认证令牌在环境变量中配置，默认值为 `my_internal_secret_2024`，生产环境应该使用更复杂的密钥。

认证中间件会在每个请求处理前执行，它会从请求头中提取 Authorization 字段，验证其格式和内容是否正确。验证失败会返回 401 状态码和详细的错误信息。内部网络中的服务间调用也使用相同的认证机制，确保没有未经授权的服务能够访问 OpenCode 功能。

### 飞书安全验证

飞书平台本身提供了多层次的安全保障机制。首先是签名验证，飞书推送的事件会包含签名，服务器需要验证签名有效性才能处理事件。签名使用应用凭证生成，攻击者无法伪造有效的签名。其次是加密传输，所有飞书 API 调用都通过 HTTPS 加密传输，防止中间人攻击。

应用级别的安全由 Encrypt Key 和 Verification Token 提供保障。Encrypt Key 用于消息内容的加解密，确保敏感信息不会在传输过程中泄露。Verification Token 用于验证飞书推送事件的来源，防止伪造事件攻击。这些凭证应该妥善保管，不要硬编码在代码中或泄露到公开渠道。

### 代码执行安全

代码执行是系统中安全风险最高的环节，需要特别严格的安全措施。代码执行器实现了多层防护机制：输入验证层会检查代码内容，识别并拦截危险的操作模式，如文件读写、系统命令调用、网络请求等；执行环境层使用隔离的容器环境运行代码，即使代码包含恶意操作也不会影响宿主系统；执行监控层会实时监控代码执行状态，发现异常行为会立即终止执行。

代码执行超时机制防止无限循环或长时间运行消耗系统资源。默认超时时间为 30 秒，超时后会强制终止执行进程并返回超时错误。执行结果会在返回后清理临时文件，防止敏感数据残留。日志中不会记录代码执行的具体内容，保护用户隐私数据。

## API 参考

### OpenCode API

OpenCode 服务提供 OpenAI 兼容的 RESTful API，所有接口都遵循相同的请求和响应格式。

#### 健康检查

获取服务健康状态，用于监控和服务发现。

- **端点**：`GET /health`
- **请求参数**：无
- **响应**：
  ```json
  {
    "status": "healthy",
    "timestamp": "2024-01-01T00:00:00",
    "version": "1.0.0"
  }
  ```

#### 模型列表

获取可用的模型列表。

- **端点**：`GET /v1/models`
- **请求头**：Authorization: Bearer \<api_key\>
- **响应**：
  ```json
  {
    "object": "list",
    "data": [
      {
        "id": "opencode-1.0",
        "object": "model",
        "created": 1704067200,
        "owned_by": "system"
      }
    ]
  }
  ```

#### 聊天完成

发送对话请求，获取 AI 生成的回答或代码。

- **端点**：`POST /v1/chat/completions`
- **请求头**：Authorization: Bearer \<api_key\>
- **请求体**：
  ```json
  {
    "model": "opencode-1.0",
    "messages": [
      {
        "role": "user",
        "content": "请用 Python 实现快速排序算法"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 2048
  }
  ```
- **响应**：
  ```json
  {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1704067200,
    "model": "opencode-1.0",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "def quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 15,
      "completion_tokens": 58,
      "total_tokens": 73
    }
  }
  ```

## 扩展指南

### 添加新语言支持

代码执行器当前支持 Python、JavaScript 和 Bash 三种语言。如需添加新的语言支持，需要修改 `opencode/src/executor.py` 文件中的 `supported_languages` 配置和 `execute_code` 方法。添加新语言需要考虑以下因素：语言运行时环境的安装、代码执行命令的配置、安全策略的制定以及错误处理逻辑的实现。

### 替换 AI 模型

项目目前使用 Google Gemini 模型，可以通过修改 `init_gemini` 函数和调用方式切换到其他模型提供商。替换过程需要修改两个地方：Clawdbot 服务的 `src/llm.py` 和 OpenCode 服务的 `opencode/src/llm.py`。新的模型需要提供类似的 API 接口，或者在调用处进行适配层转换。

### 集成其他通讯平台

除了飞书，项目还可以集成微信、钉钉等其他通讯平台。这需要在 `src/client.py` 中添加对应平台的 SDK 封装，在 `src/bot.py` 中添加对应的消息处理逻辑，在主程序中配置对应的事件回调入口。由于不同平台的事件格式和 API 差异较大，这部分工作需要针对每个平台单独实现。

## 常见问题

**服务启动失败怎么办？**

首先检查 Docker 服务是否正常运行，然后查看详细日志定位问题。常见原因包括：环境变量配置不完整、Docker 镜像构建失败、端口被占用等。运行 `docker-compose logs` 查看各服务的详细日志，根据错误信息进行排查。

**代码执行没有反应？**

检查 OpenCode 服务是否正常运行，确认 Google API Key 配置正确且有足够配额。代码执行超时时间由 OpenCode 服务控制，如需调整请参考官方文档配置服务参数。

**飞书消息接收不到？**

检查飞书应用的回调配置是否正确，确认服务器能够访问公网并能接收飞书的 Webhook 请求。验证事件订阅是否开启，应用凭证是否正确。如果使用 HTTPS，确保 SSL 证书有效且配置正确。

## 许可证

本项目采用 MIT 许可证开源，您可以自由使用、修改和分发本项目的代码，但需要保留原始的许可证声明。
