from playwright.async_api import async_playwright
import logging

async def fetch_page(url: str) -> dict:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 15s timeout for page load
            await page.goto(url, wait_until="networkidle", timeout=15000)
            # Small wait for JS rendering
            await page.wait_for_timeout(1000)
            
            html = await page.content()
            text = await page.text_content("body")
            
            await browser.close()
            return {"html": html, "question": text.strip() if text else ""}
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        return None
