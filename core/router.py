# core/router.py
import logging
from handlers import (
    image_color, audio, llm  # Keep it simple: Image, Audio, LLM
)

async def route_and_solve(question: str, url: str, page_data: dict, email: str) -> str:
    q = question.lower()
    
    # 1. Image Tasks
    if "heatmap" in q or "color" in q or ".png" in q:
        return await image_color.handler(question, url)
        
    # 2. Audio Tasks
    if "audio" in q or "listen" in q or ".opus" in q or ".mp3" in q:
        return await audio.handler(question, url)

    # 3. EVERYTHING ELSE -> LLM
    # This handles SQL, CSV, JSON, Docker, Git, Curl, etc.
    return await llm.handler(question, url)
