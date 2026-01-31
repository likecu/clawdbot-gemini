#!/bin/bash
# OPENROUTER_API_KEY 应从环境变量或 .env 文件中加载
# export OPENROUTER_API_KEY=你的密钥
export OPENROUTER_DEFAULT_MODEL=${OPENROUTER_DEFAULT_MODEL:-"deepseek/deepseek-r1"}
export OPENROUTER_API_BASE_URL=${OPENROUTER_API_BASE_URL:-"https://openrouter.ai/api/v1"}
cd "$(dirname "$0")"
node server.js
