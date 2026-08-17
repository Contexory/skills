#!/usr/bin/env python3
"""Inventory a diff so the author reviews the surprises rather than the summary.

Deterministic half of self-review: what changed, what kind of file it is, and
four flags that reliably mark the places authors miss. Whether a flag matters is
a judgement call and is left to the reader — the script never says "this is
wrong", only "this is unusual, decide about it".

    python3 review_surface.py [base-ref]

`base-ref` defaults to the merge base with the repository's default branch, so it
reports the change as a reviewer would see it rather than only the last commit.
Standard library only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

WIDE_HUNK_LINES = 200

GENERATED_MARKERS = ("/generated/", "/dist/", "/.next/", "/node_modules/")
LOCKFILES = ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "Cargo.lock", "poetry.lock", "go.sum")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.(py|go)$|test_.*\.py$")
DOC_RE = re.compile(r"\.(md|mdx|rst|txt|adoc)$|(^|/)docs?/")
CONFIG_RE = re.compile(r"\.(json|ya?ml|toml|ini|cfg|env)$|(^|/)\.[^/]+rc|config\.[jt]s$")
SOURCE_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|cs|php|scala)$")

# An exported symbol, across the languages this is likely to meet. Deliberately
# conservative: a missed export is a quieter failure than a false one, which
# would train the reader to ignore the flag.
EXPORT_RE = re.compile(
    r"^\+\s*(?:export\s+(?:default\s+|const\s+|function\s+|class\s+|type\s+|interface\s+|enum\s+|async\s+)"
    r"|pub\s+(?:fn|struct|enum|trait)\s+"
    r"|func\s+[A-Z]"
    r"|public\s+(?:static\s+)?(?:class|interface|[A-Za-z<>\[\]]+\s+[A-Z]))"
)
# A removed line that was a test case.
DEL_TEST_RE = re.compile(r"^-\s*(?:it|test|describe)\s*[(.]|^-\s*def test_|^-\s*func Test[A-Z]")


@dataclass
class FileChange:
    path: str
    added: int = 0
    removed: int = 0
    new_exports: list[str] = field(default_factory=list)
    deleted_tests: int = 0
    widest_hunk: int = 0

    @property
    def kind(self) -> str:
        p = self.path
        if any(m in f"/{p}" for m in GENERATED_MARKERS):
            return "generated"
        if os.path.basename(p) in LOCKFILES:
            return "lockfile"
        if TEST_RE.search(p):
            return "test"
        if DOC_RE.search(p):
            return "docs"
        if SOURCE_RE.search(p):
            return "source"
        if CONFIG_RE.search(p):
            return "config"
        return "other"

    @property
    def stem(self) -> str:
        """Path with test/spec markers and extension stripped, for pairing a
        source file with the test file that covers it."""
        base = os.path.basename(self.path)
        base = re.sub(r"\.(test|spec)(?=\.)", "", base)
        base = re.sub(r"^test_|_test$", "", os.path.splitext(base)[0])
        return base


def git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def diff_path(header: str) -> str | None:
    """Path from a `---`/`+++` header line, or None for `/dev/null`.

    A **deleted** file's `+++` is `/dev/null` and its only name is on the `---`
    line, so reading `+++ b/` alone does not merely lose the deletion — the
    parser stays pointed at the previously-parsed file and charges every removed
    line to it. Deleting a whole test file then reports DEL-TEST against an
    unrelated source file, which is the flag pointing at the wrong place.
    """
    rest = header.strip()
    if rest == "/dev/null":
        return None
    return rest[2:] if rest[:2] in ("a/", "b/") else rest


def default_base() -> str:
    """Merge base with the default branch, falling back to HEAD~1.

    Reviewers see the whole branch, not the last commit, so that is what gets
    inventoried. A repo with no main/master (a fresh clone, a detached CI
    checkout) still gets a useful answer rather than an error.
    """
    for branch in ("origin/main", "main", "origin/master", "master"):
        base = git(["merge-base", "HEAD", branch]).strip()
        if base:
            return base
    return "HEAD~1"


def collect(base: str) -> list[FileChange]:
    files: dict[str, FileChange] = {}
    current: FileChange | None = None
    old_path: str | None = None
    in_hunks = False
    hunk_len = 0

    diff = git(["diff", "--unified=0", base, "--"])
    for line in diff.splitlines():
        # Headers are read only before a file's first `@@`. Position is what
        # disambiguates them: a removed line whose own text begins with `---`
        # (a YAML document marker, a comment) is otherwise indistinguishable
        # from a file header, and treating it as one silently reassigns the
        # rest of the hunk.
        if line.startswith("diff --git "):
            if current:
                current.widest_hunk = max(current.widest_hunk, hunk_len)
            current, old_path, in_hunks, hunk_len = None, None, False, 0
            continue
        if not in_hunks:
            if line.startswith("--- "):
                old_path = diff_path(line[4:])
            elif line.startswith("+++ "):
                if current:
                    current.widest_hunk = max(current.widest_hunk, hunk_len)
                hunk_len = 0
                path = diff_path(line[4:]) or old_path
                current = files.setdefault(path, FileChange(path=path)) if path else None
            elif line.startswith("@@"):
                in_hunks = True
            continue
        if current is None:
            continue
        if line.startswith("@@"):
            current.widest_hunk = max(current.widest_hunk, hunk_len)
            hunk_len = 0
            continue
        # Past the first `@@` every `+`/`-` line is content, so no header guard
        # is needed here — and the guard that used to be here was itself a
        # miscount: it dropped any removed line whose own text starts with `---`
        # (a YAML document marker, an ASCII rule), understating the churn of
        # exactly the frontmatter-heavy files it most needs to measure.
        if line.startswith("+"):
            current.added += 1
            hunk_len += 1
            if EXPORT_RE.search(line):
                current.new_exports.append(line[1:].strip()[:90])
        elif line.startswith("-"):
            current.removed += 1
            if DEL_TEST_RE.search(line):
                current.deleted_tests += 1
    if current:
        current.widest_hunk = max(current.widest_hunk, hunk_len)

    # `git diff` cannot see a file that was never added, so a brand-new module
    # sitting untracked in the working tree is invisible to it — which is
    # precisely the surprise this script exists to surface. Treat each untracked
    # file as wholly added and run the same flags over its contents.
    for path in git(["ls-files", "--others", "--exclude-standard"]).splitlines():
        path = path.strip()
        if not path or path in files:
            continue
        change = files.setdefault(path, FileChange(path=path))
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()
        except OSError:
            continue
        change.added = len(lines)
        change.widest_hunk = len(lines)
        change.new_exports = [
            ln.strip()[:90] for ln in lines if EXPORT_RE.search("+" + ln)
        ]

    return sorted(files.values(), key=lambda f: f.path)


def main() -> int:
    # Run from the repository root, as the sibling scripts do. `git diff` reports
    # root-relative paths from anywhere, but `git ls-files --others` reports
    # cwd-relative paths *and* only descends the cwd subtree — so invoked from a
    # subdirectory the untracked scan silently drops new files elsewhere in the
    # repo, which is precisely the blind spot that scan was added to close.
    root = git(["rev-parse", "--show-toplevel"]).strip()
    if root:
        os.chdir(root)

    base = sys.argv[1] if len(sys.argv) > 1 else default_base()
    changes = collect(base)
    if not changes:
        print(f"No changes against {base}.")
        return 0

    changed_test_stems = {c.stem for c in changes if c.kind == "test"}

    print(f"base: {base}")
    print(f"{len(changes)} file(s) changed\n")

    flagged: list[tuple[str, str]] = []
    for c in changes:
        flags = []
        if c.kind == "source" and c.stem not in changed_test_stems:
            flags.append("NO-TEST")
        if c.new_exports:
            flags.append("NEW-EXPORT")
        if c.deleted_tests:
            flags.append("DEL-TEST")
        if c.widest_hunk > WIDE_HUNK_LINES:
            flags.append("WIDE")
        churn = f"+{c.added}/-{c.removed}"
        print(f"  [{c.kind:>9}] {churn:>12}  {c.path}")
        if flags:
            print(f"              {' '.join(flags)}")
            flagged.append((c.path, " ".join(flags)))
        for e in c.new_exports[:5]:
            print(f"                · {e}")

    print("\n── decisions required ──\n")
    if not flagged:
        print("  None. Nothing in this diff carries a flag.")
    for path, flags in flagged:
        print(f"  {path}: {flags}")

    print(
        "\nFor each NO-TEST file, state one of: behaviour-preserving / covered by an "
        "existing test (name it) / needs a test (write it now).\n"
        "A flag is a prompt for a decision, not a verdict."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
