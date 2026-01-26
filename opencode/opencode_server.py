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


def analyze_intent(user_message: str) -> Dict[str, Any]:
    """
    分析用户意图，判断是否需要获取系统数据

    Args:
        user_message: 用户消息

    Returns:
        Dict: 意图分析结果
    """
    message_lower = user_message.lower()

    intent_patterns = {
        'system_info': [
            '内存', 'memory', 'cpu', '磁盘', '硬盘', '空间',
            '系统信息', 'system info', 'system information',
            '使用率', 'usage', 'utilization',
            '负载', 'load average', 'load',
            '进程', 'process', '进程列表',
            '网络', 'network', '连接数',
            '端口', 'port', '监听',
        ],
        'file_operation': [
            '文件', 'file', '目录', 'folder', '列出',
            '读取', 'read', '查看', 'cat', 'type',
            '写入', 'write', '创建', 'create', '删除', 'delete',
            '大小', 'size', '权限', 'permission', 'chmod',
            '搜索', 'search', 'find', 'grep',
        ],
        'environment': [
            '环境变量', 'environment', 'env', '变量',
            'python', 'pip', '包', 'package', '依赖', 'dependency',
            '版本', 'version', 'python version',
            'docker', '容器', 'container',
        ],
        'network_info': [
            'curl', 'wget', 'ping', 'dns', 'ip 地址',
            '端口', 'port', '连接', 'connection',
            '请求', 'request', 'http', 'api',
        ],
        'computation': [
            '计算', 'calculate', 'compute', '求和', 'sum',
            '排序', 'sort', '搜索', 'search',
            '斐波那契', 'fibonacci', '阶乘', 'factorial',
            '素数', 'prime', '统计', 'statistics',
        ],
    }

    detected_intents = []

    for intent, patterns in intent_patterns.items():
        for pattern in patterns:
            if pattern in message_lower:
                detected_intents.append(intent)
                break

    need_execution = len(detected_intents) > 0 or any(keyword in message_lower for keyword in [
        '执行', '运行', 'run', 'execute', '帮我', '请',
        '当前', '现在', 'today', '当前日期', '当前时间',
    ])

    return {
        'intents': detected_intents,
        'need_execution': need_execution,
        'message_lower': message_lower
    }


def generate_code_for_intent(intent_info: Dict[str, Any]) -> Optional[str]:
    """
    根据意图生成代码

    Args:
        intent_info: 意图分析结果

    Returns:
        str: 生成的代码，如果没有匹配返回 None
    """
    message = intent_info['message_lower']
    intents = intent_info['intents']

    code_templates = {
        'system_info': {
            'memory': '''import psutil
memory = psutil.virtual_memory()
print(f"内存使用情况:")
print(f"  总内存: {memory.total / (1024**3):.2f} GB")
print(f"  已用内存: {memory.used / (1024**3):.2f} GB")
print(f"  可用内存: {memory.available / (1024**3):.2f} GB")
print(f"  使用率: {memory.percent:.1f}%")
''',
            'cpu': '''import psutil
print(f"CPU 使用情况:")
print(f"  CPU 逻辑核心数: {psutil.cpu_count()}")
print(f"  CPU 物理核心数: {psutil.cpu_count(logical=False)}")
print(f"  当前 CPU 使用率: {psutil.cpu_percent(interval=1)}%")
print(f"  各核心使用率: {psutil.cpu_percent(interval=1, percpu=True)}")
print(f"  系统负载 (1/5/15分钟): {os.getloadavg()}")
''',
            'disk': '''import psutil
print(f"磁盘使用情况:")
for part in psutil.disk_partitions():
    usage = psutil.disk_usage(part.mountpoint)
    print(f"  {part.mountpoint}:")
    print(f"    总空间: {usage.total / (1024**3):.2f} GB")
    print(f"    已用: {usage.used / (1024**3):.2f} GB")
    print(f"    可用: {usage.free / (1024**3):.2f} GB")
    print(f"    使用率: {usage.percent:.1f}%")
''',
            'process': '''import psutil
print(f"系统进程信息:")
print(f"  进程总数: {len(psutil.pids())}")
print(f"  前5个进程:")
for pid in sorted(psutil.pids())[:5]:
    try:
        p = psutil.Process(pid)
        print(f"    PID {pid}: {p.name()} - CPU: {p.cpu_percent():.1f}% - Memory: {p.memory_info().rss / (1024**2):.1f} MB")
    except:
        pass
''',
            'network': '''import psutil
print(f"网络连接信息:")
connections = psutil.net_connections()
print(f"  总连接数: {len(connections)}")
established = [c for c in connections if c.status == 'ESTABLISHED']
print(f"  ESTABLISHED 连接: {len(established)}")
print(f"  各状态统计:")
for status in ['ESTABLISHED', 'TIME_WAIT', 'CLOSE_WAIT', 'LISTEN']:
    count = len([c for c in connections if c.status == status])
    print(f"    {status}: {count}")
''',
        },
        'file_operation': {
            'list_files': '''import os
path = '.'
print(f"目录 {path} 内容:")
for item in sorted(os.listdir(path)):
    full_path = os.path.join(path, item)
    if os.path.isdir(full_path):
        print(f"  [DIR]  {item}")
    else:
        size = os.path.getsize(full_path)
        print(f"  [FILE] {item} ({size} bytes)")
''',
            'file_size': '''import os
import glob
print("查找大文件:")
for pattern in ['**/*.py', '**/*.log', '**/*.tmp']:
    for f in glob.glob(pattern, recursive=True):
        size = os.path.getsize(f)
        if size > 1024 * 1024:
            print(f"  {f}: {size / (1024**2):.2f} MB")
''',
        },
        'environment': {
            'python_info': '''import sys
import platform
print(f"Python 环境信息:")
print(f"  Python 版本: {sys.version}")
print(f"  可执行文件: {sys.executable}")
print(f"  编码: {sys.getdefaultencoding()}")
print(f"  平台: {platform.platform()}")
print(f"  架构: {platform.machine()}")
''',
            'pip_list': '''import subprocess
result = subprocess.run(['pip', 'list', '--format=json'], capture_output=True, text=True)
packages = json.loads(result.stdout)
print(f"已安装的包数量: {len(packages)}")
print(f"前10个包:")
for p in sorted(packages, key=lambda x: x['name'].lower())[:10]:
    print(f"  {p['name']}=={p['version']}")
''',
        },
        'network_info': {
            'curl': '''import subprocess
result = subprocess.run(['curl', '-s', 'ifconfig.me'], capture_output=True, text=True)
print(f"公网 IP: {result.stdout.strip()}")
''',
        },
        'computation': {
            'fibonacci': '''def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

n = 20
print(f"斐波那契数列前 {n} 项:")
result = [fibonacci(i) for i in range(n)]
print(result)
print(f"第 {n} 项: {fibonacci(n)}")
''',
            'prime': '''def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

primes = [n for n in range(2, 101) if is_prime(n)]
print(f"2-100 范围内的素数 ({len(primes)} 个):")
print(primes)
''',
        }
    }

    import os
    os.environ['PYTHONUNBUFFERED'] = '1'

    if 'system_info' in intents:
        if 'memory' in message or '内存' in message:
            return code_templates['system_info']['memory']
        elif 'cpu' in message or 'cpu' in message:
            return code_templates['system_info']['cpu']
        elif '磁盘' in message or '硬盘' in message or 'disk' in message:
            return code_templates['system_info']['disk']
        elif '进程' in message or 'process' in message:
            return code_templates['system_info']['process']
        elif '网络' in message or 'network' in message:
            return code_templates['system_info']['network']
        else:
            return code_templates['system_info']['memory']

    if 'file_operation' in intents:
        if '列出' in message or 'list' in message or '目录' in message:
            return code_templates['file_operation']['list_files']
        elif '大小' in message or 'size' in message or '大文件' in message:
            return code_templates['file_operation']['file_size']

    if 'environment' in intents:
        if 'python' in message or '版本' in message:
            return code_templates['environment']['python_info']
        elif 'pip' in message or '包' in message:
            return code_templates['environment']['pip_list']

    if 'network_info' in intents:
        if 'ip' in message:
            return code_templates['network_info']['curl']

    if 'computation' in intents:
        if '斐波那契' in message or 'fibonacci' in message:
            return code_templates['computation']['fibonacci']
        elif '素数' in message or 'prime' in message:
            return code_templates['computation']['prime']

    if any(kw in message for kw in ['当前时间', '现在时间', 'today', 'time now', '几点']):
        return '''from datetime import datetime
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")
print(f"当前时间戳: {datetime.now().timestamp()}")
'''

    if any(kw in message for kw in ['当前日期', 'today', 'date now']):
        return '''from datetime import datetime
print(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")
print(f"当前时间: {datetime.now().strftime('%H:%M:%S')}")
print(f"今天是星期: {['一', '二', '三', '四', '五', '六', '日'][datetime.now().weekday()]}")
'''

    return None


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

        intent_info = analyze_intent(user_message)
        logger.info(f'意图分析: {intent_info}')

        generated_code = None

        if intent_info['need_execution']:
            generated_code = generate_code_for_intent(intent_info)

            if generated_code:
                logger.info(f'自动生成代码执行...')
                code_result = execute_python_code(generated_code)
                logger.info(f'代码执行结果: {code_result[:200]}...')

                if code_result.strip() and not code_result.startswith('错误'):
                    assistant_response = f"执行结果：\n{code_result}"
                else:
                    assistant_response = code_result if code_result else "代码执行完成，无输出"
            else:
                should_execute, code_result = executor.analyze_and_execute(user_message)
                if should_execute and code_result:
                    assistant_response = f"代码执行结果：\n{code_result}"
                else:
                    intent_info['need_execution'] = False

        if not intent_info['need_execution'] or not generated_code:
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
