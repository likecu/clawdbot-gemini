#!/bin/bash
export OPENROUTER_API_KEY=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
export OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-r1
export OPENROUTER_API_BASE_URL=https://openrouter.ai/api/v1
cd /home/milk/clawdbot-gemini/opencode
node server.js
