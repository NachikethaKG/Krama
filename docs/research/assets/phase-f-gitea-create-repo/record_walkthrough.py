"""Record the 'create a repository' flow in local Gitea, step by step, as raw material for the first fixture."""

import json
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:3001"
OUT = Path(__file__).parent / "walk"
OUT.mkdir(exist_ok=True)
REPO = "demo-repo"


def state(page: Page) -> dict:
    main = page.locator("[role=main], .page-content").first
    return {
        "url": page.url.replace(BASE, ""),
        "title": page.title(),
        "headings": [h.strip() for h in page.locator(".page-content h1, .page-content h2, .page-content h3, .page-content h4")
                     .all_inner_texts() if h.strip()][:5],
        "aria_excerpt": "\n".join(main.aria_snapshot().splitlines()[:12]),
    }


steps: list[dict] = []
t0 = time.monotonic()


def step(page: Page, n: int, action: str, role: str, name: str, value: str | None = None, wait_url: str | None = None,
         scope=None):
    loc = (scope or page).get_by_role(role, name=name)
    box = loc.bounding_box()
    before = page.url.replace(BASE, "")
    start = int((time.monotonic() - t0) * 1000)
    if action == "fill":
        loc.fill(value or "")
    else:
        loc.click()
    if wait_url:
        page.wait_for_url(f"**{wait_url}")
    else:
        page.wait_for_timeout(300)
    end = int((time.monotonic() - t0) * 1000)
    shot = OUT / f"step-{n}.png"
    page.screenshot(path=shot)
    steps.append({"seq": n, "action": {"type": action, "value": value},
                  "target": {"role": role, "name": name, "bbox": [round(box[k]) for k in ("x", "y", "width", "height")] if box else None},
                  "url_before": before, "observed": state(page), "timing": {"start_ms": start, "end_ms": end},
                  "screenshot": shot.name})
    print(f"step {n}: {action} {role} '{name}' -> {page.url.replace(BASE, '')} | {page.title()}")


with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1280, "height": 800})

    # Precondition: signed in as demo
    page.goto(f"{BASE}/user/login")
    login = {"url": "/user/login", "title": page.title()}
    page.get_by_label("Username or Email Address").fill("demo")
    page.get_by_label("Password").fill("demo-local-only")
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(f"{BASE}/")
    page.screenshot(path=OUT / "step-0-dashboard.png")
    start_state = state(page)
    print("precondition: signed in ->", start_state["url"], "|", start_state["title"])

    step(page, 1, "click", "menu", "Create…")
    step(page, 2, "click", "menuitem", "New Repository", wait_url="/repo/create")
    step(page, 3, "fill", "textbox", "Repository Name", value=REPO)
    step(page, 4, "click", "checkbox", "Initialize Repository (Adds .gitignore, License and README)")
    step(page, 5, "click", "button", "Create Repository", wait_url=f"/demo/{REPO}")
    final = state(page)
    readme_visible = page.get_by_role("heading", name="demo-repo").count() > 0 or "README" in page.content()
    print("final headings:", final["headings"], "| README present:", readme_visible)

    # Negative case: the same name again must fail and stay on the form
    page.goto(f"{BASE}/repo/create")
    page.get_by_role("textbox", name="Repository Name").fill(REPO)
    page.get_by_role("button", name="Create Repository").click()
    page.wait_for_load_state("domcontentloaded")
    page.screenshot(path=OUT / "negative-duplicate.png")
    err = page.locator(".ui.negative.message, .flash-error").first
    negative = {"url": page.url.replace(BASE, ""), "title": page.title(),
                "error_text": err.inner_text().strip() if err.count() else None,
                "aria_excerpt": "\n".join(err.aria_snapshot().splitlines()[:5]) if err.count() else None}
    print("duplicate name ->", negative["url"], "|", negative["error_text"])

(OUT / "walkthrough.json").write_text(json.dumps(
    {"precondition": {"signed_in_as": "demo", "login_page": login, "start_state": start_state},
     "steps": steps, "final_state": final, "negative_duplicate_name": negative}, indent=2, ensure_ascii=False),
    encoding="utf-8")
print("saved", OUT / "walkthrough.json")
