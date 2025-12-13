import re
import io
from collections import Counter
from PIL import Image
import httpx

async def handler(question: str, url: str) -> str:
    try:
        m = re.search(r'(/project2/[^\s"\'<>]+\.png)', question)
        if not m:
            return "#000000"
        relative = m.group(1)
        domain = re.match(r'(https?://[^/]+)', url).group(1)
        img_url = domain + relative
        async with httpx.AsyncClient() as client:
            resp = await client.get(img_url, timeout=10)
            img_bytes = resp.content
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        pixels = list(img.getdata())
        (r, g, b), _ = Counter(pixels).most_common(1)[0]
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    except:
        return "#000000"
