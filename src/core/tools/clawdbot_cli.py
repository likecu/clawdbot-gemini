"""
Clawdbot CLI 工具适配器

负责异步调用本地 clawsbot 命令行工具，并将结果通过回调传回。
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ClawdbotCliTool:
    """
    Clawdbot 命令行工具封装
    """
    
    def __init__(self):
        pass

    async def run_async(self, task_prompt: str, session_id: str, callback: Callable[[str, str], None]) -> None:
        """
        异步运行 clawdbot 命令
        
        Args:
            task_prompt:以此Prompt运行clawdbot
            session_id: 会话ID，用于回调时识别用户
            callback: 任务完成后的回调函数，签名 func(session_id, result_content)
        """
        # 启动后台任务，避免阻塞当前协程
        asyncio.create_task(self._execute_subprocess(task_prompt, session_id, callback))
        logger.info(f"已启动后台 Clawdbot 任务: {task_prompt[:50]}... (Session: {session_id})")

    async def _execute_subprocess(self, task_prompt: str, session_id: str, callback: Callable[[str, str], None]) -> None:
        """
        执行子进程的具体逻辑
        """
        try:
            logger.info(f"开始执行 Clawdbot CLI: {task_prompt}")
            
            # 构造命令: clawdbot "prompt"
            # 注意：需确保 clawdbot 在 PATH 中，或者使用绝对路径
            # 这里为了安全和正确性，我们使用 shell=False 并传列表
            cmd = ["clawdbot", task_prompt]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()
            
            if process.returncode == 0:
                logger.info(f"Clawdbot 任务执行成功 (PID: {process.pid})")
                result_msg = f"[Clawdbot 任务完成]\n\n{stdout_str}"
                
                # 如果有 stderr，也记录或附带（视情况而定，CLI工具有时会把非错误日志输出到stderr）
                if stderr_str:
                    logger.warning(f"Clawdbot stderr: {stderr_str}")
            else:
                logger.error(f"Clawdbot 任务失败 (Code: {process.returncode})\nStderr: {stderr_str}")
                result_msg = f"[Clawdbot 任务失败]\n\n错误代码: {process.returncode}\n错误信息:\n{stderr_str}"
            
            # 执行回调
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, result_msg)
                else:
                    # 如果回调不是异步的（虽然在设计中应该是异步的），我们需要小心处理
                    # 这里假设 main.py 传进来的是 async
                    logger.warning("Callback is not a coroutine, executing synchronously (might block)")
                    callback(session_id, result_msg)
                    
        except FileNotFoundError:
            err_msg = "[系统错误] 找不到 `clawdbot` 命令，请检查环境变量或安装情况。"
            logger.error(err_msg)
            if callback:
                 if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, err_msg)
        except Exception as e:
            err_msg = f"[系统错误] 执行 Clawdbot 时发生异常: {str(e)}"
            logger.error(err_msg, exc_info=True)
            if callback:
                 if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, err_msg)
