"""
飞书消息处理模块

处理接收到的飞书消息事件，实现消息分发和回复逻辑
"""

import json
from typing import Optional
from client import FeishuBot
from llm import get_response


class MessageHandler:
    """
    消息处理器类
    
    负责处理各种类型的飞书消息事件，并将消息转发给Gemini处理
    """
    
    def __init__(self, bot: FeishuBot, llm_model):
        """
        初始化消息处理器
        
        Args:
            bot: FeishuBot实例
            llm_model: 已初始化的Gemini模型
        """
        self.bot = bot
        self.llm_model = llm_model
    
    def handle_private_message(self, data: dict) -> None:
        """
        处理私聊消息
        
        Args:
            data: 飞书推送的消息事件数据
        """
        try:
            message = data.get("event", {}).get("message", {})
            message_id = message.get("message_id")
            chat_id = message.get("chat_id")
            sender_id = message.get("sender_id", {}).get("open_id")
            
            content_str = message.get("content", "{}")
            content = json.loads(content_str)
            user_text = content.get("text", "").strip()
            
            if not user_text:
                return
            
            self.bot.send_message(sender_id, "text", json.dumps({
                "text": "正在思考..."
            }))
            
            response_text = get_response(self.llm_model, user_text)
            
            self.bot.send_message(sender_id, "text", json.dumps({
                "text": response_text
            }))
            
        except Exception as e:
            error_msg = f"处理私聊消息时出错: {str(e)}"
            print(error_msg)
            if sender_id:
                self.bot.send_message(sender_id, "text", json.dumps({
                    "text": "抱歉，处理您消息时出现了问题，请稍后重试。"
                }))
    
    def handle_group_message(self, data: dict) -> None:
        """
        处理群聊中@机器人的消息
        
        Args:
            data: 飞书推送的消息事件数据
        """
        try:
            message = data.get("event", {}).get("message", {})
            message_id = message.get("message_id")
            chat_id = message.get("chat_id")
            
            content_str = message.get("content", "{}")
            content = json.loads(content_str)
            user_text = content.get("text", "").strip()
            
            if not user_text:
                return
            
            mentions = message.get("mentions", [])
            if not any(mention.get("id", {}).get("open_id") == self.get_bot_open_id() 
                      for mention in mentions):
                return
            
            for mention in mentions:
                mention_info = mention.get("name", "某用户")
                user_text = user_text.replace(f"@{mention_info}", "").strip()
            
            response_text = get_response(self.llm_model, user_text)
            
            self.bot.send_message(chat_id, "text", json.dumps({
                "text": response_text
            }))
            
        except Exception as e:
            error_msg = f"处理群聊消息时出错: {str(e)}"
            print(error_msg)
    
    def get_bot_open_id(self) -> str:
        """
        获取机器人的open_id
        
        Returns:
            str: 机器人的open_id
        """
        return ""
    
    def handle_message(self, event_type: str, data: dict) -> None:
        """
        消息分发入口
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if event_type == "im.message.message_v1":
            message = data.get("event", {}).get("message", {})
            chat_type = message.get("chat_type", "")
            
            if chat_type == "p2p":
                self.handle_private_message(data)
            elif chat_type == "group":
                self.handle_group_message(data)
        else:
            print(f"未处理的事件类型: {event_type}")


def create_message_handler(bot: FeishuBot, llm_model) -> MessageHandler:
    """
    创建消息处理器实例
    
    Args:
        bot: FeishuBot实例
        llm_model: Gemini模型实例
        
    Returns:
        MessageHandler实例
    """
    return MessageHandler(bot, llm_model)
