import re
import httpx

def find_submit_url(q: str, html: str, url: str) -> str:
    m = re.search(r'(https?://[^\s<>"\']+/submit[^\s<>"\']*)', q)
    if m:
        return m.group(1)
    m = re.search(r'(https?://[^\s<>"\']+/submit[^\s<>"\']*)', html)
    if m:
        return m.group(1)
    domain = re.match(r'(https?://[^/]+)', url)
    if domain and "/submit" in q:
        return domain.group(1) + "/submit"
    # Fallback
    if domain:
        return domain.group(1) + "/submit"
    return url

async def submit_answer(email: str, secret: str, url: str, answer: str, submit_url: str) -> dict:
    payload = {"email": email, "secret": secret, "url": url, "answer": answer}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(submit_url, json=payload)
            return r.json() if r.status_code == 200 else {"correct": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"correct": False, "reason": str(e)}
