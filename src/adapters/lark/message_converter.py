"""
消息转换器模块

提供Markdown到飞书富文本格式的转换功能
"""

import re
import json
from typing import List, Dict, Any, Optional


class MessageConverter:
    """
    消息格式转换器类
    
    负责将Markdown格式转换为飞书富文本格式
    """
    
    def __init__(self):
        """
        初始化消息转换器
        """
        self.lang_map = {
            "py": "PYTHON",
            "python": "PYTHON",
            "js": "JAVASCRIPT",
            "javascript": "JAVASCRIPT",
            "ts": "TYPESCRIPT",
            "typescript": "TYPESCRIPT",
            "c++": "CPP",
            "cpp": "CPP",
            "c": "C",
            "java": "JAVA",
            "go": "GO",
            "golang": "GO",
            "rust": "RUST",
            "rs": "RUST",
            "sql": "SQL",
            "bash": "BASH",
            "shell": "SHELL",
            "json": "JSON",
            "xml": "XML",
            "html": "HTML",
            "css": "CSS",
            "markdown": "MARKDOWN",
            "md": "MARKDOWN",
        }
    
    def markdown_to_lark_post(self, text: str) -> Dict[str, Any]:
        """
        将Markdown文本转换为飞书post消息格式
        
        Args:
            text: Markdown格式的文本
            
        Returns:
            Dict: 飞书post消息格式的字典
            
        Raises:
            ValueError: 当文本为空时抛出
        """
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        
        # 使用正则表达式分割代码块
        pattern = r"```(\w*)\n([\s\S]*?)```"
        parts = []
        last_end = 0
        
        for match in re.finditer(pattern, text):
            # 添加代码块之前的文本
            if match.start() > last_end:
                plain_text = text[last_end:match.start()]
                if plain_text.strip():
                    parts.append(self._create_text_node(plain_text))
            
            # 解析代码块
            lang = match.group(1).lower()
            code = match.group(2)
            parts.append(self._create_code_block_node(code, lang))
            
            last_end = match.end()
        
        # 添加最后剩余的文本
        if last_end < len(text):
            remaining_text = text[last_end:]
            if remaining_text.strip():
                parts.append(self._create_text_node(remaining_text))
        
        # 如果没有代码块，整个文本作为普通文本处理
        if not parts:
            parts.append(self._create_text_node(text))
        
        # 构建飞书post消息结构
        post_content = {
            "zh_cn": {
                "title": "",
                "content": parts
            }
        }
        
        return {
            "msg_type": "post",
            "content": json.dumps(post_content)
        }
    
    def _create_text_node(self, text: str) -> Dict[str, Any]:
        """
        创建文本节点
        
        Args:
            text: 文本内容
            
        Returns:
            Dict: 文本节点字典
        """
        # 简单的Markdown处理
        processed_text = self._process_markdown_formatting(text)
        
        return {
            "tag": "text",
            "text": processed_text
        }
    
    def _create_code_block_node(self, code: str, language: str = "") -> Dict[str, Any]:
        """
        创建代码块节点
        
        Args:
            code: 代码内容
            language: 编程语言标识
            
        Returns:
            Dict: 代码块节点字典
        """
        # 映射语言标识到飞书标准格式
        standard_lang = self.lang_map.get(language, language.upper() if language else "TEXT")
        
        return {
            "tag": "code_block",
            "language": standard_lang,
            "text": code.rstrip()
        }
    
    def _process_markdown_formatting(self, text: str) -> str:
        """
        处理简单的Markdown格式
        
        Args:
            text: 原始文本
            
        Returns:
            str: 处理后的文本
        """
        # 处理粗体
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        
        # 处理斜体
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        
        # 处理行内代码
        text = re.sub(r"`([^`]+)`", r"\1", text)
        
        # 处理删除线
        text = re.sub(r"~~([^~]+)~~", r"\1", text)
        
        return text
    
    def extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """
        从文本中提取所有代码块
        
        Args:
            text: 包含代码块的文本
            
        Returns:
            List[Dict]: 代码块列表，每个包含language和code
        """
        pattern = r"```(\w*)\n([\s\S]*?)```"
        code_blocks = []
        
        for match in re.finditer(pattern, text):
            lang = match.group(1).lower()
            code = match.group(2).rstrip()
            code_blocks.append({
                "language": lang,
                "code": code
            })
        
        return code_blocks
    
    def split_text_and_code(self, text: str) -> List[Dict[str, Any]]:
        """
        将文本分割为文本段和代码段
        
        Args:
            text: 原始文本
            
        Returns:
            List[Dict]: 段落列表，每个包含type和content
        """
        pattern = r"```(\w*)\n([\s\S]*?)```"
        parts = []
        last_end = 0
        
        for match in re.finditer(pattern, text):
            if match.start() > last_end:
                plain_text = text[last_end:match.start()].strip()
                if plain_text:
                    parts.append({
                        "type": "text",
                        "content": plain_text
                    })
            
            lang = match.group(1).lower()
            code = match.group(2).rstrip()
            parts.append({
                "type": "code",
                "language": lang,
                "content": code
            })
            
            last_end = match.end()
        
        if last_end < len(text):
            remaining_text = text[last_end:].strip()
            if remaining_text:
                parts.append({
                    "type": "text",
                    "content": remaining_text
                })
        
        return parts


# 便捷函数
def markdown_to_feishu_post(text: str) -> Dict[str, Any]:
    """
    将Markdown转换为飞书post消息格式
    
    Args:
        text: Markdown文本
        
    Returns:
        Dict: 飞书消息内容字典
    """
    converter = MessageConverter()
    return converter.markdown_to_lark_post(text)


def format_code_block(code: str, language: str = "TEXT") -> Dict[str, Any]:
    """
    格式化代码块
    
    Args:
        code: 代码内容
        language: 编程语言
        
    Returns:
        Dict: 飞书代码块节点
    """
    converter = MessageConverter()
    return converter._create_code_block_node(code, language)
