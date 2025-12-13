import csv
import io
import json
import re
import httpx
import dateutil.parser

async def handler(question: str, url: str) -> str:
    try:
        # Find CSV URL
        m = re.search(r'(https?://[^\s<>"\']+\.csv[^\s<>"\']*)', question, re.IGNORECASE)
        if not m:
             # Try href
            m = re.search(r'href=["\']([^"\']+\.csv[^"\']*)', question, re.IGNORECASE)
            if m:
                relative = m.group(1)
                domain = re.match(r'(https?://[^/]+)', url).group(1)
                csv_url = domain + relative if relative.startswith('/') else domain + '/' + relative
            else:
                return "[]"
        else:
            csv_url = m.group(1)
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(csv_url)
            csv_text = resp.text
            
        reader = csv.DictReader(io.StringIO(csv_text))
        data = []
        for row in reader:
            new_row = {}
            for k, v in row.items():
                new_key = k.strip().lower()
                val = v.strip()
                
                if new_key == 'id' or new_key == 'value':
                    try:
                        new_row[new_key] = int(val)
                    except:
                        new_row[new_key] = val # Fallback
                elif new_key == 'joined':
                    try:
                        dt = dateutil.parser.parse(val, dayfirst=True)
                        new_row[new_key] = dt.strftime('%Y-%m-%d')
                    except:
                        new_row[new_key] = val
                else:
                    new_row[new_key] = val
            data.append(new_row)
            
        # Sort by id
        data.sort(key=lambda x: x.get('id', 0))
        
        return json.dumps(data)
        
    except Exception as e:
        print(f"Normalize Error: {e}")
        return "[]"
