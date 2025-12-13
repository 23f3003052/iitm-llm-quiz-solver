import csv
import io
import json
import re
import httpx
from datetime import datetime

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
                # Snake case key: "Full Name" -> "full_name"
                new_key = k.strip().lower().replace(" ", "_")
                val = v.strip()
                
                # Integer columns
                if new_key in ['id', 'value', 'salary', 'age', 'count']:
                    try:
                        new_row[new_key] = int(val)
                    except:
                        new_row[new_key] = val
                
                # Date columns (common formats)
                elif new_key in ['joined', 'date', 'signup_date']:
                    try:
                        # Try YYYY-MM-DD
                        dt = datetime.strptime(val, '%Y-%m-%d')
                        new_row[new_key] = dt.strftime('%Y-%m-%d')
                    except:
                        try:
                            # Try DD/MM/YYYY
                            dt = datetime.strptime(val, '%d/%m/%Y')
                            new_row[new_key] = dt.strftime('%Y-%m-%d')
                        except:
                            new_row[new_key] = val
                else:
                    new_row[new_key] = val
            data.append(new_row)
            
        # Sort by id just in case
        data.sort(key=lambda x: x.get('id', 0))
        
        return json.dumps(data)
        
    except Exception as e:
        print(f"Normalize Error: {e}")
        return "[]"
