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
            # Extract text from segments
            text_segments = [seg.get('data', {}).get('text', '') for seg in self.message if seg.get('type') == 'text']
            return ''.join(text_segments)
        return ""
    time: int
    self_id: int
