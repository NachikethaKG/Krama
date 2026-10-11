"""End to end at device_scale_factor=2: screenshot is 2560x1600 px, but Playwright's mouse uses CSS px (1280x800).
Gemini's 0-1000 coordinates are relative to the image, so scale by the CSS viewport, not the PNG size."""
import asyncio, struct
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from pydantic import BaseModel
from app.config import get_settings

class Box(BaseModel):
    box_2d: list[int]

async def main() -> None:
    s = get_settings(); client = genai.Client(api_key=s.gemini_api_key)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        await page.goto("http://localhost:3001/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url("http://localhost:3001/")
        await page.get_by_role("main").wait_for()
        png = await page.screenshot()
        w, h = struct.unpack(">II", png[16:24])
        print("png size:", w, h, "| css viewport:", page.viewport_size)
        r = client.models.generate_content(model="gemini-3.8-flash", contents=[
            types.Part.from_bytes(data=png, mime_type="image/png"),
            'Return the bounding box of the link "New Repository" in the repository list panel. box_2d is [ymin, xmin, ymax, xmax] normalized to 0-1000.'],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=Box.model_json_schema(),
                                               thinking_config=types.ThinkingConfig(thinking_level="low")))
        ymin, xmin, ymax, xmax = Box.model_validate_json(r.text).box_2d
        vw, vh = page.viewport_size["width"], page.viewport_size["height"]
        x, y = (xmin + xmax) / 2 / 1000 * vw, (ymin + ymax) / 2 / 1000 * vh
        print(f"click at CSS ({x:.0f}, {y:.0f})  (using PNG size instead would give ({x*2:.0f}, {y*2:.0f}): off-screen)")
        await page.mouse.click(x, y)
        await page.wait_for_url("**/repo/create", timeout=5000)
        print("navigated to:", page.url)
        await b.close()
asyncio.run(main())
