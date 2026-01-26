"""
Gemini API接口封装模块

提供与Google Gemini模型交互的功能，包括初始化、生成内容等操作
"""

import google.generativeai as genai
from typing import Optional, Any
import os


def init_gemini(api_key: Optional[str] = None, model: str = "gemini-1.5-pro-latest") -> Any:
    """
    初始化Gemini模型

    Args:
        api_key: Google API密钥，如果为None则从环境变量GOOGLE_API_KEY获取
        model: 模型名称，默认为gemini-1.5-pro

    Returns:
        GenerativeModel实例

    Raises:
        ValueError: 当api_key为空且环境变量中也不存在时抛出
    """
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("Google API Key未配置，请设置GOOGLE_API_KEY环境变量或传入api_key参数")
    
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model)


def get_response(model: genai.GenerativeModel, user_message: str) -> str:
    """
    获取Gemini生成的回复

    Args:
        model: 已初始化的GenerativeModel实例
        user_message: 用户发送的消息内容

    Returns:
        str: Gemini生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常，包含错误信息
    """
    try:
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")


def get_response_with_history(model: genai.GenerativeModel, 
                              user_message: str, 
                              history: Optional[list] = None) -> str:
    """
    获取Gemini生成的回复（支持对话历史）

    Args:
        model: 已初始化的GenerativeModel实例
        user_message: 用户发送的消息内容
        history: 对话历史列表，每条记录为{'role': 'user'/'model', 'parts': [text]}

    Returns:
        str: Gemini生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常
    """
    try:
        chat = model.start_chat(history=history or [])
        response = chat.send_message(user_message)
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")