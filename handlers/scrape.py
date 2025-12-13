import re
from playwright.async_api import async_playwright

async def handler(question: str, url: str) -> str:
    
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
