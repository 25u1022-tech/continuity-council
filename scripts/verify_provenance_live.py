import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    repo_root = Path(__file__).resolve().parent.parent
    out_path = repo_root / "docs" / "demo" / "provenance_live.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    url = "https://frontend-murex-omega-66.vercel.app/methodology"
    print(f"Opening {url}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            device_scale_factor=2
        )
        page = await context.new_page()
        
        # Navigate with networkidle
        resp = await page.goto(url, wait_until="networkidle", timeout=30000)
        print(f"Page response status: {resp.status if resp else 'unknown'}")
        
        # Hard refresh to ensure no cache
        await page.reload(wait_until="networkidle")
        
        # Wait for provenance card
        await page.wait_for_selector('[data-testid="corpus-provenance-card"]', timeout=15000)
        print("Found [data-testid='corpus-provenance-card']")
        
        # Verify text content
        content = await page.content()
        assert "Historical Corpus Provenance" in content, "Missing Historical Corpus Provenance"
        assert "The 200,000-row historical corpus is synthetic, grounded in real public archives." in content, "Missing honesty line"
        assert "Open-Meteo Historical Weather 2019–2024" in content or "Open-Meteo" in content, "Missing Open-Meteo"
        assert "8.17x monsoon surge, Jun-Sep" in content, "Missing 8.17x caption"
        assert "Jul peak 234" in content, "Missing Jul peak 234"
        assert "Six years" in content or "six years" in content, "Missing six years"
        print("All assertions passed!")
        
        # Scroll provenance card into clear view
        card = page.locator('[data-testid="corpus-provenance-card"]')
        await card.scroll_into_view_if_needed()
        await page.wait_for_timeout(1000)
        
        # Capture screenshot of the provenance card and surrounding context
        await page.screenshot(path=str(out_path), full_page=False)
        print(f"Saved screenshot to {out_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
