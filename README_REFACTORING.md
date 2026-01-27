# Clawdbot重构项目

## 项目概述

本项目是对Claswdbot的现代化重构，从传统的简单问答机器人向基于OpenCode智能体范式的自动化编码助手演进。

## 核心特性

- **零公网依赖**：通过WebSocket长连接通信，无需内网穿透或公网IP
- **深度推理**：集成DeepSeek R1模型，支持复杂逻辑推理
- **原生体验**：完美适配飞书富文本格式，代码块支持语法高亮
- **上下文记忆**：基于Redis的多轮对话管理

## 架构设计

### 六边形架构

```
src/
├── adapters/          # 外部适配器
│   ├── lark/         # 飞书开放平台适配器
│   └── llm/          # LLM模型适配器
├── core/             # 核心业务逻辑
│   ├── agent.py      # 智能体核心
│   ├── session.py    # 会话管理
│   └── prompt.py     # 提示词工程
├── infrastructure/   # 基础设施
│   ├── redis_client.py
│   └── deepseek_client.py
└── main.py           # 应用入口
```

## 技术栈

- Python 3.11+
- lark-oapi (飞书SDK)
- DeepSeek API (通过OpenRouter)
- Redis (会话存储)
- Docker

## 快速开始

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件填入凭证
# LARK_APP_ID=cli_xxx
# LARK_APP_SECRET=xxx
# OPENROUTER_API_KEY=sk-xxx

# 使用Docker启动
docker-compose up --build
```

## 开发指南

详细开发指南请参阅项目文档。
