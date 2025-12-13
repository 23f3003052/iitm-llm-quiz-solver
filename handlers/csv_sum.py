import re
import csv
from io import StringIO
import httpx

async def handler(question: str, url: str) -> str:
    try:
        m = re.search(r'Cutoff[:\s]+(\d+)', question, re.IGNORECASE)
        cutoff = int(m.group(1)) if m else 0
        csv_url = None
        m = re.search(r'(https?://[^\s<>"\']+\.csv[^\s<>"\']*)', question, re.IGNORECASE)
        if m:
            csv_url = m.group(1)
        if not csv_url:
            return "0"
        async with httpx.AsyncClient() as client:
            resp = await client.get(csv_url, timeout=10)
            csv_text = resp.text
        reader = csv.reader(StringIO(csv_text))
        total = 0
        for row in reader:
            for cell in row:
                try:
                    v = float(cell)
                    if v > cutoff:
                        total += v
                except:
                    pass
        return str(int(total))
    except:
        return "0"
