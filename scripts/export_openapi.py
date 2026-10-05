"""Write contracts/openapi.json from the FastAPI app (`just export-openapi`, also run by `just gen-contracts`).

Run inside the backend environment: `uv run --project backend python scripts/export_openapi.py`.
Output is sorted and LF-terminated, so it is byte-identical on Windows and on Linux CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "contracts" / "openapi.json"


def main() -> int:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import create_app

    spec = create_app().openapi()
    text = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}: {len(spec['paths'])} paths, "
          f"{len(spec.get('components', {}).get('schemas', {}))} schemas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
