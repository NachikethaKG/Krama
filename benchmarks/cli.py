"""Unified command-line interface entrypoint for benchmarks."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from benchmarks.report import main as report_main
from benchmarks.runner import main as runner_main


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        return report_main([])

    subcommand = args[0]
    if subcommand in ("report", "bench-report"):
        return report_main(args[1:])
    if subcommand in ("run", "trial"):
        return runner_main(args[1:])

    # Default to report parser if flags match report options
    if any(arg.startswith(("--input", "--output")) or arg == "--json" for arg in args):
        return report_main(args)

    # Otherwise fallback to runner
    return runner_main(args)


if __name__ == "__main__":
    sys.exit(main())
