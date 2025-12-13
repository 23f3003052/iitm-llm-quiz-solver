import logging
from handlers import (
    uv_cmd, git_cmd, literal_path, image_color, 
    csv_normalize, csv_sum, github_tree, logs_zip, 
    scrape, generic, audio  # <--- Added audio
)

async def route_and_solve(question: str, url: str, page_data: dict, email: str) -> str:
    q = question.lower()
    
    # 1. Command String Tasks
    if "uv http" in q and "command string" in q:
        return await uv_cmd.handler(question, url, email)
    if "git" in q and "commit" in q:
        return await git_cmd.handler(question)
    
    # 2. Literal Path Tasks (e.g., submit /project2/foo.md)
    if "exact string" in q or "relative link target" in q:
        return await literal_path.handler(question)
        
    # 3. Image Tasks
    if "heatmap" in q or "color" in q or ".png" in q:
        return await image_color.handler(question, url)
    
    # NEW: Audio Tasks
    if "audio" in q or "listen" in q or ".opus" in q or ".mp3" in q:
        return await audio.handler(question, url)
        
    # 4. CSV Tasks
    if "normalize" in q and "json" in q:
        return await csv_normalize.handler(question, url)
    if "csv" in q or "cutoff" in q:
        return await csv_sum.handler(question, url)
        
    # 5. GitHub API Tasks
    if "github api" in q and "tree" in q:
        return await github_tree.handler(question, url, email)
        
    # 6. Zip/Log Tasks
    if "logs.zip" in q or "jsonl" in q:
        return await logs_zip.handler(question, url, email)
        
    # 7. Web Scraping / Secret Finding (Fallback for "scrape")
    if "scrape" in q or "secret" in q:
        return await scrape.handler(question, url)
        
    # 8. Generic / Unknown
    return await generic.handler(question)
