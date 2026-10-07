"""Experiment 1 (#25): Playwright aria_snapshot / role locators / expect on local Gitea."""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3001"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
results: dict = {"snapshots": {}, "checks": {}}


def snap(page, name: str, scope: str = "body") -> str:
    t0 = time.perf_counter()
    loc = page.locator("body") if scope == "body" else page.get_by_role(scope)
    text = loc.aria_snapshot()
    ms = (time.perf_counter() - t0) * 1000
    (OUT / f"{name}.{scope}.yaml").write_text(text, encoding="utf-8")
    results["snapshots"][f"{name}:{scope}"] = {
        "url": page.url.replace(BASE, ""),
        "chars": len(text),
        "lines": text.count("\n") + 1,
        "approx_tokens_chars_div_4": len(text) // 4,
        "ms": round(ms, 1),
    }
    return text


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{BASE}/user/login")
    snap(page, "login")
    page.get_by_label("Username or Email Address").fill("demo")
    page.get_by_label("Password").fill("demo-local-only")
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(f"{BASE}/")
    snap(page, "dashboard")
    snap(page, "dashboard", "main")

    page.get_by_role("menu", name="Create…").click()
    snap(page, "menu-open")

    page.get_by_role("menuitem", name="New Repository").click()
    page.wait_for_url(f"{BASE}/repo/create")
    snap(page, "repo-create-empty")
    snap(page, "repo-create-empty", "main")

    # Locator matching with the " *" required-field suffix
    c = results["checks"]
    c["role_textbox_substring_count"] = page.get_by_role("textbox", name="Repository Name").count()
    c["role_textbox_exact_no_star_count"] = page.get_by_role("textbox", name="Repository Name", exact=True).count()
    c["role_textbox_exact_with_star_count"] = page.get_by_role("textbox", name="Repository Name *", exact=True).count()
    c["label_substring_count"] = page.get_by_label("Repository Name").count()

    page.get_by_role("textbox", name="Repository Name").fill("demo-repo")
    page.get_by_role("checkbox", name="Initialize Repository").check()
    filled = snap(page, "repo-create-filled", "main")
    c["snapshot_shows_textbox_value"] = "demo-repo" in filled
    c["snapshot_shows_checked"] = "[checked]" in filled
    c["checkbox_lines"] = [l.strip() for l in filled.splitlines() if "Initialize" in l]
    c["name_lines"] = [l.strip() for l in filled.splitlines() if "Repository Name" in l]

    # expect() assertions
    t0 = time.perf_counter()
    expect(page.get_by_role("checkbox", name="Initialize Repository")).to_be_checked()
    expect(page.get_by_role("textbox", name="Repository Name")).to_have_value("demo-repo")
    c["expect_pass_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter()
    try:
        expect(page).to_have_url(f"{BASE}/demo/demo-repo", timeout=1000)
        c["expect_fail_raised"] = False
    except AssertionError as e:
        c["expect_fail_raised"] = True
        c["expect_fail_msg_first_line"] = str(e).splitlines()[0]
    c["expect_fail_ms_with_1s_timeout"] = round((time.perf_counter() - t0) * 1000, 1)

    # Snapshot matching (to_match_aria_snapshot) as a verifier primitive
    try:
        expect(page.get_by_role("main")).to_match_aria_snapshot(
            '- checkbox /Initialize Repository/ [checked]\n', timeout=1000
        )
        c["to_match_aria_snapshot_partial"] = "pass"
    except AssertionError as e:
        c["to_match_aria_snapshot_partial"] = "fail: " + str(e).splitlines()[0]

    # Auto-wait: action on a missing element times out
    t0 = time.perf_counter()
    try:
        page.get_by_role("button", name="Does Not Exist").click(timeout=2000)
    except PWTimeout as e:
        c["missing_click_error"] = str(e).splitlines()[0]
    c["missing_click_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    btn = page.get_by_role("button", name="Create Repository")
    c["create_btn_bbox"] = btn.bounding_box()
    btn.click()
    page.wait_for_url(f"{BASE}/demo/demo-repo")
    snap(page, "repo-home")
    snap(page, "repo-home", "main")

    # Duplicate-name failure state
    page.goto(f"{BASE}/repo/create")
    page.get_by_role("textbox", name="Repository Name").fill("demo-repo")
    page.get_by_role("button", name="Create Repository").click()
    page.wait_for_load_state("domcontentloaded")
    dup = snap(page, "repo-create-duplicate", "main")
    c["duplicate_banner_in_snapshot"] = [l.strip() for l in dup.splitlines() if "already used" in l]
    browser.close()

(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
