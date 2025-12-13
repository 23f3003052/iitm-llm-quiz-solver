import re

async def handler(question: str, url: str, email: str) -> str:
    try:
        m = re.search(r'uv\s+http\s+(\w+)\s+on\s+(https?://[^\s<>"\']+)', question, re.IGNORECASE)
        if not m:
            return "uv http get https://example.com"
        method = m.group(1)
        api_url = m.group(2).replace("<your email>", email)
        parts = [f"uv http {method} {api_url}"]
        if "Accept: application/json" in question:
            parts.append('-H "Accept: application/json"')
        return " ".join(parts)
    except:
        return "uv http get https://example.com"
