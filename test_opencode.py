"""
测试OpenCode API功能
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from dotenv import load_dotenv
from opencode import init_opencode, get_response

load_dotenv()

print("=" * 50)
print("测试OpenCode API功能")
print("=" * 50)

print("\n1. 初始化OpenCode...")
try:
    config = init_opencode()
    print(f"   初始化成功！base_url: {config['base_url']}")
except Exception as e:
    print(f"   初始化失败: {e}")
    sys.exit(1)

print("\n2. 测试发送消息...")
test_message = "你好，请介绍一下你自己"

try:
    response = get_response(config, test_message)
    print(f"   OpenCode回复: {response}")
    print("   测试成功！")
except Exception as e:
    print(f"   测试失败: {e}")

print("\n" + "=" * 50)
print("测试完成")
print("=" * 50)
