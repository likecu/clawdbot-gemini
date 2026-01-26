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
import subprocess
import re
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

    Args:
        func: 被装饰的函数

    Returns:
        wrapper: 装饰后的函数
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
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                raise ValueError('Invalid authorization format')

            api_key = parts[1]
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

    last_message = messages[-1]
    if not isinstance(last_message, dict):
        return '消息必须是对象格式'

    if 'content' not in last_message:
        return '消息缺少 content 字段'

    return None


def analyze_intent_with_ai(user_message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
    """
    使用 AI 分析用户意图，返回 JSON 格式的结果

    Args:
        user_message: 用户消息
        conversation_history: 对话历史（可选）

    Returns:
        Dict: 意图分析结果，包含 intents、need_execution、generated_code、response_text
    """
    gemini_model = executor.get_gemini_model()

    history_text = ""
    if conversation_history:
        history_text = "\n对话历史:\n" + "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('parts', [msg.get('content', '')])[-1]}"
            for msg in conversation_history[-5:]
        ])

    system_prompt = """你是一个意图分析助手。用户会发送消息，你需要进行意图分析并生成代码。

## 分析要求
1. 分析用户消息，判断是否需要获取系统数据或执行代码
2. 如果需要执行代码，生成 Python 代码来完成任务
3. 如果不需要执行代码，准备一个友好的回复

## 意图类型
- system_info: 系统信息（内存、CPU、磁盘、网络、进程等）
- file_operation: 文件操作（列出、读取、创建、删除文件等）
- environment: 环境信息（Python版本、环境变量、Docker等）
- network_info: 网络操作（curl、ping、API请求等）
- computation: 计算任务（排序、搜索、数学计算等）
- general_chat: 一般对话（不需要执行代码）

## 输出格式
请返回严格的 JSON 对象（不要包含任何其他文本）：

```json
{
    "intents": ["system_info"],
    "need_execution": true,
    "generated_code": "import psutil\nprint('内存使用情况:')\nmemory = psutil.virtual_memory()\nprint(f'使用率: {memory.percent}%')",
    "response_text": null
}
```

或者（不需要执行代码时）：

```json
{
    "intents": ["general_chat"],
    "need_execution": false,
    "generated_code": null,
    "response_text": "你好！我是 Clawdbot，一个 AI 编程助手。我可以帮助你完成编程任务、获取系统信息等。"
}
```

## 代码要求
1. 使用 Python 3
2. 代码必须完整可运行
3. 使用 print 输出结果
4. 不要使用 input() 或 interactive 功能
5. 执行时间限制 30 秒
6. 导入必要的模块（psutil、os、subprocess 等）

当前时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + history_text

    try:
        response = gemini_model.generate_content(
            f"{system_prompt}\n\n用户消息: {user_message}"
        )
        response_text = response.text.strip()

        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response_text

        result = json.loads(json_str)

        if not isinstance(result, dict):
            raise ValueError("返回结果不是 JSON 对象")

        required_keys = ['intents', 'need_execution']
        for key in required_keys:
            if key not in result:
                raise ValueError(f"返回结果缺少必要字段: {key}")

        logger.info(f'AI 意图分析结果: {result}')
        return result

    except Exception as e:
        logger.error(f'AI 意图分析失败: {str(e)}，使用默认处理')
        return {
            'intents': [],
            'need_execution': False,
            'generated_code': None,
            'response_text': None
        }


def execute_python_code(code: str) -> str:
    """
    执行 Python 代码并返回结果

    Args:
        code: Python 代码

    Returns:
        str: 执行结果
    """
    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )

        output = result.stdout
        if result.stderr:
            output += f"STDERR: {result.stderr}"

        return output if output.strip() else "(代码执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return "错误: 代码执行超时 (30秒)"
    except Exception as e:
        return f"错误: {str(e)}"


@app.route('/v1/models', methods=['GET'])
def list_models():
    """
    列出可用模型
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
    """
    try:
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

        intent_result = analyze_intent_with_ai(user_message, conversation_history)
        logger.info(f'AI 意图分析结果: {intent_result}')

        assistant_response = ""

        if intent_result.get('need_execution') and intent_result.get('generated_code'):
            generated_code = intent_result['generated_code']
            logger.info(f'执行 AI 生成的代码...')
            code_result = execute_python_code(generated_code)
            logger.info(f'代码执行结果: {code_result[:200]}...')

            if code_result.strip() and not code_result.startswith('错误'):
                assistant_response = f"执行结果：\n{code_result}"
            else:
                assistant_response = code_result if code_result else "代码执行完成，无输出"

        elif intent_result.get('response_text'):
            assistant_response = intent_result['response_text']

        else:
            from src.llm import get_response_with_history

            gemini_model = executor.get_gemini_model()
            response_text = get_response_with_history(
                gemini_model,
                user_message,
                conversation_history[:-1]
            )
            assistant_response = response_text

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
