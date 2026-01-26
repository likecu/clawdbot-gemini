"""
工具函数模块

提供通用的辅助功能，包括日志配置、环境变量加载等
"""

import os
import json
import logging
from typing import Any, Dict, Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    配置日志系统
    
    Args:
        level: 日志级别，默认为INFO
        
    Returns:
        配置好的logger实例
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def getenv(key: str, default: Any = None) -> Any:
    """
    安全获取环境变量
    
    Args:
        key: 环境变量名称
        default: 默认值，当环境变量不存在时返回
        
    Returns:
        环境变量值或默认值
    """
    return os.getenv(key, default)


def load_json_config(config_str: str) -> Dict:
    """
    加载JSON配置字符串
    
    Args:
        config_str: JSON格式的字符串
        
    Returns:
        dict: 解析后的字典
        
    Raises:
        json.JSONDecodeError: 当JSON解析失败时抛出
    """
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败: {str(e)}")


def truncate_text(text: str, max_length: int = 2000) -> str:
    """
    截断文本内容
    
    Args:
        text: 原始文本
        max_length: 最大长度
        
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_error_response(error_msg: str) -> str:
    """
    格式化错误响应
    
    Args:
        error_msg: 错误消息
        
    Returns:
        str: 格式化的错误响应
    """
    return f"抱歉，发生了错误：{error_msg}\n\n请稍后重试或联系管理员。"
