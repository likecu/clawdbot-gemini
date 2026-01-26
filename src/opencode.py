"""
OpenCode API接口封装模块

提供与OpenCode模型交互的功能，包括初始化、生成内容等操作
"""

import requests
from typing import Optional, Any
import os
import json


def init_opencode(api_key: Optional[str] = None, base_url: Optional[str] = None) -> dict:
    """
    初始化OpenCode配置

    Args:
        api_key: OpenCode API密钥，如果为None则从环境变量OPENCODE_API_KEY获取
        base_url: OpenCode API基础URL，如果为None则使用默认值

    Returns:
        dict: 包含配置信息的字典

    Raises:
        ValueError: 当api_key为空且环境变量中也不存在时抛出
    """
    if api_key is None:
        api_key = os.getenv("OPENCODE_API_KEY")
    
    if not api_key:
        raise ValueError("OpenCode API Key未配置，请设置OPENCODE_API_KEY环境变量或传入api_key参数")
    
    if base_url is None:
        base_url = os.getenv("OPENCODE_BASE_URL", "https://opencode-api.example.com/v1")
    
    return {
        "api_key": api_key,
        "base_url": base_url
    }


def get_response(config: dict, user_message: str, model: str = "opencode-1.0") -> str:
    """
    获取OpenCode生成的回复

    Args:
        config: 包含OpenCode配置的字典
        user_message: 用户发送的消息内容
        model: 模型名称，默认为opencode-1.0

    Returns:
        str: OpenCode生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常，包含错误信息
    """
    try:
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
        
    except requests.RequestException as e:
        raise Exception(f"OpenCode API调用失败: {str(e)}")
    except (KeyError, ValueError) as e:
        raise Exception(f"OpenCode API响应解析失败: {str(e)}")


def get_response_with_history(config: dict, 
                              user_message: str, 
                              history: Optional[list] = None, 
                              model: str = "opencode-1.0") -> str:
    """
    获取OpenCode生成的回复（支持对话历史）

    Args:
        config: 包含OpenCode配置的字典
        user_message: 用户发送的消息内容
        history: 对话历史列表，每条记录为{'role': 'user'/'assistant', 'content': 'text'}
        model: 模型名称，默认为opencode-1.0

    Returns:
        str: OpenCode生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常，包含错误信息
    """
    try:
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}"
        }
        
        messages = []
        if history:
            messages.extend(history)
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
        
    except requests.RequestException as e:
        raise Exception(f"OpenCode API调用失败: {str(e)}")
    except (KeyError, ValueError) as e:
        raise Exception(f"OpenCode API响应解析失败: {str(e)}")