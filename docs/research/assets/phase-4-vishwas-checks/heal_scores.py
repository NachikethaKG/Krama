"""Self-healing candidates on drifted Gitea pages: Healenium's scoring vs a role/name/context score.

For each scenario the script:
  1. opens the page as it is today and records the target element twice:
     - Healenium's fingerprint: the node path html → element with tag, id, classes, other attributes, index and
       innerText (port of healenium-web 3.5.8 `itemsWithAttributes.js`);
     - Krama's: ARIA role + accessible name (`parse_aria_snapshot`), `element_context` and the page bbox;
  2. opens the page again with a drift script (rename / restyle / move / remove), marks the element that is
     really "the same control" (window.__truth, never an attribute, so scoring can't see it);
  3. scores every candidate with
     - `healenium`: a line-by-line port of tree-comparing 0.4.14 `PathFinder` + `LCSPathDistance` +
       `HeuristicNodeDistance`, cut at Healenium's default score-cap 0.6;
     - `aria`: same role only, 0.30 name similarity + 0.20 same container (dialog/section heading) + 0.20 same
       form (its action URL + hidden `action` value) + 0.20 same stable attribute (id or name=) + 0.10 position.
       Two earlier tries are kept for the note: `score_no_form` (0.45 name + 0.35 container + 0.20 position) and
       `score_no_attr` (0.35 name + 0.25 container + 0.25 form + 0.15 position);
     and applies an accept rule: Healenium heals if top >= 0.6 (its own rule); `aria` heals only if
     top >= 0.75 AND top - second >= 0.15;
  4. runs Krama's real `ActionExecutor` (no vision) on the stored role/name: does today's chain still find it?
  5. with --vision: asks `GeminiVisionLocator` for the stored target on the drifted page (one request per scenario
     marked vision=True) and reports which element is under the point.

Run from backend/:  uv run python ../docs/research/assets/phase-4-vishwas-checks/heal_scores.py [--vision]
Output: results-heal.json next to this script.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from playwright.async_api import Page, async_playwright

from app.agent.context import element_context
from app.agent.executor import ActionExecutor
from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import run_script
from app.config import get_settings
from app.contracts_gen.common_schema import Action, Target
from app.verifier.aria import parse_aria_snapshot

BASE = "http://127.0.0.1:3001"
OUT = Path(__file__).with_name("results-heal.json")
S = get_settings()

# The element each scenario is about, found in the undrifted page (JS expression → Element).
CREATE_BTN = "[...document.querySelectorAll('form button.primary')].find(b => b.textContent.trim() === 'Create Repository')"
NAME_INPUT = "document.querySelector('#repo_name')"
# Gitea's settings page has three "Update Settings" buttons; the first one saves the description form.
SETTINGS_BTN = "document.querySelector('form input[name=action][value=update]').form.querySelector('button.primary')"


@dataclass(frozen=True)
class Scenario:
    id: str
    path: str
    find: str
    role: str
    name: str
    instruction: str
    drift: str = ""
    """JS run on DOMContentLoaded with `el` = the target; must leave window.__truth = the same control or null."""
    vision: bool = False


SCENARIOS = [
    Scenario("create:baseline", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository"),
    Scenario("create:renamed", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository", "el.textContent = 'Make repo';", vision=True),
    Scenario("create:restyled", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository", "el.className = 'ui green button btn-submit'; el.id = 'submit-new';"),
    Scenario("create:moved", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository",
             "const form = el.form; const box = document.createElement('div'); box.className = 'actions-top';"
             " box.appendChild(el); form.prepend(box);"),
    Scenario("create:renamed+restyled", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository",
             "el.textContent = 'Make repo'; el.className = 'ui green button'; el.id = 'go';"),
    Scenario("create:removed", "/repo/create", CREATE_BTN, "button", "Create Repository",
             "Click Create Repository", "el.remove(); window.__truth = null;", vision=True),
    Scenario("name:relabelled", "/repo/create", NAME_INPUT, "textbox", "Repository Name *",
             "Type the name in Repository Name",
             "document.querySelector('label[for=repo_name]').textContent = 'Name of the repository';"),
    Scenario("settings:baseline", "/demo/bench-settings/settings", SETTINGS_BTN, "button", "Update Settings",
             "Click Update Settings to save the description"),
    Scenario("settings:renamed", "/demo/bench-settings/settings", SETTINGS_BTN, "button", "Update Settings",
             "Click Update Settings to save the description", "el.textContent = 'Save';", vision=True),
    Scenario("settings:removed", "/demo/bench-settings/settings", SETTINGS_BTN, "button", "Update Settings",
             "Click Update Settings to save the description", "el.remove(); window.__truth = null;"),
]

# --- Healenium: capture (port of itemsWithAttributes.js, path html → element) ---------------------------------
PATH_JS = """el => { const items = []; let a = el;
  while (a && a !== document) { let i = 0, c = a; while ((c = c.previousElementSibling)) i++;
    const other = {}; for (const at of a.attributes || []) if (!['id','class','style'].includes(at.name)) other[at.name] = at.value;
    items.unshift({tag: a.tagName.toLowerCase(), id: a.id || '', index: i, innerText: a.innerText || '',
      classes: (a.getAttribute('class') || '').split(' ').filter(Boolean), other});
    a = a.parentNode; }
  return items; }"""
# The whole page as a tree (what Healenium parses with jsoup from document.body.outerHTML: here from <html>).
TREE_JS = """() => { let n = 0; const truth = window.__truth || null;
  const walk = (e, index) => { const other = {};
    for (const at of e.attributes) if (!['id','class','style'].includes(at.name)) other[at.name] = at.value;
    const node = {uid: n++, tag: e.tagName.toLowerCase(), id: e.id || '', index,
      classes: (e.getAttribute('class') || '').split(' ').filter(Boolean), other,
      text: (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 300), truth: e === truth,
      label: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' "' + (e.innerText || e.value || '').trim().slice(0, 40) + '"',
      children: [...e.children].filter(c => !['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(c.tagName)).map((c, i) => walk(c, i))};
    return node; };
  return walk(document.documentElement, 0); }"""


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lev_score(t1: str | None, t2: str | None, threshold_pct: float) -> float:
    """HeuristicNodeDistance.calculateLevenshteinScore: 0 beyond the threshold distance."""
    if t1 is None or t2 is None:
        return 0.0
    t1, t2 = t1.lower(), t2.lower()
    length = max(len(t1), len(t2))
    if length == 0:
        return 1.0
    if t1 in ("true", "false") or t2 in ("true", "false"):
        return 1.0 if t1 == t2 else 0.0
    d = _lev(t1[:300], t2[:300])
    return 0.0 if d > int(length * threshold_pct + 1) else (length - d) / length


def node_distance(n1: dict, n2: dict, lcs: int, height: int) -> float:
    """HeuristicNodeDistance.distance (tag 100, LCS 100, id 50, class 40, text 30, other attrs 30, index 0)."""
    if height == 0 or (height > 5 and lcs / height < 0.7):
        return 0.0
    score = lcs / height * 100
    maximum = 100 + 50 + 0 + 30 + 100 + 40 + 30
    if n1["tag"] == n2["tag"]:
        score += 100
    if n1["id"] is not None and n2["id"] is not None:
        score += 50 * lev_score(n1["id"], n2["id"], 0.3)
    score += 30 * lev_score(n1["innerText"], n2["text"], 0.3)
    c1, c2 = set(n1["classes"]), set(n2["classes"])
    union = c1 | c2
    score += (len(c1 & c2) * 40 / len(union)) if union else 40
    d1, d2 = c1 - c2, c2 - c1
    if d1 | d2:
        a, b = (d1, c2) if d1 else (c1, d2)
        pairs = [lev_score(x, y, 0.75) for x in a for y in b]
        cs = (sum(pairs) / len(pairs)) if pairs else 0.0
        cs = cs / len(union) if union else cs
        score += len(d1 | d2) * 40 * cs
    names = set(n1["other"]) | set(n2["other"])
    if names:
        score += sum(30 * lev_score(n1["other"].get(k), n2["other"].get(k), 0.75) for k in names) / len(names)
    else:
        score += 30
    return score / maximum


def healenium_candidates(path: list[dict], tree: dict, cap: float = 0.6) -> list[dict]:
    """PathFinder.findScoresToNodes + getSortedNodes: LCS of the stored path with every leaf path (nodes equal when
    tag and id are equal), candidates = the nodes of each leaf path from position LCS-1 down."""
    leaves: list[list[dict]] = []
    stack = [[tree]]
    while stack:
        p = stack.pop()
        kids = p[-1]["children"]
        if not kids:
            leaves.append(p)
        else:
            stack.extend(p + [k] for k in kids)
    key = [(n["tag"], n["id"]) for n in path]
    scored: list[tuple[list[dict], int]] = []
    for leaf in leaves:
        lk = [(n["tag"], n["id"]) for n in leaf]
        table = [[0] * (len(lk) + 1) for _ in range(len(key) + 1)]
        for i in range(1, len(key) + 1):
            for j in range(1, len(lk) + 1):
                table[i][j] = table[i - 1][j - 1] + 1 if key[i - 1] == lk[j - 1] else max(table[i - 1][j], table[i][j - 1])
        if table[-1][-1] >= 1:
            scored.append((leaf, table[-1][-1]))
    height = min(max((d for _, d in scored), default=0), len(path))
    best: dict[int, tuple[float, dict]] = {}
    for leaf, lcs in scored:
        for node in leaf[lcs - 1:]:
            s = node_distance(path[-1], node, lcs, height)
            if node["uid"] not in best or s > best[node["uid"]][0]:
                best[node["uid"]] = (s, node)
    ranked = sorted(best.values(), key=lambda t: -t[0])
    return [{"score": round(s, 3), "above_cap": s >= cap, "truth": n["truth"], "el": n["label"]} for s, n in ranked[:5]]


FORM_JS = """e => { const f = e.form || e.closest('form'); if (!f) return null;
  const a = f.querySelector('input[name=action]'); return (f.getAttribute('action') || '') + '|' + (a ? a.value : ''); }"""


# --- Krama: role + name + container + position ----------------------------------------------------------------
async def aria_fingerprint(page: Page, handle) -> dict:
    loc = page.locator("[data-krama-probe]")
    await handle.evaluate("e => e.setAttribute('data-krama-probe', '1')")
    snap = parse_aria_snapshot(await loc.aria_snapshot())
    ctx = await element_context(loc)
    box = await loc.bounding_box()
    scroll = await page.evaluate("[scrollX, scrollY]")
    form = await handle.evaluate(FORM_JS)
    attrs = await handle.evaluate("e => ({id: e.id || null, name: e.getAttribute('name')})")
    await handle.evaluate("e => e.removeAttribute('data-krama-probe')")
    return {
        "role": snap[0].role if snap else None,
        "name": snap[0].label() if snap else None,
        "context": ctx.model_dump() if ctx else None,
        "form": form,
        "attrs": attrs,
        "center": [box["x"] + scroll[0] + box["width"] / 2, box["y"] + scroll[1] + box["height"] / 2] if box else None,
    }


def name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(" *"), b.lower().strip(" *")).ratio()


def aria_score(stored: dict, cand: dict) -> dict:
    name = name_sim(stored["name"] or "", cand["name"] or "")
    sc, cc = stored["context"], cand["context"]
    context = 1.0 if sc == cc else 0.5 if (sc and cc and sc["container"] == cc["container"]) else 0.0
    position = 0.0
    if stored["center"] and cand["center"]:
        dist = ((stored["center"][0] - cand["center"][0]) ** 2 + (stored["center"][1] - cand["center"][1]) ** 2) ** 0.5
        position = max(0.0, 1 - dist / 500)
    form = 1.0 if stored["form"] == cand["form"] else 0.0
    sa, ca = stored["attrs"], cand["attrs"]
    keys = [k for k in ("id", "name") if sa.get(k)]
    attr = (1.0 if any(sa[k] == ca.get(k) for k in keys) else 0.0) if keys else 0.5
    total = 0.30 * name + 0.20 * context + 0.20 * form + 0.20 * attr + 0.10 * position
    no_attr = 0.35 * name + 0.25 * context + 0.25 * form + 0.15 * position
    no_form = 0.45 * name + 0.35 * context + 0.20 * position
    return {"score": round(total, 3), "score_no_attr": round(no_attr, 3), "score_no_form": round(no_form, 3),
            "name": round(name, 2), "context": context, "form": form, "attr": attr, "position": round(position, 2)}


async def aria_candidates(page: Page, stored: dict) -> list[dict]:
    loc = page.get_by_role(stored["role"]).filter(visible=True)  # type: ignore[arg-type]
    out = []
    for i in range(await loc.count()):
        h = await loc.nth(i).element_handle()
        if h is None:
            continue
        fp = await aria_fingerprint(page, h)
        truth = await h.evaluate("e => e === window.__truth")
        out.append({**aria_score(stored, fp), "truth": truth, "el": f'{fp["role"]} "{fp["name"]}"',
                    "context_seen": fp["context"]})
    out.sort(key=lambda c: -c["score"])
    return out[:5]


def decide(cands: list[dict], cap: float, margin: float) -> str:
    """What healing would do: heal_right / heal_WRONG / no_heal (nothing there: right) / missed (it was there)."""
    truth_present = any(c["truth"] for c in cands)
    top = cands[0] if cands else None
    second = cands[1]["score"] if len(cands) > 1 else 0.0
    if top is not None and top["score"] >= cap and top["score"] - second >= margin:
        return "heal_right" if top["truth"] else "heal_WRONG"
    return "missed" if truth_present else "no_heal"


async def signed_in_page(browser, drift: Scenario | None) -> Page:
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
    ctx.set_default_timeout(4_000)
    if drift is not None:
        await ctx.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => { const el = (%s);"
            " window.__truth = el; if (el && location.pathname === %s) { %s } });"
            % (drift.find, json.dumps(drift.path), drift.drift)
        )
    page = await ctx.new_page()
    await page.goto("/")
    log = await run_script(ActionExecutor(page), login_steps(user=S.gitea_demo_user, password=S.gitea_demo_password),
                           task="pre", base_url=BASE)
    assert log.ok, "sign-in failed"
    return page


async def main(use_vision: bool) -> None:
    vision = None
    if use_vision:
        from app.agent.vision import GeminiVisionLocator
        from app.llm import create_provider

        vision = GeminiVisionLocator(create_provider(S.model_copy(update={"llm_provider": "gemini"})))
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        clean = await signed_in_page(browser, None)
        for sc in SCENARIOS:
            await clean.goto(sc.path)
            handle = await clean.evaluate_handle(sc.find)
            stored_path = await handle.evaluate(PATH_JS)
            stored_aria = await aria_fingerprint(clean, handle)

            page = await signed_in_page(browser, sc)
            await page.goto(sc.path)
            tree = await page.evaluate(TREE_JS)
            row = {
                "scenario": sc.id,
                "stored": {"role": sc.role, "name": sc.name, "aria": stored_aria},
                "healenium": healenium_candidates(stored_path, tree),
                "aria": await aria_candidates(page, stored_aria),
            }
            row["decision"] = {"healenium": decide(row["healenium"], 0.6, 0.0), "aria": decide(row["aria"], 0.75, 0.15)}
            res = await ActionExecutor(page).execute(Action(type="wait"), Target(role=sc.role, name=sc.name))
            row["executor"] = {"ok": res.ok, "strategy": res.strategy, "error": res.error.code if res.error else None}
            if vision is not None and sc.vision:
                v = await vision.point(page, Target(role=sc.role, name=sc.name), sc.instruction)
                under = None
                if v.point is not None:
                    under = await page.evaluate(
                        "([x, y]) => { const e = document.elementFromPoint(x, y); const b = e && e.closest('button, a, input');"
                        " return b ? {el: b.tagName.toLowerCase() + ' \"' + (b.innerText || b.value || '').trim().slice(0, 40) + '\"',"
                        " truth: b === window.__truth} : null; }", list(v.point))
                row["vision"] = {"model": v.model, "point": v.point, "under_point": under, "error": v.error,
                                 "requests": len(v.attempts)}
            await page.context.close()
            results.append(row)
            h, a = row["healenium"], row["aria"]
            print(f'{sc.id:26} executor={row["executor"]["error"] or row["executor"]["strategy"]:17} '
                  f'healenium {h[0]["score"] if h else "-"}/{h[1]["score"] if len(h) > 1 else "-"} '
                  f'{row["decision"]["healenium"]:10} | aria {a[0]["score"] if a else "-"}/{a[1]["score"] if len(a) > 1 else "-"} '
                  f'{row["decision"]["aria"]}' + (f' | vision={row["vision"]["under_point"]}' if "vision" in row else ""))
        await browser.close()
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vision", action="store_true", help="also ask Gemini (one request per vision scenario)")
    sys.exit(asyncio.run(main(ap.parse_args().vision)))
