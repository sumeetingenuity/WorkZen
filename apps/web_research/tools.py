"""
Web Research Tools for SecureAssist.

Example tools using @agent_tool decorator.
"""
from core.decorators import agent_tool


@agent_tool(
    name="search_web",
    description="Search the web for information using AI-powered search. Returns relevant snippets and URLs.",
    secrets=["TAVILY_API_KEY"],
    log_response_to_orm=True,
    category="web_research"
)
async def search_web(query: str, max_results: int = 5) -> dict:
    """
    Search the web using Tavily AI search.
    
    The LLM just calls: @search_web(query="Django best practices")
    Response is stored in DB and shown to user directly.
    """
    import httpx
    
    # Get secret (injected by decorator)
    api_key = _secret_TAVILY_API_KEY  # noqa: F821
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            return {"error": f"Search failed: {response.status_code}"}
        
        data = response.json()
        
        return {
            "query": query,
            "answer": data.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:300]
                }
                for r in data.get("results", [])
            ]
        }


@agent_tool(
    name="browse_page",
    description="Navigate to a URL and extract page content including text and links.",
    log_response_to_orm=True,
    timeout_seconds=60,
    category="web_research"
)
async def browse_page(url: str, extract_links: bool = False) -> dict:
    """
    Browse a web page and extract content.
    
    Uses Playwright for JavaScript-rendered pages.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright not installed. Run: pip install playwright && playwright install"}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            title = await page.title()
            text = await page.evaluate("() => document.body.innerText")
            
            links = []
            if extract_links:
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a'))
                        .map(a => ({href: a.href, text: a.innerText.trim()}))
                        .filter(l => l.href.startsWith('http') && l.text)
                        .slice(0, 50)
                """)
            
            return {
                "url": url,
                "title": title,
                "text_content": text[:10000],  # Truncate for storage
                "links": links
            }
            
        except Exception as e:
            return {"error": f"Failed to load page: {str(e)}"}
        finally:
            await browser.close()
