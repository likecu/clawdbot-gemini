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
DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "gemini-2.0-flash")

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
            {"id": "gemini-3-flash-preview", "object": "model", "created": int(time.time()), "owned_by": "google"},
            {"id": "gemini-2.0-flash-exp", "object": "model", "created": int(time.time()), "owned_by": "google"},
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        tools = body.get("tools", [])
        if messages:
             logger.info(f"System Prompt Length: {len(messages[0].get('content', ''))}")
             logger.info(f"System Prompt Start: {str(messages[0].get('content', ''))[:500]}...")
        if tools:
             logger.info(f"Tools provided: {len(tools)} tools")
             
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
            role = msg["role"]
            content = extract_text(msg.get("content", ""))
            
            # OpenAI roles: system, user, assistant, tool
            # Gemini roles for history: user, model
            if role == "system":
                # 把 system prompt 也当成 user 消息的起始部分（Gemini 通常如此处理）
                if content:
                    history.append({"role": "user", "parts": [content]})
            elif role == "user":
                if content:
                    history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                if content:
                    history.append({"role": "model", "parts": [content]})
                # 如果有 tool_calls，Gemini history 格式比较复杂，暂简化为文本描述
            elif role == "tool":
                # 工具执行结果
                if content:
                    history.append({"role": "user", "parts": [f"工具执行结果: {content}"]})
        
        last_user_msg = extract_text(messages[-1].get("content", ""))
        
        # 统计所有发送的 Token (包含 System, History, User, Tools)
        total_input_content = ""
        for msg in messages:
            total_input_content += extract_text(msg.get("content", ""))
        
        # 将工具定义也计入 Token 统计
        if tools:
            import json
            total_input_content += json.dumps(tools)

        logger.info(f"Generating response for model: {model_name}")
        logger.info(f"Total input content length (approx.): {len(total_input_content)} characters")
        
        # 准备工具格式转换
        gemini_tools_input = []
        if tools:
            for t in tools:
                if t["type"] == "function":
                    func = t["function"]
                    
                    # [HOTFIX] 移除与原生自带 DuckDuckGo 文本指令冲突的 OpenClaw 'web_search' 工具
                    # 防止因为服务端没有配置 Brave 密钥而报错
                    if func["name"] == "web_search":
                        logger.info("Filtered out 'web_search' tool to avoid conflict with native DuckDuckGo text instructions.")
                        continue
                        
                    params = func.get("parameters", {"type": "object", "properties": {}})
                    
                    # Gemini SDK 期望类型是大写 (OBJECT, STRING, NUMBER 等)
                    def normalize_types(obj):
                        if isinstance(obj, dict):
                            if "type" in obj and isinstance(obj["type"], str):
                                # 映射小写到大写，或者保持原样
                                type_map = {
                                    "string": "STRING",
                                    "number": "NUMBER",
                                    "integer": "INTEGER",
                                    "boolean": "BOOLEAN",
                                    "array": "ARRAY",
                                    "object": "OBJECT"
                                }
                                obj["type"] = type_map.get(obj["type"].lower(), obj["type"])
                            
                            for k, v in obj.items():
                                normalize_types(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                normalize_types(item)
                    
                    import copy
                    normalized_params = copy.deepcopy(params)
                    normalize_types(normalized_params)

                    gemini_tools_input.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": normalized_params
                    })

        # 调用 Gemini (llm.py 中的方法)
        response_text, tool_calls = get_response_with_history(
            gemini_client, last_user_msg, history, tools=gemini_tools_input
        )
        logger.info(f"Response generated: {response_text[:100]}... (Tools: {len(tool_calls)})")
        
        message_out = {
            "role": "assistant",
            "content": response_text if response_text else None,
        }
        if tool_calls:
            message_out["tool_calls"] = tool_calls

        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": message_out,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(total_input_content) // 4,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": (len(total_input_content) + len(response_text)) // 4
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
