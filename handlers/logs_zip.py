import re
import io
import zipfile
import json
import httpx

async def handler(question: str, url: str, email: str) -> str:
    try:
        m = re.search(r'(/project2/[^\s"\'<>]+\.zip)', question)
        if not m:
            return "0"
        relative = m.group(1)
        domain = re.match(r'(https?://[^/]+)', url).group(1)
        zip_url = domain + relative
        async with httpx.AsyncClient() as client:
            resp = await client.get(zip_url, timeout=10)
            zip_bytes = resp.content
        total = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for name in z.namelist():
                with z.open(name) as f:
                    for line in f:
                        try:
                            obj = json.loads(line)
                            if obj.get("event") == "download":
                                total += obj.get("bytes", 0)
                        except:
                            pass
        offset = len(email) % 5
        return str(total + offset)
    except:
        return "0"
