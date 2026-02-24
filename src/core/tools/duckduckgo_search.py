"""
DuckDuckGo 免费搜索工具
提供无需 API Key 的网页文本搜索能力
使用原生 HTML 爬虫，绕过 API 限制
"""

import logging
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse

logger = logging.getLogger(__name__)

async def search_web_duckduckgo(query: str, max_results: int = 5) -> str:
    """
    使用 DuckDuckGo 执行网页搜索并格式化为文本结果
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        
    Returns:
        文本化的搜索结果
    """
    logger.info(f"Executing HTML DuckDuckGo search for: {query}")
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    return f"搜索请求失败, 状态码: {response.status}"
                html = await response.text()
                
        soup = BeautifulSoup(html, 'html.parser')
        results = soup.find_all('div', class_='result')
        
        if not results:
            return "未找到相关搜索结果。"
            
        results_text = []
        for i, res in enumerate(results[:max_results]):
            title_tag = res.find('a', class_='result__url')
            snippet_tag = res.find('a', class_='result__snippet')
            
            title = title_tag.text.strip() if title_tag else '无标题'
            link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else ''
            # DuckDuckGo HTML version redirects, clean it up
            if link.startswith('//duckduckgo.com/l/?uddg='):
                link = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])
            snippet = snippet_tag.text.strip() if snippet_tag else '无内容摘要'
            
            results_text.append(f"[{i+1}] {title}\n摘要: {snippet}\n链接: {link}")
            
        return "\n\n".join(results_text)
        
    except Exception as e:
        logger.error(f"DuckDuckGo HTML search failed: {e}")
        return f"搜索失败: {str(e)}"
