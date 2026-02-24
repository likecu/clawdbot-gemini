
import os
import logging
from typing import Optional

class MemoryBank:
    """
    用户长期记忆库
    
    负责读取和管理用户专属的长期记忆文件
    """
    
    def __init__(self, data_dir: str = "/app/memories"):
        """
        初始化记忆库
        
        Args:
            data_dir: 记忆文件存储目录
        """
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)
        
        # 确保目录存在
        try:
            os.makedirs(data_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"无法创建记忆目录 {data_dir}: {e}")

    def get_user_memory(self, user_id: str) -> str:
        """
        获取用户的长期记忆
        
        Args:
            user_id: 用户ID (e.g. "qq:254067848")
            
        Returns:
            str: 记忆内容，如果不存在则返回空字符串
        """
        # 安全处理文件名，将非法字符替换为下划线
        safe_uid = user_id.replace(":", "_").replace("/", "_")
        file_path = os.path.join(self.data_dir, f"{safe_uid}.md")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    self.logger.info(f"已加载用户记忆: {safe_uid} (长度: {len(content)})")
                    return content
            except Exception as e:
                self.logger.error(f"读取用户记忆失败 {file_path}: {e}")
        
        return ""

    def save_user_memory(self, user_id: str, content: str) -> bool:
        """
        保存用户记忆（覆盖）
        
        Args:
            user_id: 用户ID
            content: 记忆内容
            
        Returns:
            bool: 是否保存成功
        """
        safe_uid = user_id.replace(":", "_").replace("/", "_")
        file_path = os.path.join(self.data_dir, f"{safe_uid}.md")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            self.logger.error(f"保存用户记忆失败 {file_path}: {e}")
            return False

    def delete_user_memory(self, user_id: str) -> bool:
        """
        删除用户记忆文件
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否删除成功
        """
        safe_uid = user_id.replace(":", "_").replace("/", "_")
        file_path = os.path.join(self.data_dir, f"{safe_uid}.md")
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.logger.info(f"已删除用户记忆文件: {file_path}")
                return True
            except Exception as e:
                self.logger.error(f"删除用户记忆失败 {file_path}: {e}")
                return False
        return True

# 单例实例
_memory_bank: Optional[MemoryBank] = None

def create_memory_bank(data_dir: str = "/app/memories") -> MemoryBank:
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = MemoryBank(data_dir)
    return _memory_bank

def get_memory_bank() -> MemoryBank:
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = create_memory_bank()
    return _memory_bank
