"""Create a throwaway repo with one of everything that has a delete/close/transfer control (local Gitea only)."""
import base64, httpx
from app.config import get_settings
s = get_settings()
c = httpx.Client(base_url="http://localhost:3001/api/v1", auth=(s.gitea_demo_user, s.gitea_demo_password), timeout=20)
R = "demo/policy-fixture"
def ok(r: httpx.Response, what: str) -> None:
    print(f"{what:12} {r.status_code}")
c.delete(f"/repos/{R}")  # idempotent re-run
ok(c.post("/user/repos", json={"name": "policy-fixture", "auto_init": True, "readme": "Default"}), "repo")
ok(c.post(f"/repos/{R}/branches", json={"new_branch_name": "feature-x"}), "branch")
ok(c.post(f"/repos/{R}/labels", json={"name": "bug", "color": "#ee0701"}), "label")
ok(c.post(f"/repos/{R}/milestones", json={"title": "M1"}), "milestone")
i = c.post(f"/repos/{R}/issues", json={"title": "Fixture issue", "body": "for policy research"}); ok(i, "issue")
ok(c.post(f"/repos/{R}/issues/{i.json()['number']}/comments", json={"body": "a comment"}), "comment")
ok(c.post(f"/repos/{R}/releases", json={"tag_name": "v0.1", "name": "v0.1", "target_commitish": "main"}), "release")
ok(c.post(f"/repos/{R}/hooks", json={"type": "gitea", "active": False, "config": {"url": "http://127.0.0.1:9/never", "content_type": "json"}}), "webhook")
ok(c.post(f"/repos/{R}/wiki/new", json={"title": "Home", "content_base64": base64.b64encode(b"wiki").decode()}), "wiki")
