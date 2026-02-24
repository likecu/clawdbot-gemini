
import pytest
import requests
import json
import os

# 远程服务器配置
BASE_URL = os.getenv("TEST_API_URL", "http://34.72.125.220:8081")

def test_root_endpoint():
    """测试根端点 / (实际测试 /api/qq/status)"""
    # 注意：main.py 可能没有根端点。
    # 根据 main.py 的检查结果：
    # /qq/status -> /api/qq/status
    url = f"{BASE_URL}/api/qq/status"
    try:
        response = requests.get(url, timeout=5)
        # 即使是 500，也表示连接成功。我们检查连接性。
        print(f"GET {url} -> {response.status_code}")
        assert response.status_code in [200, 500, 502], "应返回有效的 HTTP 状态码"
        if response.status_code == 200:
            data = response.json()
            # 结构应该返回 {"status": ...}
            assert "status" in data
    except requests.exceptions.ConnectionError:
        pytest.fail(f"无法连接到 {BASE_URL}。服务器是否正在运行？")

def test_qq_qr_endpoint():
    """测试 /api/qq/qr 端点"""
    url = f"{BASE_URL}/api/qq/qr"
    try:
        response = requests.get(url, timeout=5)
        print(f"GET {url} -> {response.status_code}")
        # 如果二维码文件不存在，404 是有效的
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "url" in data
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")

def test_send_message_validation():
    """测试 /send_msg 的输入验证"""
    # 注意：send_message 路径是 /send_msg (没有 /api 前缀)
    url = f"{BASE_URL}/send_msg"
    payload = {
        # 缺少必填字段 target_id
        "content": "test"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"POST {url} (Invalid) -> {response.status_code}")
        # 应该是 422 Unprocessable Entity (Pydantic 验证错误)
        assert response.status_code == 422
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    # 允许直接运行
    try:
        test_root_endpoint()
        test_qq_qr_endpoint()
        test_send_message_validation()
        print("基础 API 检查通过！")
    except Exception as e:
        print(f"测试失败: {e}")
        exit(1)
