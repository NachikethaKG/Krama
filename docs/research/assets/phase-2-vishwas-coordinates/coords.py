"""Do stored bboxes line up with the rrweb recording? Measured on a scrolled Gitea page.

For each target on /repo/create (viewport 1280x600, so the bottom of the form is below the fold):
  A  what the agent stores today: bounding_box() + window.scroll, measured BEFORE the action
  B  scroll and box right after the action (Playwright's click scrolls the element into view)
  C  rrweb's own MouseInteraction click (x, y are viewport coordinates) and the last rrweb scroll before it
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-coordinates/coords.py <dpr>
"""
import asyncio, json, sys
from playwright.async_api import async_playwright
from app.config import get_settings
from app.observer.rrweb import RRWebRecorder

BASE = "http://127.0.0.1:3001"
DPR = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
VIEW = {"width": 1280, "height": 600}
# Harmless targets low on the create form (toggle / focus only; nothing is submitted).
TARGETS = [("checkbox", "Make repository a template"), ("textbox", "Default Branch"), ("checkbox", "Make repository private")]

async def main() -> None:
    s = get_settings()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport=VIEW, device_scale_factor=DPR)
        page = await ctx.new_page()
        await page.goto(BASE + "/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        rec = RRWebRecorder()
        await rec.start(ctx)
        await page.goto(BASE + "/repo/create"); await page.get_by_role("main").wait_for(); await page.wait_for_timeout(500)
        doc_h = await page.evaluate("document.documentElement.scrollHeight")
        rows = []
        for role, name in TARGETS:
            loc = page.get_by_role(role, name=name, exact=True)
            box = await loc.bounding_box()
            sx, sy = await page.evaluate("[scrollX, scrollY]")
            stored = (box["x"] + sx, box["y"] + sy, box["width"], box["height"])     # A: today's code
            t_click = await page.evaluate("Date.now()")
            await loc.click()
            await page.wait_for_timeout(300)
            sx2, sy2 = await page.evaluate("[scrollX, scrollY]")
            box2 = await loc.bounding_box()
            rows.append({"target": f"{role} {name!r}", "t_click": t_click, "stored_A": stored, "scroll_before": [sx, sy],
                         "scroll_after": [sx2, sy2], "page_box_after": (box2["x"] + sx2, box2["y"] + sy2, box2["width"], box2["height"])})
        await page.wait_for_timeout(500)
        events = await rec.stop()
        shot = await page.screenshot()
        await b.close()
    clicks = [e for e in events if e.get("type") == 3 and e["data"].get("source") == 2 and e["data"].get("type") == 2]
    scrolls = [e for e in events if e.get("type") == 3 and e["data"].get("source") == 3]
    meta = [e["data"] for e in events if e.get("type") == 4]
    from PIL import Image; import io
    print(f"DPR {DPR}: screenshot {Image.open(io.BytesIO(shot)).size} for viewport {VIEW}; document height {doc_h}; rrweb meta {meta[-1:]}")
    for r, c in zip(rows, clicks):
        prior = [e for e in scrolls if e["timestamp"] <= c["timestamp"]]
        rr_scroll = (prior[-1]["data"]["x"], prior[-1]["data"]["y"]) if prior else (0, 0)
        x, y, w, h = r["stored_A"]
        # Where the stored box is in the replay's viewport at the click, using rrweb's own scroll:
        vx, vy = x - rr_scroll[0], y - rr_scroll[1]
        inside = vx <= c["data"]["x"] <= vx + w and vy <= c["data"]["y"] <= vy + h
        print(json.dumps({**r, "rrweb_click_xy": [c["data"]["x"], c["data"]["y"]], "rrweb_scroll_at_click": rr_scroll,
                          "stored_box_in_replay_viewport": [round(vx, 1), round(vy, 1), w, h], "click_inside_stored_box": inside}))
    print(f"{len(clicks)} rrweb clicks, {len(scrolls)} rrweb scroll events")
    t0 = clicks[0]["timestamp"] if clicks else 0
    for e in sorted(clicks + scrolls, key=lambda e: e["timestamp"]):
        kind = "click " if e["data"]["source"] == 2 else "scroll"
        print(f"  +{e['timestamp'] - t0:5d} ms  {kind} x={e['data']['x']} y={e['data']['y']}")

asyncio.run(main())
