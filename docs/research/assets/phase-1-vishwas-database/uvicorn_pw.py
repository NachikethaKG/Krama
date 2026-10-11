import asyncio
from fastapi import FastAPI
from playwright.async_api import async_playwright
app = FastAPI()
@app.get("/")
async def check() -> dict[str, str]:
    loop = type(asyncio.get_running_loop()).__name__
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(); await b.close()
        pw = "launched"
    except Exception as e:
        pw = f"FAIL {type(e).__name__}"
    return {"loop": loop, "playwright": pw}
