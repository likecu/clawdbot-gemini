"""
应用配置模块

提供全局配置管理
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """
    应用配置类
    
    集中管理所有应用配置项
    """
    
    # 飞书配置
    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_encrypt_key: str = ""
    lark_verification_token: str = ""
    
    # OpenRouter配置
    openrouter_api_key: str = ""
    openrouter_api_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "tngtech/deepseek-r1t2-chimera:free"
    
    # DeepSeek配置
    deepseek_api_key: str = ""
    deepseek_api_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    
    # 模型选择
    active_model: str = "openrouter"  # openrouter 或 deepseek
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    
    # 会话配置
    session_max_history: int = 10
    
    @classmethod
    def from_env(cls) -> 'Settings':
        """
        从环境变量加载配置
        
        Returns:
            Settings: 配置实例
        """
        return cls(
            lark_app_id=os.getenv("FEISHU_APP_ID", ""),
            lark_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            lark_encrypt_key=os.getenv("FEISHU_ENCRYPT_KEY", ""),
            lark_verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
            
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_api_base_url=os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1"),
            openrouter_default_model=os.getenv("OPENROUTER_DEFAULT_MODEL", "tngtech/deepseek-r1t2-chimera:free"),
            
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_api_base_url=os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            
            active_model=os.getenv("ACTIVE_MODEL", "openrouter"),
            
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", 6379)),
            redis_db=int(os.getenv("REDIS_DB", 0)),
            redis_password=os.getenv("REDIS_PASSWORD"),
            
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", 8000)),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            
            session_max_history=int(os.getenv("SESSION_MAX_HISTORY", 10))
        )
    
    def validate(self) -> tuple:
        """
        验证配置有效性
        
        Returns:
            tuple: (是否有效, 错误消息列表)
        """
        errors = []
        
        if not self.lark_app_id:
            errors.append("飞书App ID未配置")
        if not self.lark_app_secret:
            errors.append("飞书App Secret未配置")
        
        if self.active_model == "openrouter" and not self.openrouter_api_key:
            errors.append("OpenRouter API密钥未配置")
        elif self.active_model == "deepseek" and not self.deepseek_api_key:
            errors.append("DeepSeek API密钥未配置")
        
        return (len(errors) == 0, errors)


# 全局配置单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    获取全局配置单例
    
    Returns:
        Settings: 配置实例
    """
    global _settings
    
    if _settings is None:
        _settings = Settings.from_env()
    
    return _settings


def reload_settings() -> Settings:
    """
    重新加载配置
    
    Returns:
        Settings: 配置实例
    """
    global _settings
    _settings = Settings.from_env()
    return _settings
