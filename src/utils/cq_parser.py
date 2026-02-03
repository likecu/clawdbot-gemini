"""
CQ码解析工具

解析QQ消息中的CQ码格式，提取图片URL、表情等信息
"""

import re
from typing import List, Dict, Any, Optional


def parse_cq_code(text: str) -> Dict[str, Any]:
    """
    解析包含CQ码的文本
    
    Args:
        text: 包含CQ码的文本，如 [CQ:image,file=xxx.png,url=https://...]
        
    Returns:
        Dict: 解析结果，包含以下字段：
            - text: 纯文本部分
            - images: 图片URL列表
            - has_image: 是否包含图片
            - raw_cq_codes: 原始CQ码列表
    
    Example:
        >>> result = parse_cq_code('[CQ:image,url=https://example.com/1.jpg]看图')
        >>> result['text']
        '看图'
        >>> result['images']
        ['https://example.com/1.jpg']
    """
    # 提取所有CQ码
    cq_pattern = r'\[CQ:([^,\]]+)(?:,([^\]]+))?\]'
    matches = re.findall(cq_pattern, text)
    
    images = []
    raw_cq_codes = []
    
    for match in matches:
        cq_type = match[0]
        cq_params_str = match[1]  if len(match) > 1 else ""
        
        # 解析参数
        params = {}
        if cq_params_str:
            # 参数格式: key1=value1,key2=value2
            param_pairs = cq_params_str.split(',')
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    # 反转义 OneBot CQ 码特殊字符
                    value = value.replace('&amp;', '&').replace('&comma;', ',').replace('&#91;', '[').replace('&#93;', ']')
                    params[key] = value
        
        raw_cq_codes.append({
            'type': cq_type,
            'params': params
        })
        
        # 提取图片URL
        if cq_type == 'image' and 'url' in params:
            images.append(params['url'])
    
    # 移除CQ码，得到纯文本
    plain_text = re.sub(cq_pattern, '', text).strip()
    
    return {
        'text': plain_text,
        'images': images,
        'has_image': len(images) > 0,
        'raw_cq_codes': raw_cq_codes
    }


def extract_image_urls(text: str) -> List[str]:
    """
    从文本中提取所有图片URL
    
    Args:
        text: 包含CQ码的文本
        
    Returns:
        List[str]: 图片URL列表
    """
    result = parse_cq_code(text)
    return result['images']


def has_cq_image(text: str) -> bool:
    """
    判断文本是否包含图片CQ码
    
    Args:
        text: 待检查的文本
        
    Returns:
        bool: 是否包含图片
    """
    return '[CQ:image' in text
