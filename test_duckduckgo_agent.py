import asyncio
import logging
from src.core.tools.duckduckgo_search import search_web_duckduckgo

logging.basicConfig(level=logging.INFO)

async def test_search():
    query = "OpenAI 最新模型"
    print(f"Testing search with query: {query}")
    results = await search_web_duckduckgo(query, max_results=3)
    print("--- Search Results ---")
    print(results)
    print("----------------------")

if __name__ == "__main__":
    asyncio.run(test_search())
