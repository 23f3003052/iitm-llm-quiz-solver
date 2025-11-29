from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import re
import json
import httpx
from datetime import datetime
import base64
import csv
from io import StringIO

load_dotenv()

app = FastAPI()

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

class QuizResponse(BaseModel):
    status: str
    message: str = None

VALID_EMAIL = os.getenv("STUDENT_EMAIL")
VALID_SECRET = os.getenv("STUDENT_SECRET")

@app.post("/solve")
async def solve_quiz(request: QuizRequest) -> QuizResponse:
    if request.email != VALID_EMAIL:
        raise HTTPException(status_code=403, detail="Invalid email")
    if request.secret != VALID_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    try:
        await solve_quiz_chain(request.url, request.email, request.secret)
        return QuizResponse(status="success")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return QuizResponse(status="error", message=str(e))

async def solve_quiz_chain(initial_url: str, email: str, secret: str):
    current_url = initial_url
    attempt = 0
    
    while current_url and attempt < 15:
        attempt += 1
        print(f"\n{'='*70}\n[QUIZ {attempt}] {current_url}\n{'='*70}")
        
        page_data = await fetch_page(current_url)
        if not page_data:
            continue
        
        question = page_data["question"]
        print(f"Q: {question[:300]}...")
        
        submit_url = find_submit_url(question, page_data["html"], current_url)
        if not submit_url:
            submit_url = f"{current_url.split('?')[0].replace(current_url.split('/')[-1], '')}submit"
        
        print(f"Submit: {submit_url}")
        
        # Solve
        answer = await solve(question, current_url, page_data, email)
        print(f"Answer: {answer}")
        
        # Submit
        resp = await submit(email, secret, current_url, answer, submit_url)
        print(f"Response: Correct={resp.get('correct')}, Reason={resp.get('reason')}")
        
        if resp.get("correct"):
            current_url = resp.get("url")
            if not current_url:
                print("\n✅ QUIZ COMPLETE\n")
                break
        else:
            current_url = resp.get("url")
            if not current_url:
                break

async def fetch_page(url: str) -> dict:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)
            
            html = await page.content()
            text = await page.text_content("body")
            
            await browser.close()
            return {"html": html, "question": text.strip() if text else ""}
    except:
        return None

def find_submit_url(q: str, html: str, url: str) -> str:
    m = re.search(r'(https?://[^\s<>"\']+/submit[^\s<>"\']*)', q)
    if m: return m.group(1)
    m = re.search(r'(https?://[^\s<>"\']+/submit[^\s<>"\']*)', html)
    if m: return m.group(1)
    domain = re.match(r'(https?://[^/]+)', url)
    if domain and "/submit" in q: return domain.group(1) + "/submit"
    return None

async def solve(question: str, url: str, page_data: dict, email: str) -> str:
    q = question.lower()
    
    if "scrape" in q or "secret" in q:
        return await scrape_secret(question, url, email)
    elif "csv" in q or "cutoff" in q:
        return await parse_csv(question, url, email)
    elif "pdf" in q or "download" in q:
        return "0"
    else:
        return "anything you want"

async def scrape_secret(question: str, url: str, email: str) -> str:
    try:
        # Extract relative URL
        m = re.search(r'Scrape\s+([\w\/\?\-=&@.]+)', question, re.IGNORECASE)
        if not m:
            return "not_found"
        
        relative = m.group(1).strip()
        domain = re.match(r'(https?://[^/]+)', url).group(1)
        scrape_url = domain + relative if relative.startswith('/') else domain + '/' + relative
        
        print(f"  Scraping: {scrape_url}")
        
        # Use Playwright to render
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(scrape_url, wait_until="networkidle", timeout=10000)
            await page.wait_for_timeout(1500)
            
            html = await page.content()
            text = await page.text_content("body")
            
            await browser.close()
        
        print(f"  Full content:\n{text[:300]}...")
        
        # Look for "Secret code is XXXX" pattern
        m = re.search(r'Secret\s+code\s+is\s+([0-9a-zA-Z_\-]+)', text, re.IGNORECASE)
        if m:
            secret = m.group(1).strip()
            print(f"  ✅ Found secret: {secret}")
            return secret
        
        # Look for "code: XXXX" pattern
        m = re.search(r'code[:\s]+([0-9a-zA-Z_\-]+)', text, re.IGNORECASE)
        if m:
            secret = m.group(1).strip()
            print(f"  ✅ Found code: {secret}")
            return secret
        
        # Look in HTML comments
        m = re.search(r'<!--\s*([0-9a-zA-Z_\-]{6,})\s*-->', html, re.IGNORECASE)
        if m:
            secret = m.group(1).strip()
            print(f"  ✅ Found in comment: {secret}")
            return secret
        
        # Look for data attributes
        m = re.search(r'data-secret=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            secret = m.group(1).strip()
            print(f"  ✅ Found in data attr: {secret}")
            return secret
        
        # Last resort: extract any number
        numbers = re.findall(r'\b\d{4,}\b', text)
        if numbers:
            print(f"  ✅ Using number: {numbers[0]}")
            return numbers[0]
        
        print(f"  ❌ No secret pattern found")
        return "not_found"
    
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return "error"

async def parse_csv(question: str, url: str, email: str) -> str:
    try:
        # Extract cutoff
        m = re.search(r'Cutoff[:\s]+(\d+)', question, re.IGNORECASE)
        cutoff = int(m.group(1)) if m else 0
        print(f"  Cutoff: {cutoff}")
        
        # Strategy 1: Look for CSV URL in question
        csv_url = None
        m = re.search(r'(https?://[^\s<>"\']+\.csv[^\s<>"\']*)', question, re.IGNORECASE)
        if m:
            csv_url = m.group(1)
            print(f"  Found CSV URL in question: {csv_url}")
        
        # Strategy 2: Look for data file link
        if not csv_url:
            m = re.search(r'href=["\']([^"\']+\.csv[^"\']*)', question, re.IGNORECASE)
            if m:
                relative = m.group(1)
                domain = re.match(r'(https?://[^/]+)', url).group(1)
                csv_url = domain + relative if relative.startswith('/') else domain + '/' + relative
                print(f"  Found CSV in href: {csv_url}")
        
        # Strategy 3: Try common patterns for data files
        if not csv_url:
            base = url.split('?')[0]  # Remove query params
            # Try replacing page name with data file
            base_domain = re.match(r'(https?://[^/]+)', url).group(1)
            
            # Pattern: demo-audio -> data-q-audio.csv
            page_name = base.split('/')[-1]
            variants = [
                f"{base_domain}/data-{page_name}.csv",
                f"{base_domain}/data.csv",
                f"{base_domain}/data-q.csv",
                base.replace(page_name, 'data.csv'),
            ]
            
            for variant in variants:
                print(f"  Trying: {variant}")
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.head(variant)
                        if resp.status_code == 200:
                            csv_url = variant
                            print(f"  ✅ Found: {csv_url}")
                            break
                except:
                    pass
        
        if not csv_url:
            print(f"  ⚠️  No CSV URL found")
            return "0"
        
        print(f"  Fetching: {csv_url}")
        
        # Fetch CSV
        async with httpx.AsyncClient() as client:
            resp = await client.get(csv_url, timeout=10)
            csv_text = resp.text
        
        print(f"  Fetched {len(csv_text)} bytes")
        print(f"  CSV preview: {csv_text[:200]}...")
        
        # Parse CSV
        reader = csv.reader(StringIO(csv_text))
        total = 0
        count = 0
        
        for row in reader:
            for cell in row:
                try:
                    val = float(cell)
                    if val > cutoff:
                        total += val
                        count += 1
                        print(f"    Added {val} (>{cutoff})")
                except:
                    pass
        
        print(f"  Total sum: {int(total)} (count: {count})")
        return str(int(total))
    
    except Exception as e:
        print(f"  CSV Error: {e}")
        import traceback
        traceback.print_exc()
        return "0"


async def submit(email: str, secret: str, url: str, answer: str, submit_url: str) -> dict:
    payload = {"email": email, "secret": secret, "url": url, "answer": answer}
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(submit_url, json=payload)
            return r.json() if r.status_code == 200 else {"correct": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"correct": False, "reason": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

#NEW

async def solve(question: str, url: str, page_data: dict, email: str) -> str:
    q = question.lower()
    
    # Project 2 challenges
    
    # UV command challenge
    if "uv http" in q and "command string" in q:
        print("  🔧 UV HTTP command challenge")
        return await generate_uv_command(question, url, email)
    
    # Original demo challenges
    if "scrape" in q:
        print("  🔍 Scraping question")
        return await scrape_secret(question, url, email)
    
    if "secret" in q and "scrape" not in q:
        print("  🔍 Secret extraction")
        return await scrape_secret(question, url, email)
    
    if "csv" in q or "cutoff" in q:
        print("  📊 CSV question")
        return await parse_csv(question, url, email)
    
    if "pdf" in q or ("download" in q and "file" in q):
        print("  📄 PDF question")
        return "0"
    
    print("  ❓ Generic question")
    return "anything you want"

async def generate_uv_command(question: str, url: str, email: str) -> str:
    """Generate uv http command string"""
    try:
        # Extract the URL pattern from question
        # Pattern: "uv http get on https://...?email=<your email>"
        m = re.search(r'uv\s+http\s+(\w+)\s+on\s+(https?://[^\s<>"\']+)', question, re.IGNORECASE)
        if not m:
            print(f"  ⚠️  Could not parse uv command format")
            return "uv http get https://example.com"
        
        method = m.group(1)  # "get", "post", etc.
        api_url = m.group(2).replace('<your email>', email)
        
        print(f"  Method: {method}")
        print(f"  URL: {api_url}")
        
        # Look for headers in question
        headers = []
        if "Accept: application/json" in question:
            headers.append('-H "Accept: application/json"')
        
        # Build command string
        if headers:
            command = f'uv http {method} {api_url} {" ".join(headers)}'
        else:
            command = f'uv http {method} {api_url}'
        
        print(f"  Command: {command}")
        return command
    
    except Exception as e:
        print(f"  Error: {e}")
        return "uv http get https://example.com"
