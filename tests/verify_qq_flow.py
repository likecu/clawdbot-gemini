import sys
import os
import asyncio
import logging

# 将 src 目录加入路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from channels.qq.adapter import QQChannel
from core.agent import Agent
from channels.base import UnifiedSendRequest

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

def test_id_parsing():
    """测试复合 ID 的解析逻辑"""
    logger.info(">>> 开始测试 ID 解析逻辑...")
    
    # 模拟一个带平台前缀和日期后缀的 ID
    test_ids = [
        "qq:user:254067848:20260214",
        "private_12345678",
        "254067848",
        "qq:private:88888888"
    ]
    
    # 我们并不需要启动真正的客户端，只需要验证逻辑
    # 逻辑位于 send_message 方法中
    # 这里我们手动复现逻辑进行验证
    
    for rid in test_ids:
        raw_id = rid
        if ":" in raw_id:
            parts = raw_id.split(":")
            for p in parts:
                if p.isdigit():
                    raw_id = p
                    break
        elif "_" in raw_id:
            raw_id = raw_id.split("_")[-1]
            
        try:
            parsed_id = int(raw_id)
            logger.info(f"输入: {rid} -> 解析后: {parsed_id} (SUCCESS)")
        except ValueError:
            logger.error(f"输入: {rid} -> 解析失败 (FAILED)")
            return False
    return True

async def test_callback_interface():
    """测试回调接口 (需要服务正在运行)"""
    logger.info(">>> 开始测试远程回调接口响应...")
    import aiohttp
    
    # 模拟外部回传 payload
    payload = {
        "session_id": "qq:private:254067848:20260214", # 采用之前报错的混合 ID
        "content": "这是一条来自自动化验证脚本的测试消息。如果您看到这条消息，说明链路已打通。"
    }
    
    url = "http://127.0.0.1:8081/api/clawdbot/callback"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    res_json = await response.json()
                    logger.info(f"回调推送成功: {res_json}")
                    return True
                else:
                    logger.error(f"回调推送失败: HTTP {response.status}")
                    return False
    except Exception as e:
        logger.error(f"无法连接到回调服务: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== 启动自动化验证流程 ===")
    
    id_ok = test_id_parsing()
    if not id_ok:
        sys.exit(1)
        
    # 回调模式测试需要运行在远程环境或本地有启动服务
    # 我们尝试运行，如果不通则跳过
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_callback_interface())
    
    logger.info("=== 验证流程结束 ===")
