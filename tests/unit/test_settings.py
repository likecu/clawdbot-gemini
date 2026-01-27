"""
配置模块单元测试
"""

import unittest
import sys
import os
from unittest.mock import patch

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"
))

from config.settings import Settings, get_settings, reload_settings


class TestSettings(unittest.TestCase):
    """
    配置测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        # 重置配置单例
        import config.settings
        config.settings._settings = None
    
    def tearDown(self):
        """
        测试后清理
        """
        # 重置配置单例
        import config.settings
        config.settings._settings = None
    
    @patch.dict(os.environ, {
        "FEISHU_APP_ID": "test_app_id",
        "FEISHU_APP_SECRET": "test_secret",
        "OPENROUTER_API_KEY": "test_api_key",
        "ACTIVE_MODEL": "openrouter"
    })
    def test_from_env(self):
        """
        测试从环境变量加载配置
        """
        settings = Settings.from_env()
        
        self.assertEqual(settings.lark_app_id, "test_app_id")
        self.assertEqual(settings.lark_app_secret, "test_secret")
        self.assertEqual(settings.openrouter_api_key, "test_api_key")
        self.assertEqual(settings.active_model, "openrouter")
    
    def test_default_values(self):
        """
        测试默认值
        """
        settings = Settings()
        
        self.assertEqual(settings.app_port, 8000)
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.redis_port, 6379)
        self.assertEqual(settings.session_max_history, 10)
    
    def test_validate_valid_config(self):
        """
        测试有效配置验证
        """
        settings = Settings(
            lark_app_id="test_id",
            lark_app_secret="test_secret",
            active_model="openrouter",
            openrouter_api_key="test_key"
        )
        
        is_valid, errors = settings.validate()
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_missing_lark_app_id(self):
        """
        测试缺失飞书App ID验证
        """
        settings = Settings(
            lark_app_secret="test_secret",
            active_model="openrouter",
            openrouter_api_key="test_key"
        )
        
        is_valid, errors = settings.validate()
        
        self.assertFalse(is_valid)
        self.assertTrue(any("App ID" in error for error in errors))
    
    def test_validate_missing_openrouter_key(self):
        """
        测试缺失OpenRouter密钥验证
        """
        settings = Settings(
            lark_app_id="test_id",
            lark_app_secret="test_secret",
            active_model="openrouter"
        )
        
        is_valid, errors = settings.validate()
        
        self.assertFalse(is_valid)
        self.assertTrue(any("OpenRouter" in error for error in errors))
    
    def test_validate_missing_deepseek_key(self):
        """
        测试缺失DeepSeek密钥验证
        """
        settings = Settings(
            lark_app_id="test_id",
            lark_app_secret="test_secret",
            active_model="deepseek"
        )
        
        is_valid, errors = settings.validate()
        
        self.assertFalse(is_valid)
        self.assertTrue(any("DeepSeek" in error for error in errors))


class TestSettingsSingleton(unittest.TestCase):
    """
    配置单例测试类
    """
    
    def tearDown(self):
        """
        测试后清理
        """
        import config.settings
        config.settings._settings = None
    
    def test_get_settings(self):
        """
        测试获取配置单例
        """
        with patch.dict(os.environ, {
            "FEISHU_APP_ID": "singleton_id",
            "FEISHU_APP_SECRET": "singleton_secret",
            "OPENROUTER_API_KEY": "singleton_key",
            "ACTIVE_MODEL": "openrouter"
        }):
            settings1 = get_settings()
            settings2 = get_settings()
            
            self.assertIs(settings1, settings2)
    
    def test_reload_settings(self):
        """
        测试重新加载配置
        """
        with patch.dict(os.environ, {
            "FEISHU_APP_ID": "original_id",
            "FEISHU_APP_SECRET": "original_secret"
        }):
            settings1 = get_settings()
            original_id = settings1.lark_app_id
            
            # 修改环境变量
            os.environ["FEISHU_APP_ID"] = "new_id"
            
            # 重新加载
            settings2 = reload_settings()
            
            self.assertEqual(settings2.lark_app_id, "new_id")


class TestSettingsModelConfiguration(unittest.TestCase):
    """
    模型配置测试类
    """
    
    def test_openrouter_default_model(self):
        """
        测试OpenRouter默认模型
        """
        settings = Settings()
        
        self.assertEqual(settings.openrouter_default_model, "tngtech/deepseek-r1t2-chimera:free")
        self.assertEqual(settings.openrouter_api_base_url, "https://openrouter.ai/api/v1")
    
    def test_deepseek_default_model(self):
        """
        测试DeepSeek默认模型
        """
        settings = Settings()
        
        self.assertEqual(settings.deepseek_model, "deepseek-chat")
        self.assertEqual(settings.deepseek_api_base_url, "https://api.deepseek.com")


if __name__ == "__main__":
    unittest.main()
