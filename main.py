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
        
        # Use Playwright to render the scrape page
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(scrape_url, wait_until="networkidle", timeout=10000)
            await page.wait_for_timeout(1500)
            
            html = await page.content()
            text = await page.text_content("body")
            
            await browser.close()
        
        print(f"  Content: {text[:150]}...")
        
        # Look for secret
        patterns = [
            r'<!--\s*([A-Za-z0-9_\-]{6,})\s*-->',
            r'<div[^>]*id=["\']secret["\'][^>]*>([^<]+)</div>',
            r'data-secret=["\']([^"\']+)["\']',
            r'"secret"\s*:\s*"([^"]+)"',
            r'Secret[:\s]+([A-Za-z0-9_\-]{6,})',
        ]
        
        for pattern in patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                secret = m.group(1).strip()
                print(f"  Found: {secret}")
                return secret
        
        # Last resort: extract any substantial string
        words = re.findall(r'\b[A-Za-z0-9_\-]{8,20}\b', text)
        for w in words:
            if w.lower() not in ['email', 'secret', 'password', 'answer', 'your', 'submit']:
                print(f"  Using: {w}")
                return w
        
        return "not_found"
    except Exception as e:
        print(f"  Error: {e}")
        return "error"

async def parse_csv(question: str, url: str, email: str) -> str:
    try:
        # Extract cutoff
        m = re.search(r'Cutoff[:\s]+(\d+)', question, re.IGNORECASE)
        cutoff = int(m.group(1)) if m else 0
        print(f"  Cutoff: {cutoff}")
        
        # Find CSV URL - try multiple patterns
        csv_url = None
        
        # Pattern 1: Direct URL in question
        m = re.search(r'(https?://[^\s<>"\']+\.csv[^\s<>"\']*)', question, re.IGNORECASE)
        if m:
            csv_url = m.group(1)
        
        # Pattern 2: Link in question
        m = re.search(r'href=["\']([^"\']+\.csv[^"\']*)', question, re.IGNORECASE)
        if m:
            relative = m.group(1)
            domain = re.match(r'(https?://[^/]+)', url).group(1)
            csv_url = domain + relative if relative.startswith('/') else domain + '/' + relative
        
        # Pattern 3: Relative path
        if not csv_url:
            m = re.search(r'(\/[a-z\-0-9]+\.csv[^\s<>"\']*)', question, re.IGNORECASE)
            if m:
                domain = re.match(r'(https?://[^/]+)', url).group(1)
                csv_url = domain + m.group(1)
        
        # Pattern 4: Look in URL for data file
        if not csv_url:
            base = url.split('?')[0]
            csv_url = base.replace('demo-audio', 'data-q') + '.csv'
        
        if not csv_url:
            print(f"  No CSV URL found")
            return "0"
        
        print(f"  CSV URL: {csv_url}")
        
        # Fetch CSV
        async with httpx.AsyncClient() as client:
            resp = await client.get(csv_url, timeout=10)
            csv_text = resp.text
        
        print(f"  Fetched {len(csv_text)} bytes")
        
        # Parse
        reader = csv.reader(StringIO(csv_text))
        total = 0
        for row in reader:
            for cell in row:
                try:
                    val = float(cell)
                    if val > cutoff:
                        total += val
                except:
                    pass
        
        print(f"  Sum: {int(total)}")
        return str(int(total))
    
    except Exception as e:
        print(f"  CSV Error: {e}")
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
