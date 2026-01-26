"""
OpenRouter客户端单元测试

测试OpenRouter服务集成的各项功能，包括初始化、消息发送、对话历史管理等
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from openrouter import (
    OpenRouterClient,
    init_openrouter,
    get_response,
    reset_openrouter_client
)


class TestOpenRouterClientInitialization:
    """测试OpenRouter客户端初始化功能"""

    def test_default_initialization(self):
        """
        测试默认初始化
        验证环境变量正确加载
        """
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test_key",
            "OPENROUTER_API_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_DEFAULT_MODEL": "deepseek/deepseek-r1"
        }, clear=False):
            client = OpenRouterClient()
            
            assert client.api_key == "test_key"
            assert client.api_base_url == "https://openrouter.ai/api/v1"
            assert client.default_model == "deepseek/deepseek-r1"
            assert client.conversation_history == []

    def test_custom_initialization(self):
        """
        测试自定义参数初始化
        验证传入参数覆盖环境变量
        """
        client = OpenRouterClient(
            api_base_url="https://custom.api.v1",
            api_key="custom_key",
            default_model="custom/model"
        )
        
        assert client.api_key == "custom_key"
        assert client.api_base_url == "https://custom.api.v1"
        assert client.default_model == "custom/model"

    def test_missing_api_key_raises_error(self):
        """
        测试缺少API密钥时抛出异常
        验证参数验证功能
        """
        with patch.dict(os.environ, {}, clear=True):
            client = OpenRouterClient(api_key=None)
            
            with pytest.raises(ValueError, match="API Key未配置"):
                client.chat("test message")

    def test_headers_configuration(self):
        """
        测试请求头配置
        验证认证和引用信息正确设置
        """
        client = OpenRouterClient(api_key="test_key")
        
        headers = client.session.headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_key"
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers


class TestOpenRouterClientChat:
    """测试OpenRouter客户端聊天功能"""

    @pytest.fixture
    def mock_response(self):
        """
        创建模拟API响应
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "测试回复内容"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        return mock_resp

    def test_chat_success(self, mock_response):
        """
        测试正常聊天流程
        验证消息发送和响应解析
        """
        with patch('requests.Session.post', return_value=mock_response):
            client = OpenRouterClient(api_key="test_key")
            result = client.chat("你好")
            
            assert result == "测试回复内容"
            assert len(client.conversation_history) == 2

    def test_chat_with_custom_model(self):
        """
        测试指定模型聊天
        验证模型参数正确传递
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "回复内容"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp) as mock_post:
            client = OpenRouterClient(api_key="test_key")
            client.chat("测试消息", model="anthropic/claude-3-haiku")
            
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "anthropic/claude-3-haiku"

    def test_chat_uses_default_model(self):
        """
        测试默认模型使用
        验证环境变量中的默认模型被正确使用
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "回复内容"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp) as mock_post:
            client = OpenRouterClient(
                api_key="test_key",
                default_model="deepseek/deepseek-r1"
            )
            client.chat("测试消息")
            
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "deepseek/deepseek-r1"

    def test_chat_conversation_history_maintained(self):
        """
        测试对话历史维护
        验证历史消息正确累积
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "回复1"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp):
            client = OpenRouterClient(api_key="test_key")
            client.request_interval = 0.1
            
            client.chat("消息1")
            assert len(client.conversation_history) == 2
            
            import time
            time.sleep(0.15)
            
            client.chat("消息2")
            assert len(client.conversation_history) == 4

    def test_chat_history_limit(self):
        """
        测试对话历史限制
        验证超过限制时旧消息被清理
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "回复"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp):
            client = OpenRouterClient(api_key="test_key")
            client.conversation_history = [
                {"role": "user", "content": f"消息{i}"} 
                for i in range(18)
            ]
            
            client.chat("新消息")
            
            assert len(client.conversation_history) == 20

    def test_chat_timeout_handling(self):
        """
        测试超时异常处理
        验证超时错误正确转换
        """
        import requests
        
        with patch('requests.Session.post', side_effect=requests.exceptions.Timeout):
            client = OpenRouterClient(api_key="test_key")
            
            with pytest.raises(Exception, match="响应超时"):
                client.chat("测试消息")

    def test_chat_request_error_handling(self):
        """
        测试请求异常处理
        验证网络错误正确转换
        """
        import requests
        
        with patch('requests.Session.post', side_effect=requests.exceptions.RequestException("网络错误")):
            client = OpenRouterClient(api_key="test_key")
            
            with pytest.raises(Exception, match="请求失败"):
                client.chat("测试消息")

    def test_chat_response_format_error(self):
        """
        测试响应格式错误处理
        验证格式错误正确识别
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp):
            client = OpenRouterClient(api_key="test_key")
            
            with pytest.raises(Exception, match="响应格式错误"):
                client.chat("测试消息")


class TestOpenRouterClientHistory:
    """测试对话历史管理功能"""

    def test_clear_history(self):
        """
        测试清空历史
        验证历史记录被正确清空
        """
        client = OpenRouterClient(api_key="test_key")
        client.conversation_history = [
            {"role": "user", "content": "消息1"},
            {"role": "assistant", "content": "回复1"}
        ]
        
        client.clear_history()
        
        assert client.conversation_history == []

    def test_get_history_returns_copy(self):
        """
        测试获取历史副本
        验证返回的是独立副本
        """
        client = OpenRouterClient(api_key="test_key")
        client.conversation_history = [{"role": "user", "content": "消息"}]
        
        history = client.get_history()
        history.append({"role": "test", "content": "修改"})
        
        assert len(client.conversation_history) == 1
        assert len(history) == 2


class TestOpenRouterClientModels:
    """测试模型相关功能"""

    def test_get_available_models(self):
        """
        测试获取可用模型列表
        验证API调用和响应解析
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "model1", "name": "Model 1"},
                {"id": "model2", "name": "Model 2"}
            ]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.get', return_value=mock_resp):
            client = OpenRouterClient(api_key="test_key")
            models = client.get_available_models()
            
            assert len(models) == 2
            assert models[0]["id"] == "model1"

    def test_get_model_info(self):
        """
        测试获取指定模型信息
        验证单模型信息查询
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "id": "deepseek/deepseek-r1",
                "name": "DeepSeek R1",
                "pricing": {"input": "0.1", "output": "0.1"}
            }
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.get', return_value=mock_resp):
            client = OpenRouterClient(api_key="test_key")
            info = client.get_model_info("deepseek/deepseek-r1")
            
            assert info["id"] == "deepseek/deepseek-r1"


class TestOpenRouterRateLimit:
    """测试速率限制功能"""

    def test_rate_limit_enforced(self):
        """
        测试速率限制生效
        验证频繁请求被阻止
        """
        client = OpenRouterClient(api_key="test_key")
        client.request_interval = 1.0
        client.last_request_time = datetime.now()
        
        with pytest.raises(RuntimeError, match="请求过于频繁"):
            client._check_rate_limit()

    def test_rate_limit_allows_after_interval(self):
        """
        测试间隔后允许请求
        验证时间间隔后恢复正常
        """
        client = OpenRouterClient(api_key="test_key")
        client.request_interval = 0.1
        client.last_request_time = datetime.now()
        
        import time
        time.sleep(0.15)
        
        client._check_rate_limit()


class TestOpenRouterModuleFunctions:
    """测试模块级函数"""

    def test_init_openrouter_singleton(self):
        """
        测试初始化函数单例模式
        验证多次调用返回同一实例
        """
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            reset_openrouter_client()
            
            client1 = init_openrouter()
            client2 = init_openrouter()
            
            assert client1 is client2

    def test_init_openrouter_with_custom_params(self):
        """
        测试带参数初始化
        验证参数更新功能
        """
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "original_key"}):
            reset_openrouter_client()
            
            client = init_openrouter(api_key="new_key")
            
            assert client.api_key == "new_key"

    def test_get_response_function(self):
        """
        测试模块级get_response函数
        验证函数调用正确转发
        """
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "模块函数回复"
                }
            }]
        }
        mock_resp.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_resp):
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
                reset_openrouter_client()
                client = init_openrouter()
                result = get_response(client, "测试消息")
                
                assert result == "模块函数回复"

    def test_reset_openrouter_client(self):
        """
        测试重置客户端功能
        验证单例被正确重置
        """
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            client1 = init_openrouter()
            reset_openrouter_client()
            client2 = init_openrouter()
            
            assert client1 is not client2


class TestOpenRouterErrorMessages:
    """测试错误消息"""

    def test_timeout_error_message(self):
        """
        测试超时错误消息格式
        """
        import requests
        
        with patch('requests.Session.post', side_effect=requests.exceptions.Timeout):
            client = OpenRouterClient(api_key="test_key")
            
            try:
                client.chat("test")
            except Exception as e:
                assert "超时" in str(e)

    def test_request_error_message(self):
        """
        测试请求错误消息格式
        """
        import requests
        
        with patch('requests.Session.post', side_effect=requests.exceptions.RequestException("Connection refused")):
            client = OpenRouterClient(api_key="test_key")
            
            try:
                client.chat("test")
            except Exception as e:
                assert "请求失败" in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
