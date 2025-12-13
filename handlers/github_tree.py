import re
import httpx
import json

async def handler(question: str, url: str, email: str) -> str:
    try:
        m = re.search(r'(/project2/[^\s"\'<>]+\.json)', question)
        if not m:
            return "0"
        relative = m.group(1)
        domain = re.match(r'(https?://[^/]+)', url).group(1)
        cfg_url = domain + relative
        async with httpx.AsyncClient() as client:
            cfg = (await client.get(cfg_url)).json()
        owner = cfg["owner"]
        repo = cfg["repo"]
        sha = cfg["sha"]
        prefix = cfg.get("pathPrefix", "")
        ext = cfg.get("extension", ".md")
        api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
        tree = (await httpx.AsyncClient().get(api)).json()
        count = 0
        for item in tree.get("tree", []):
            path = item.get("path", "")
            if path.startswith(prefix) and path.endswith(ext):
                count += 1
        offset = len(email) % 2
        return str(count + offset)
    except:
        return "0"
