"""Gemini vision grounding on real Gitea screenshots vs Playwright's exact bounding boxes.

One request per (page, model): all targets of that page are asked for at once (free tier = 20 requests/day/model).
Metric: does the CENTRE of Gemini's box land inside the real element (i.e. would a click hit it)?"""
import asyncio, json, sys, time
from pathlib import Path
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from pydantic import BaseModel
from app.config import get_settings

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
MODELS = sys.argv[2].split(",")
BASE = "http://localhost:3001"
VIEW = {"width": 1280, "height": 800}
PAGES = {
    "dashboard": ("/", [("link", "New Repository"), ("link", "Explore"), ("link", "Milestones"), ("link", "Notifications"),
                        ("menu", "Create…"), ("combobox", "Other Filters"), ("link", "Dashboard")]),
    "repo-create": ("/repo/create", [("textbox", "Repository Name *"), ("checkbox", "Make repository private"),
                                     ("textbox", "Description"), ("link", "Migrate repository."), ("link", "Choose a license."),
                                     ("checkbox", "Make repository a template"), ("textbox", "Default Branch")]),
    "repo-home": ("/demo/demo-repo", [("link", "Settings"), ("button", "Star"), ("button", "Unwatch"), ("link", "Wiki"),
                                      ("button", "New Pull Request"), ("button", "Copy URL"), ("link", "Go to file"),
                                      ("textbox", "Search code..."), ("link", "1 Commit")]),
}

class Box(BaseModel):
    label: str
    box_2d: list[int]

class Boxes(BaseModel):
    items: list[Box]

def norm_to_px(b: list[int], w: int, h: int) -> tuple[float, float, float, float]:
    """Gemini box_2d = [ymin, xmin, ymax, xmax] in 0..1000 -> (x, y, width, height) in CSS px of the screenshot."""
    ymin, xmin, ymax, xmax = b
    x0, y0, x1, y1 = xmin / 1000 * w, ymin / 1000 * h, xmax / 1000 * w, ymax / 1000 * h
    return x0, y0, x1 - x0, y1 - y0

def iou(a, b) -> float:
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    ix = max(0, min(ax1, bx1) - max(a[0], b[0])); iy = max(0, min(ay1, by1) - max(a[1], b[1]))
    inter = ix * iy
    return inter / (a[2] * a[3] + b[2] * b[3] - inter) if inter else 0.0

async def capture() -> dict[str, tuple[bytes, list[tuple[str, str, tuple[float, float, float, float]]]]]:
    s = get_settings()
    shots = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport=VIEW)
        await page.goto(BASE + "/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        for key, (path, targets) in PAGES.items():
            await page.goto(BASE + path); await page.get_by_role("main").wait_for(); await page.wait_for_timeout(500)
            truth = []
            for role, name in targets:
                loc = page.get_by_role(role, name=name, exact=True)
                if await loc.count() != 1:
                    print(f"  skip {key} {role} {name!r}: {await loc.count()} matches"); continue
                bb = await loc.bounding_box()
                if not bb or bb["y"] < 0 or bb["y"] + bb["height"] > VIEW["height"]:
                    print(f"  skip {key} {role} {name!r}: off-screen"); continue
                truth.append((role, name, (bb["x"], bb["y"], bb["width"], bb["height"])))
            png = await page.screenshot()
            (OUT / f"{key}.png").write_bytes(png)
            shots[key] = (png, truth)
        await b.close()
    return shots

def ask(client: genai.Client, model: str, png: bytes, truth) -> tuple[list[Box], float]:
    wanted = "\n".join(f"- {i}: the {role} labelled \"{name}\"" for i, (role, name, _) in enumerate(truth))
    prompt = ("This is a screenshot of a web page. For each UI element below, return its bounding box. "
              "Use the element's index as label. box_2d is [ymin, xmin, ymax, xmax] normalized to 0-1000.\n" + wanted)
    thinking = types.ThinkingConfig(thinking_budget=0) if "2.5" in model else types.ThinkingConfig(thinking_level="low")
    t = time.perf_counter()
    r = client.models.generate_content(
        model=model, contents=[types.Part.from_bytes(data=png, mime_type="image/png"), prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           response_json_schema=Boxes.model_json_schema(), thinking_config=thinking))
    return Boxes.model_validate_json(r.text).items, time.perf_counter() - t

async def main() -> None:
    shots = await capture()
    client = genai.Client(api_key=get_settings().gemini_api_key)
    rows = []
    for model in MODELS:
        for key, (png, truth) in shots.items():
            try:
                boxes, secs = ask(client, model, png, truth)
            except Exception as e:
                print(f"{model} {key}: ERROR {type(e).__name__}: {str(e)[:150]}"); continue
            by_label = {b.label.strip(): b for b in boxes}
            for i, (role, name, real) in enumerate(truth):
                b = by_label.get(str(i))
                if not b or len(b.box_2d) != 4:
                    rows.append(dict(model=model, page=key, target=f"{role} {name}", hit=False, err=None, iou=0.0, secs=secs)); continue
                pred = norm_to_px(b.box_2d, VIEW["width"], VIEW["height"])
                cx, cy = pred[0] + pred[2] / 2, pred[1] + pred[3] / 2
                hit = real[0] <= cx <= real[0] + real[2] and real[1] <= cy <= real[1] + real[3]
                rx, ry = real[0] + real[2] / 2, real[1] + real[3] / 2
                rows.append(dict(model=model, page=key, target=f"{role} {name}", hit=hit,
                                 err=round(((cx - rx) ** 2 + (cy - ry) ** 2) ** 0.5, 1), iou=round(iou(pred, real), 2),
                                 real=[round(v) for v in real], pred=[round(v) for v in pred], secs=round(secs, 1)))
    (OUT / "results.json").write_text(json.dumps(rows, indent=2))
    for m in MODELS:
        mr = [r for r in rows if r["model"] == m]
        if not mr: continue
        errs = sorted(r["err"] for r in mr if r["err"] is not None)
        print(f"{m}: click hits {sum(r['hit'] for r in mr)}/{len(mr)}, median centre error "
              f"{errs[len(errs)//2] if errs else '-'} px, mean IoU {sum(r['iou'] for r in mr)/len(mr):.2f}, "
              f"latency/page {sorted({r['secs'] for r in mr})}")
        for r in mr:
            if not r["hit"]:
                print(f"   miss: {r['page']:12} {r['target']:50} err={r['err']} real={r.get('real')} pred={r.get('pred')}")

asyncio.run(main())
