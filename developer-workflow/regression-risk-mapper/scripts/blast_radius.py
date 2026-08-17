#!/usr/bin/env python3
"""Find everything that references the symbols a diff touched.

The mechanical half of "what could this break": which symbols moved, who names
them, and which of those callers sit in files with no test. Whether a caller
actually depends on the changed *behaviour* is a reading task, and the script
says so rather than implying its list is a risk assessment.

    python3 blast_radius.py [base-ref]

Textual search, with the blind spots that implies — dynamic dispatch, string-keyed
lookup, reflection and consumers in other repositories are invisible here, and the
report repeats that every run. Standard library only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import defaultdict

SOURCE_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|cs)$")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.(py|go)$|test_.*\.py$")
SKIP_RE = re.compile(r"(^|/)(node_modules|dist|build|\.next|coverage|vendor|__pycache__)(/|$)")

# Symbols whose definition line changed, restricted to the *public* surface.
#
# An earlier version matched any `const x =`, which pulled every local in every
# changed test body into the map — `spy`, `res`, `rows`, `elapsed` — and then
# reported a thousand references for each. That is not a blast radius, it is a
# concordance, and a reader who sees it once stops reading the tool's output.
#
# Two rules keep it honest: the definition must be exported (or top-level, for
# languages where export is implicit), and it must sit at column zero, so a
# nested helper inside a function body is never mistaken for API.
DEFINITION_RE = re.compile(
    r"^[+-](?:export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:function|const|let|var|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)"
    r"|pub\s+(?:fn|struct|trait|enum)\s+([A-Za-z_][\w]*)"
    r"|def\s+([A-Za-z_][\w]*)"
    r"|class\s+([A-Za-z_][\w]*)"
    r"|func\s+(?:\([^)]*\)\s*)?([A-Z][\w]*))"
)

# Languages with no export keyword need a second gate, or the rule above admits
# nothing and everything: Python has no `export`, so *every* module-level `def`
# reads as public API. On this pack's own scripts that meant 47 "changed
# symbols" — `git`, `walk`, `parse`, `report`, `usage`, `collect` — whose top
# five each blew past NOISE_THRESHOLD and printed "too common to map" instead of
# a radius. TOO_COMMON cannot keep up; the words are ordinary.
#
# The honest test for public is whether anything imports it by name. A helper
# nobody imports has no blast radius outside its own file by definition, which
# is exactly the question this script answers.
NEEDS_IMPORT_PROOF = (".py",)
IMPORTED_NAME_RE = re.compile(
    r"^\s*from\s+[\w.]+\s+import\s+(.+)$|^\s*import\s+([\w.]+)\s*(?:as\s+\w+)?\s*$"
)

# Past this many references a symbol is a common word rather than an API, and
# listing its call sites is worse than saying so.
NOISE_THRESHOLD = 200
RE_EXPORT_RE = re.compile(r"^\s*export\s+(?:\*|\{[^}]*\})\s+from\s+")

# Identifiers common enough that their call sites are noise rather than a radius.
TOO_COMMON = {
    "main", "run", "get", "set", "init", "handler", "index", "config", "options",
    "data", "value", "result", "error", "test", "setup", "teardown", "props", "state",
}


def git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def diff_path(header: str) -> str | None:
    """Path from a `---`/`+++` header line, or None for `/dev/null`.

    A **deleted** file's `+++` is `/dev/null` and its only name is on the `---`
    line. Reading `+++ b/` alone leaves the parser pointed at the previous file,
    which defeats the test-file exclusion below: the deleted file's name never
    reaches `TEST_RE`, so symbols defined only in a deleted test are mapped as
    changed API — exactly the concordance the guard exists to prevent.
    """
    rest = header.strip()
    if rest == "/dev/null":
        return None
    return rest[2:] if rest[:2] in ("a/", "b/") else rest


def default_base() -> str:
    for branch in ("origin/main", "main", "origin/master", "master"):
        base = git(["merge-base", "HEAD", branch]).strip()
        if base:
            return base
    return "HEAD~1"


def changed_symbols(base: str) -> tuple[set[str], set[str]]:
    """(symbols whose definitions changed, files the diff touched)."""
    symbols: set[str] = set()
    files: set[str] = set()
    current: str | None = None
    old_path: str | None = None
    in_hunks = False

    for line in git(["diff", "--unified=0", base, "--"]).splitlines():
        # Headers are read only before a file's first `@@`, so a removed line
        # whose own text begins with `---` cannot be mistaken for one.
        if line.startswith("diff --git "):
            current, old_path, in_hunks = None, None, False
            continue
        if not in_hunks:
            if line.startswith("--- "):
                old_path = diff_path(line[4:])
            elif line.startswith("+++ "):
                current = diff_path(line[4:]) or old_path
                if current and SOURCE_RE.search(current):
                    files.add(current)
            elif line.startswith("@@"):
                in_hunks = True
            continue
        # A symbol defined in a test file is test scaffolding, not API. Its
        # callers are the test itself, and mapping them tells the reader nothing
        # about what production code can break.
        if not current or not SOURCE_RE.search(current) or TEST_RE.search(current):
            continue
        m = DEFINITION_RE.match(line)
        if m:
            name = next((g for g in m.groups() if g), None)
            if name and name.lower() not in TOO_COMMON and len(name) > 2:
                symbols.add((name, current))
    return symbols, files


def imported_names(root: str) -> set[str]:
    """Every identifier some file imports by name.

    The public-surface test for languages with no export keyword — see
    NEEDS_IMPORT_PROOF. Collected once over the whole tree, because a symbol is
    public if *anyone* imports it, not if its own module says so.
    """
    found: set[str] = set()
    for rel in walk_sources(root):
        try:
            with open(rel, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for line in lines:
            m = IMPORTED_NAME_RE.match(line)
            if not m:
                continue
            clause = m.group(1) or m.group(2) or ""
            for token in re.split(r"[,\s()]+", clause):
                token = token.strip().strip("\\")
                if token and token not in ("as", "import", "from", "*"):
                    found.add(token.split(".")[-1])
    return found


def walk_sources(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            if SOURCE_RE.search(rel) and not SKIP_RE.search(f"/{rel}"):
                out.append(rel)
    return out


def has_paired_test(rel: str, all_files: set[str]) -> bool:
    if TEST_RE.search(rel):
        return True
    stem, _ = os.path.splitext(rel)
    return any(
        f"{stem}{suffix}" in all_files
        for suffix in (".test.ts", ".test.tsx", ".spec.ts", ".test.js", ".spec.js", "_test.py", "_test.go")
    )


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else default_base()
    root = git(["rev-parse", "--show-toplevel"]).strip() or os.getcwd()
    os.chdir(root)

    defined, touched = changed_symbols(base)

    # Apply the second gate only where the language needs it, and only once the
    # tree has been scanned — a Python `def` nobody imports is a private helper,
    # whatever its indentation says.
    if any(path.endswith(NEEDS_IMPORT_PROOF) for _, path in defined):
        importable = imported_names(root)
        symbols = {
            name for name, path in defined
            if not path.endswith(NEEDS_IMPORT_PROOF) or name in importable
        }
        dropped = len(defined) - len(symbols)
    else:
        symbols = {name for name, _ in defined}
        dropped = 0

    print(f"base: {base}")
    if dropped:
        print(
            f"({dropped} changed definition(s) in export-less languages are imported "
            "nowhere — private helpers, no radius outside their own file)"
        )
    if not symbols:
        print(
            "No changed symbol definitions found in this diff.\n"
            "The change may be behaviour-only inside existing functions — in which case "
            "map the radius of the enclosing function by name instead."
        )
        return 0

    print(f"{len(symbols)} changed symbol(s): {', '.join(sorted(symbols))}\n")

    sources = walk_sources(root)
    all_files = set(sources)
    radius: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    patterns = {s: re.compile(rf"\b{re.escape(s)}\b") for s in symbols}
    for rel in sources:
        if rel in touched:
            continue
        try:
            with open(rel, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for sym, pattern in patterns.items():
                if pattern.search(line):
                    kind = "re-export" if RE_EXPORT_RE.match(line) else "direct"
                    radius[sym].append((rel, i, kind))

    for sym in sorted(symbols, key=lambda s: -len(radius[s])):
        sites = radius[sym]
        print(f"── {sym}: {len(sites)} reference(s) outside the diff ──")
        if not sites:
            print("   none. Nothing outside this diff names it.\n")
            continue
        if len(sites) > NOISE_THRESHOLD:
            print(
                f"   too common to map — {len(sites)} references means this name is a "
                "word, not an interface.\n   Narrow it by hand (search the import, not "
                "the identifier) if the change is behavioural.\n"
            )
            continue
        untested = 0
        for rel, line_no, kind in sites[:25]:
            tested = has_paired_test(rel, all_files)
            if not tested:
                untested += 1
            mark = "  " if tested else "!!"
            print(f"   {mark} [{kind:>9}] {rel}:{line_no}")
        if len(sites) > 25:
            print(f"      … and {len(sites) - 25} more")
        print(f"   {untested} of the shown call sites are in files with no paired test\n")

    print(
        "!! marks a call site with no paired test — a regression there ships silently.\n"
        "\nBlind spots this search cannot cover, every run: dynamic dispatch, "
        "string-keyed lookup, reflection, serialized boundaries, and consumers in other "
        "repositories. Say so in your report; do not present this map as complete."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
