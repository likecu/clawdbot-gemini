"""
Gemini API接口封装模块

提供与Google Gemini模型交互的功能，包括初始化、生成内容等操作
"""

import google.genai as genai
from typing import Optional, Any, List, Dict
import os


def init_gemini(api_key: Optional[str] = None, model: str = "gemini-2.0-flash") -> Any:
    """
    初始化Gemini模型

    Args:
        api_key: Google API密钥，如果为None则从环境变量GOOGLE_API_KEY获取
        model: 模型名称，默认为gemma-3-27b-it

    Returns:
        初始化后的模型实例

    Raises:
        ValueError: 当api_key为空且环境变量中也不存在时抛出
    """
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("Google API Key未配置，请设置GOOGLE_API_KEY环境变量或传入api_key参数")
    
    # 创建客户端
    client = genai.Client(api_key=api_key)
    
    return client


def get_response(model: Any, user_message: str) -> str:
    """
    获取Gemini生成的回复

    Args:
        model: 已初始化的模型实例
        user_message: 用户发送的消息内容

    Returns:
        str: Gemini生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常，包含错误信息
    """
    try:
        response = model.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_message
        )
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")


def get_response_with_history(model: Any, 
                               user_message: str, 
                               history: Optional[List[Dict]] = None,
                               tools: Optional[List[Dict]] = None) -> tuple[str, List[Dict]]:
    """
    获取Gemini生成的回复（支持对话历史和工具调用）

    Args:
        model: 已初始化的模型实例
        user_message: 用户发送的消息内容
        history: 对话历史列表，每条记录为{'role': 'user'/'model', 'parts': [...]}
        tools: 工具定义列表 (OpenAPI/OpenAI 格式)

    Returns:
        tuple[str, List[Dict]]: (回复文本, 工具调用列表)

    Raises:
        Exception: API调用失败时抛出异常
    """
    try:
        # 构建消息内容
        contents = []
        
        # 添加历史消息
        if history:
            for msg in history:
                role = msg.get("role", "user")
                # Gemini role: user, model
                gemini_role = "user" if role in ["user", "system", "tool"] else "model"
                
                parts = []
                # 处理普通文本
                source_parts = msg.get("parts", [])
                for p in source_parts:
                    if isinstance(p, str):
                        parts.append({"text": p})
                    elif isinstance(p, dict):
                        parts.append(p)
                
                if parts:
                    contents.append({
                        "role": gemini_role,
                        "parts": parts
                    })
        
        # 添加当前消息
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
        # 配置工具
        gemini_tools = None
        if tools:
            # 这里的 tools 已经是转换后的格式了
            gemini_tools = [{"function_declarations": tools}]

        response = model.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=genai.types.GenerateContentConfig(
                tools=gemini_tools if gemini_tools else None
            ) if gemini_tools else None
        )
        
        response_text = ""
        tool_calls = []
        
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        response_text += part.text
                    if part.function_call:
                        import os
                        tool_calls.append({
                            "id": f"call_{os.urandom(4).hex()}",
                            "type": "function",
                            "function": {
                                "name": part.function_call.name,
                                "arguments": part.function_call.args
                            }
                        })
        
        return response_text, tool_calls
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise Exception(f"Gemini API调用失败: {str(e)}")
