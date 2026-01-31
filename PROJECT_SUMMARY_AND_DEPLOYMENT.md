# 项目结构与部署方案

本文档总结了 Clawdbot-Gemini 项目的当前结构、核心组件以及部署到远程服务器的详细方案。

## 1. 项目概述

Clawdbot-Gemini 是一个基于 LLM 的智能编程助手和聊天机器人，整合了飞书 (Lark) 和 QQ (通过 NapCat) 平台。项目采用微服务架构，主要包含核心业务逻辑服务、OpenCode 代码能力服务以及 QQ 协议适配服务。

## 2. 项目结构

### 根目录概览

```text
clawdbot-gemini/
├── .env                  # 环境变量配置 (需要手动创建)
├── docker-compose.yml    # 主服务的 Docker 编排文件 (Clawdbot + Opencode)
├── napcat_compose.yml    # QQ 协议适配服务 (NapCat) 的 Docker 编排文件
├── clawdbot_http_wrapper.js # Node.js 包装器，用于调用 clawdbot CLI 并提供 HTTP 接口
├── src/                  # Python 核心源代码
│   ├── main.py           # 程序入口，FastAPI 应用
│   ├── core/             # 核心逻辑 (Agent, Session, Prompt)
│   ├── adapters/         # 适配器 (QQ, Lark, LLM)
│   ├── infrastructure/   # 基础设施 (Redis 等)
│   └── config/           # 配置文件
├── opencode/             # OpenCode 服务源码 (工程师角色)
└── Dockerfile            # Clawdbot 主服务的构建文件
```

### 关键文件说明

*   **`src/main.py`**: 项目的主入口点。初始化 FastAPI 服务器，启动 Lark 和 QQ 客户端，并处理 HTTP 回调和 WebSocket 连接。
*   **`docker-compose.yml`**: 定义了两个主要服务：
    *   `opencode_service`: 运行在 8082 端口，提供代码执行和工程能力的 API。
    *   `clawdbot`: 运行在 8081 端口，核心聊天机器人服务，依赖于 `opencode_service`。
*   **`napcat_compose.yml`**: 定义了 `napcat` 服务，运行在 3000(HTTP)/8080(WS) 端口，作为无头 QQ 客户端，将 QQ 协议转换为 HTTP/WebSocket 供 Clawdbot 调用。
*   **`clawdbot_http_wrapper.js`**: 一个 Node.js 中间件，用于通过 HTTP 请求触发本地 `clawdbot` CLI 工具，并解析 session 文件将结果流式传回。

## 3. 系统架构

系统主要由三个容器化服务组成：

1.  **Clawdbot Service (Python/FastAPI)**:
    *   **角色**: 项目经理 / 核心控制器。
    *   **功能**: 接收来自 QQ/飞书的消息，维护会话上下文，调用 LLM 进行决策，并分发任务。
    *   **端口**: 8081

2.  **Opencode Service (Python)**:
    *   **角色**: 工程师 / 执行者。
    *   **功能**: 提供环境进行代码编写、执行和调试。
    *   **端口**: 8082

3.  **NapCat Service (Docker Image)**:
    *   **角色**: QQ 协议网关。
    *   **功能**: 模拟 QQ 客户端，登录账号，并通过 HTTP/WebSocket 转发消息事件。
    *   **端口**: 3000 (HTTP), 8080 (WS)

## 4. 远程部署方案

### 服务器信息
*   **IP**: `34.72.125.220`
*   **用户**: `milk`
*   **项目路径**: `/home/milk` (具体子目录需确认，假设为 `/home/milk/clawdbot-gemini` 或类似)

### 部署前提
*   本地已配置好 SSH 访问：`ssh -i ~/.ssh/milk milk@34.72.125.220`
*   服务器已安装 Docker 和 Docker Compose。

### 部署步骤

#### 1. 连接服务器
```bash
ssh -i ~/.ssh/milk milk@34.72.125.220
cd /home/milk/clawdbot-gemini  # 进入项目目录
```

#### 2. 更新代码
从 GitHub 拉取最新代码：
```bash
git pull
```

#### 3. 环境变量配置
确保 `.env` 文件存在且包含必要的配置（API Key, SQL 密码等）。
*   检查 `.env` 文件：`cat .env`
*   如果需要修改：`vim .env`

#### 4. 重启业务服务 (Clawdbot & Opencode)
当更新了 `src/` 或 `opencode/` 代码时，执行以下命令重构建并重启：

```bash
docker-compose down
docker-compose up -d --build
```

此命令会：
*   停止并移除旧容器。
*   根据 Dockerfile 重新构建镜像 (包含新的 Python 代码)。
*   后台启动服务。

#### 5. 管理 NapCat QQ 服务
NapCat 服务通常不需要频繁重启，除非配置文件变更或服务挂掉。

*   **启动/重启**:
    ```bash
    docker-compose -f napcat_compose.yml up -d
    ```
*   **查看日志 (用于扫码登录)**:
    如果是第一次运行或登录失效，需要查看日志获取二维码：
    ```bash
    docker logs -f napcatqq
    ```
    或者通过 Clawdbot 的 API 接口查看二维码。

### 常见操作命令

*   **查看所有容器状态**:
    ```bash
    docker ps -a
    ```
*   **查看应用日志**:
    ```bash
    docker logs -f clawdbot_gemini
    ```
*   **查看 Opencode 日志**:
    ```bash
    docker logs -f clawdbot_opencode
    ```

## 5. 数据库与密码备忘

*   **MySQL 数据库密码**: `!A33b3e561fec`
*   **GitHub 同步**: 需要 SSH 链接，推送代码到 `https://github.com/likecu`。

## 6. 注意事项

*   **Python 环境**: 本地开发有两个 Python 环境，服务器端使用 Docker 容器内的 Python 环境 (基于 `python:3.10-slim`)，确保 `requirements.txt` 包含所有依赖。
*   **OCR 工具**: 本地有 `gemini_ocr.py` 工具可用于图像识别测试。
