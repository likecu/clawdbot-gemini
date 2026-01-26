"""
OpenCode 服务端主程序

提供 OpenAI 兼容的 API 接口，支持代码生成和执行
集成 Google Gemini 模型实现智能代码生成
"""

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any, List

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from src.executor import CodeExecutor

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化代码执行器
executor = CodeExecutor()


def authenticate_request(func):
    """
    认证装饰器

    验证请求中的 API 密钥是否有效
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({
                'error': {
                    'message': '缺少认证信息',
                    'type': 'authentication_error',
                    'code': 'missing_api_key'
                }
            }), 401

        try:
            # 解析 Bearer Token
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                raise ValueError('Invalid authorization format')

            api_key = parts[1]

            # 验证 API 密钥
            valid_key = os.getenv('OPENCODE_API_KEY')
            if not valid_key:
                logger.error('服务器未配置 API 密钥')
                return jsonify({
                    'error': {
                        'message': '服务器配置错误',
                        'type': 'server_error',
                        'code': 'config_error'
                    }
                }), 500

            if api_key != valid_key:
                logger.warning(f'无效的 API 密钥尝试访问')
                return jsonify({
                    'error': {
                        'message': '无效的 API 密钥',
                        'type': 'authentication_error',
                        'code': 'invalid_api_key'
                    }
                }), 401

        except Exception as e:
            logger.error(f'认证过程出错: {str(e)}')
            return jsonify({
                'error': {
                    'message': '认证失败',
                    'type': 'authentication_error',
                    'code': 'auth_error'
                }
            }), 401

        return func(*args, **kwargs)

    return wrapper


def validate_chat_request(data: Dict) -> Optional[str]:
    """
    验证聊天请求参数

    Args:
        data: 请求数据字典

    Returns:
        str: 验证失败时的错误消息，成功时返回 None
    """
    if not data:
        return '请求体不能为空'

    if 'messages' not in data:
        return '缺少 messages 参数'

    messages = data['messages']
    if not isinstance(messages, list) or len(messages) == 0:
        return 'messages 参数必须是非空列表'

    # 检查最后一条消息
    last_message = messages[-1]
    if not isinstance(last_message, dict):
        return '消息必须是对象格式'

    if 'content' not in last_message:
        return '消息缺少 content 字段'

    return None


@app.route('/v1/models', methods=['GET'])
def list_models():
    """
    列出可用模型

    Returns:
        JSON: 模型列表
    """
    return jsonify({
        'object': 'list',
        'data': [
            {
                'id': 'opencode-1.0',
                'object': 'model',
                'created': int(time.time()),
                'owned_by': 'opencode'
            },
            {
                'id': 'gemma-3-27b-it',
                'object': 'model',
                'created': int(time.time()),
                'owned_by': 'google'
            }
        ]
    })


@app.route('/v1/models/<model_id>', methods=['GET'])
def get_model(model_id: str):
    """
    获取特定模型信息

    Args:
        model_id: 模型 ID

    Returns:
        JSON: 模型信息
    """
    valid_models = ['opencode-1.0', 'gemma-3-27b-it']

    if model_id not in valid_models:
        return jsonify({
            'error': {
                'message': f'模型 {model_id} 未找到',
                'type': 'invalid_request_error',
                'code': 'model_not_found'
            }
        }), 404

    return jsonify({
        'id': model_id,
        'object': 'model',
        'created': int(time.time()),
        'owned_by': 'google' if 'gemma' in model_id else 'opencode'
    })


@app.route('/v1/chat/completions', methods=['POST'])
@authenticate_request
def create_chat_completion():
    """
    创建聊天完成请求

    这是 OpenAI 兼容的主要接口
    """
    try:
        # 验证请求
        error_msg = validate_chat_request(request.json)
        if error_msg:
            return jsonify({
                'error': {
                    'message': error_msg,
                    'type': 'invalid_request_error',
                    'code': 'invalid_request'
                }
            }), 400

        data = request.json
        model = data.get('model', 'opencode-1.0')
        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 1000)
        stream = data.get('stream', False)

        # 提取用户消息
        user_message = ''
        conversation_history = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            conversation_history.append({
                'role': role,
                'parts': [content] if isinstance(content, str) else content
            })

            if role == 'user':
                user_message = content if isinstance(content, str) else content[-1]

        if not user_message:
            return jsonify({
                'error': {
                    'message': '无法提取用户消息',
                    'type': 'invalid_request_error',
                    'code': 'no_user_message'
                }
            }), 400

        logger.info(f'收到聊天请求，模型: {model}, 消息长度: {len(user_message)}')

        # 检测是否需要执行代码
        should_execute, code_result = executor.analyze_and_execute(user_message)

        if should_execute and code_result:
            # 如果执行了代码，将结果包含在回复中
            assistant_response = f"我已经帮您执行了代码，结果如下：\n\n{code_result}"
        else:
            # 调用 Gemini 生成回复
            from llm import get_response_with_history

            gemini_model = executor.get_gemini_model()
            response_text = get_response_with_history(
                gemini_model,
                user_message,
                conversation_history[:-1]
            )
            assistant_response = response_text

        # 构建响应
        response_data = {
            'id': f'chatcmpl-{hashlib.md5(f"{datetime.now().isoformat()}".encode()).hexdigest()[:8]}',
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': model,
            'choices': [
                {
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': assistant_response
                    },
                    'finish_reason': 'stop'
                }
            ],
            'usage': {
                'prompt_tokens': len(user_message) // 4,
                'completion_tokens': len(assistant_response) // 4,
                'total_tokens': (len(user_message) + len(assistant_response)) // 4
            }
        }

        if stream:
            # 流式响应（简化版）
            return app.response_class(
                response=f"data: {json.dumps(response_data)}\n\ndata: [DONE]\n",
                mimetype='text/event-stream'
            )

        return jsonify(response_data)

    except Exception as e:
        logger.error(f'处理聊天请求时出错: {str(e)}', exc_info=True)
        return jsonify({
            'error': {
                'message': f'内部服务器错误: {str(e)}',
                'type': 'server_error',
                'code': 'internal_error'
            }
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    健康检查接口

    Returns:
        JSON: 服务状态
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


@app.route('/', methods=['GET'])
def index():
    """
    根路径欢迎信息

    Returns:
        JSON: 欢迎信息和服务状态
    """
    return jsonify({
        'name': 'OpenCode API Service',
        'version': '1.0.0',
        'description': '私有化 AI 编程助手服务',
        'endpoints': {
            'models': '/v1/models',
            'chat': '/v1/chat/completions',
            'health': '/health'
        }
    })


def main():
    """
    主函数，启动服务
    """
    host = os.getenv('OPENCODE_HOST', '0.0.0.0')
    port = int(os.getenv('OPENCODE_PORT', 8080))
    debug = os.getenv('OPENCODE_DEBUG', 'false').lower() == 'true'

    logger.info(f'启动 OpenCode 服务，监听 {host}:{port}')
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
