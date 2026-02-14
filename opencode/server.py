import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import time

# 添加 src 到路径
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.llm import init_gemini, get_response_with_history

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpenCodeServer")

app = FastAPI(title="OpenCode API Server")

# 初始化 LLM
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "gemini-1.5-flash")

def extract_text(content: Any) -> str:
    """从 OpenAI 格式的内容中提取纯文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                if "text" in part:
                    texts.append(part["text"])
                elif "type" in part and part["type"] == "text" and "text" in part:
                    texts.append(part["text"])
            elif isinstance(part, str):
                texts.append(part)
        return "".join(texts)
    return str(content)

gemini_client = None

@app.on_event("startup")
async def startup_event():
    global gemini_client
    try:
        if GOOGLE_API_KEY:
            gemini_client = init_gemini(GOOGLE_API_KEY)
            logger.info("Gemini client initialized successfully.")
        else:
            logger.warning("GOOGLE_API_KEY not found in environment variables.")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "provider": "opencode-python",
        "model": DEFAULT_MODEL,
        "gemini_initialized": gemini_client is not None
    }

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gemma-3-27b-it", "object": "model", "created": int(time.time()), "owned_by": "google"},
            {"id": "gemini-2.0-flash-exp", "object": "model", "created": int(time.time()), "owned_by": "google"},
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        model_name = body.get("model", DEFAULT_MODEL)
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages are required")
        
        if not gemini_client:
            raise HTTPException(status_code=500, detail="Gemini client not initialized")

        # 提取最后一条用户消息和历史
        last_user_msg = ""
        history = []
        
        # 将 OpenAI 格式转换为 Gemini history 格式
        # Gemini 期望: [{'role': 'user'/'model', 'parts': [text]}]
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            content = extract_text(msg.get("content", ""))
            if content:
                history.append({"role": role, "parts": [content]})
        
        last_user_msg = extract_text(messages[-1].get("content", ""))
        
        logger.info(f"Generating response for model: {model_name}")
        
        # 调用 Gemini (llm.py 中的方法)
        response_text = get_response_with_history(gemini_client, last_user_msg, history)
        
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(last_user_msg) // 4, # 简单估算
                "completion_tokens": len(response_text) // 4,
                "total_tokens": (len(last_user_msg) + len(response_text)) // 4
            }
        }
        
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e)}}
        )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8082))
    uvicorn.run(app, host="0.0.0.0", port=port)
