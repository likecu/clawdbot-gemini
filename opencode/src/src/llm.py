"""
Gemini API接口封装模块

提供与Google Gemini模型交互的功能，包括初始化、生成内容等操作
"""

import google.genai as genai
from typing import Optional, Any, List, Dict
import os


def init_gemini(api_key: Optional[str] = None, model: str = "gemini-1.5-flash") -> Any:
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
            model="gemini-1.5-flash",
            contents=user_message
        )
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")


def get_response_with_history(model: Any, 
                              user_message: str, 
                              history: Optional[List[Dict]] = None) -> str:
    """
    获取Gemini生成的回复（支持对话历史）

    Args:
        model: 已初始化的模型实例
        user_message: 用户发送的消息内容
        history: 对话历史列表，每条记录为{'role': 'user'/'model', 'parts': [text]}

    Returns:
        str: Gemini生成的回复文本

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
                parts = msg.get("parts", [])
                
                # 确保 parts[0] 是字符串，如果不是则尝试提取
                raw_content = parts[0] if parts else ""
                if isinstance(raw_content, str):
                    text_content = raw_content
                elif isinstance(raw_content, list):
                    # 处理嵌套列表的情况
                    text_content = "".join([p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in raw_content])
                else:
                    text_content = str(raw_content)

                contents.append({
                    "role": role,
                    "parts": [{"text": text_content}]
                })
        
        # 添加当前消息
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
        response = model.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents
        )
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")
