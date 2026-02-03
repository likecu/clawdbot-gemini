from pydantic import BaseModel
from typing import Optional, List, Union

class MessageRequest(BaseModel):
    message_type: str = "private"  # private or group
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    message: str
    auto_escape: bool = False

class Sender(BaseModel):
    user_id: int
    nickname: str
    card: Optional[str] = None
    role: Optional[str] = None

class QQMessage(BaseModel):
    post_type: str
    message_type: Optional[str] = None
    sub_type: Optional[str] = None
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    message: Optional[Union[str, List[dict]]] = None
    raw_message: Optional[str] = None
    sender: Optional[Sender] = None

    @property
    def text(self) -> str:
        if self.raw_message:
            return self.raw_message
        if isinstance(self.message, str):
            return self.message
        if isinstance(self.message, list):
            # 重构消息串，包含文本和CQ码
            parts = []
            for seg in self.message:
                seg_type = seg.get('type')
                data = seg.get('data', {})
                if seg_type == 'text':
                    parts.append(data.get('text', ''))
                elif seg_type:
                    # 将其他类型转回 CQ 码格式
                    params = ','.join([f"{k}={v}" for k, v in data.items()])
                    parts.append(f"[CQ:{seg_type},{params}]")
            return ''.join(parts)
        return ""
    time: int
    self_id: int
