#!/usr/bin/env python3
"""Rank untested code by risk rather than by how untested it is.

Uncovered lines alone point at whatever is biggest and stalest. Multiplying by
commit count over a window points at code that is both unverified and moving,
which is a much better proxy for where the next defect lands.

    python3 coverage_gaps.py [--since 6.months] [--top 15] [--root .]

Falls back to structural pairing — source files with no matching test file — when
no coverage report exists, and says loudly which mode produced the numbers.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

COVERAGE_CANDIDATES = (
    "coverage/coverage-summary.json",
    "coverage/coverage-final.json",
    ".nyc_output/coverage-summary.json",
    "coverage.json",
)

SOURCE_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|cs)$")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.(py|go)$|test_.*\.py$")
SKIP_RE = re.compile(
    r"(^|/)(node_modules|dist|build|\.next|coverage|vendor|generated|__pycache__)(/|$)"
)
# Config and type-only modules carry no branches worth a test, and a ranking that
# puts `vitest.config.ts` near the top teaches the reader to distrust the list.
# Mirrors the exclusions a typical coverage config already applies, which is why
# they only need filtering in structural mode.
NOT_LOGIC_RE = re.compile(r"\.config\.[jt]sx?$|\.d\.ts$|(^|/)types?\.ts$|\.types\.ts$")


def git(args: list[str], root: str) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=root)
    return out.stdout if out.returncode == 0 else ""


def churn(root: str, since: str) -> dict[str, int]:
    """Commits touching each path in the window, as a movement proxy.

    `git log --name-only` prints paths relative to the *repository* root no
    matter which directory it runs in, while every other path here is relative
    to `--root`. Under `--root <subdir>` the two key spaces never intersect, so
    every count joins as 0 — and because the ranking multiplies by that count,
    the failure is not a missing column but an inverted list that reports the
    busiest files in the repo as "stable by demonstration". Re-base git's paths
    onto `root`, and drop anything outside it.
    """
    counts: dict[str, int] = {}
    top = git(["rev-parse", "--show-toplevel"], root).strip()
    prefix = ""
    if top:
        rel = os.path.relpath(root, top).replace("\\", "/")
        if rel not in (".", ""):
            prefix = f"{rel}/"
    log = git(["log", f"--since={since}", "--name-only", "--format=", "--", "."], root)
    for line in log.splitlines():
        path = line.strip()
        if not path:
            continue
        if prefix:
            if not path.startswith(prefix):
                continue
            path = path[len(prefix) :]
        counts[path] = counts.get(path, 0) + 1
    return counts


def find_coverage(root: str) -> str | None:
    for rel in COVERAGE_CANDIDATES:
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return path
    return None


def from_coverage(path: str, root: str) -> list[tuple[str, int, int]]:
    """(relative path, uncovered lines, total lines) from a coverage summary."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    rows: list[tuple[str, int, int]] = []
    for key, entry in data.items():
        if key == "total" or not isinstance(entry, dict):
            continue
        lines = entry.get("lines")
        # coverage-final.json keys statements by line number instead of carrying
        # a summary block; only the summary shape is usable here.
        if not isinstance(lines, dict) or "total" not in lines:
            continue
        total = int(lines.get("total") or 0)
        covered = int(lines.get("covered") or 0)
        if total <= 0:
            continue
        rows.append((normalise(key, root), max(total - covered, 0), total))
    return rows


def normalise(path: str, root: str) -> str:
    """Make a coverage key repo-relative, tolerating a report from another machine.

    A report generated in CI carries absolute paths like
    `/home/runner/work/app/src/db.ts`. A plain `relpath` against the local root
    turns those into `../../../../home/runner/...`, which is unreadable and does
    not match the paths `git log` reports, so churn would silently never join.
    Matching the longest existing suffix recovers the real path; a key that
    matches nothing is returned unchanged rather than mangled.
    """
    cleaned = path.replace("\\", "/")
    if not os.path.isabs(cleaned):
        return cleaned
    parts = [p for p in cleaned.split("/") if p not in ("", ".")]
    for start in range(len(parts)):
        candidate = os.path.join(root, *parts[start:])
        if os.path.exists(candidate):
            return "/".join(parts[start:])
    return cleaned


def from_structure(root: str) -> list[tuple[str, int, int]]:
    """Source files with no sibling test, sized by line count.

    Weaker than coverage data and labelled as such by the caller: a file can be
    thoroughly tested from a test file this pairing never associates with it.
    """
    sources: list[str] = []
    test_stems: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not SKIP_RE.search(f"/{d}/") and not d.startswith(".")]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            if SKIP_RE.search(f"/{rel}") or not SOURCE_RE.search(rel):
                continue
            if NOT_LOGIC_RE.search(rel):
                continue
            if TEST_RE.search(rel):
                stem = re.sub(r"\.(test|spec)(?=\.)", "", os.path.basename(rel))
                test_stems.add(os.path.splitext(stem)[0].replace("_test", "").replace("test_", ""))
            else:
                sources.append(rel)

    rows: list[tuple[str, int, int]] = []
    for rel in sources:
        if os.path.splitext(os.path.basename(rel))[0] in test_stems:
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
                size = sum(1 for _ in handle)
        except OSError:
            continue
        rows.append((rel, size, size))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="6.months")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    coverage_path = find_coverage(root)

    if coverage_path:
        rows = from_coverage(coverage_path, root)
        mode = f"coverage-backed ({os.path.relpath(coverage_path, root)})"
    else:
        rows = []

    if not rows:
        rows = from_structure(root)
        mode = "STRUCTURAL — no coverage report found, pairing source files to test files"

    print(f"mode: {mode}")
    print(f"churn window: {args.since}\n")

    if not rows:
        print("Nothing to rank: no source files found.")
        return 0

    commits = churn(root, args.since)
    ranked = sorted(
        ((rel, uncovered, total, commits.get(rel, 0)) for rel, uncovered, total in rows),
        key=lambda r: (r[1] * r[3], r[1]),
        reverse=True,
    )

    live = [r for r in ranked if r[1] > 0]
    print(f"{'risk':>8}  {'uncov':>6}  {'lines':>6}  {'commits':>7}  file")
    for rel, uncovered, total, n in live[: args.top]:
        print(f"{uncovered * n:>8}  {uncovered:>6}  {total:>6}  {n:>7}  {rel}")

    stale = [r for r in live if r[3] == 0]
    if stale:
        print(
            f"\n{len(stale)} file(s) have uncovered lines but no commits in the window. "
            "Stable by demonstration — rank them last, not first."
        )

    print(
        "\nRanking is uncovered_lines × commits. It is a heuristic: read the top files "
        "before proposing tests, and discard generated code, thin delegation, and "
        "anything covered by tests this run never saw."
    )
    # Gated on the mode actually used, not on whether a file was found. Those
    # differ: `coverage-final.json` is a candidate path but `from_coverage`
    # rejects its shape, so a repo carrying only that file runs structurally
    # while `coverage_path` is set — and used to skip the one warning that stops
    # a reader over-trusting the weaker ranking.
    if mode.startswith("STRUCTURAL"):
        print(
            "\nStructural mode is the weaker signal — a file can be well tested from a "
            "test file this pairing never associates with it. Say so in your report."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
