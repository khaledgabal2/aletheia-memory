#!/usr/bin/env python3
"""Release gate checks for preserving the generic Aletheia baseline."""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path


GENERIC_BASELINE_REFS = {"main", "refs/heads/main"}
PRODUCT_SPECIFIC_PATTERNS = (
    "aletheia/integrations/sample_adapter.py",
    "docs/ALETHEIA_SAMPLE_ADAPTER_COMPATIBILITY_LAYER_PLAN.md",
    "tests/fixtures/sample_adapter/*",
    "tests/test_sample_adapter_compatibility.py",
)


def target_is_generic_baseline(*, branch: str | None = None, base_ref: str | None = None) -> bool:
    target = (base_ref or branch or "").strip()
    return target in GENERIC_BASELINE_REFS


def disallowed_product_files(paths: list[str]) -> list[str]:
    return sorted(
        {
            path
            for path in paths
            for pattern in PRODUCT_SPECIFIC_PATTERNS
            if fnmatch.fnmatch(path, pattern)
        }
    )


def tracked_files(cwd: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def current_branch(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME"))
    parser.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_REF"))
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    branch = args.branch or current_branch(repo)
    if not target_is_generic_baseline(branch=branch, base_ref=args.base_ref):
        return 0

    matches = disallowed_product_files(tracked_files(repo))
    if matches:
        print(
            "Product-specific integration files are not allowed on the generic main baseline:",
            file=sys.stderr,
        )
        for path in matches:
            print(f"- {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
