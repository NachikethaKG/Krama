"""Generate Pydantic v2 models from contracts/schemas into backend/app/contracts_gen (`just gen-contracts`).

Never edit backend/app/contracts_gen by hand: change the schema, then re-run this.
Flags come from docs/research/phase-f-vishwas-pydantic-generation.md and contracts/README.md.
Commit the output with KRAMA_GEN=1 so the ownership hook accepts generated files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = Path("contracts/schemas")  # relative, so generated headers are identical on every machine
OUTPUT = Path("backend/app/contracts_gen")

FLAGS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.12",
    "--use-title-as-name",  # schema titles become class names (contracts/README.md rule 2)
    "--use-type-alias",  # named enums become `type Risk = Literal[...]`, so `risk == "low"` works
    "--enum-field-as-literal", "all",
    "--extra-fields", "forbid",  # additionalProperties: false
    "--use-annotated",
    "--field-constraints",
    "--use-union-operator",
    "--use-standard-collections",
    "--use-double-quotes",
    "--disable-timestamp",  # deterministic output
    "--formatters", "ruff-format",
]
# Then format and lint with the backend's own ruff config, the same config CI checks.
RUFF = [["ruff", "format", "app/contracts_gen"], ["ruff", "check", "--fix", "--quiet", "app/contracts_gen"]]


def main() -> int:
    if not (ROOT / SCHEMAS).is_dir() or not any((ROOT / SCHEMAS).glob("*.schema.json")):
        print(f"no schemas in {SCHEMAS}", file=sys.stderr)
        return 1

    # Regenerate from scratch so models of deleted schemas disappear too.
    shutil.rmtree(ROOT / OUTPUT, ignore_errors=True)
    cmd = ["uv", "run", "--project", "backend", "datamodel-codegen",
           "--input", SCHEMAS.as_posix(), "--output", OUTPUT.as_posix(), *FLAGS]
    # Force UTF-8 in the child: Windows defaults to cp1252, which breaks on characters like "…" in schemas.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env
    )
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        return result.returncode

    for ruff in RUFF:
        fixed = subprocess.run(["uv", "run", *ruff], cwd=ROOT / "backend", capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env)
        if fixed.returncode != 0:
            print(fixed.stdout + fixed.stderr, file=sys.stderr)
            return fixed.returncode

    # ruff's cache inside the output folder is not part of the generated code
    shutil.rmtree(ROOT / OUTPUT / ".ruff_cache", ignore_errors=True)
    files = sorted(p.name for p in (ROOT / OUTPUT).glob("*.py"))
    print(f"generated {len(files)} files in {OUTPUT.as_posix()}: {', '.join(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
