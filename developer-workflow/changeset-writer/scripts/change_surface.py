#!/usr/bin/env python3
"""Report what a diff did to the public surface, and how this repo writes releases.

The bump belongs to the surface change, not to the diff size, so this reports the
surface change: exports added, removed and signature-altered, per package, with
each package marked published or private. It also detects the release convention
already in use and prints recent entries to match.

    python3 change_surface.py [base-ref]

It classifies nothing on its own — a removed export is reported as removed, and
whether that is major is a judgement the caller makes with the deprecation
history in view. Standard library only; nothing is written.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SOURCE_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs)$")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.(py|go)$")
SKIP_RE = re.compile(r"(^|/)(node_modules|dist|build|\.next|coverage|vendor)(/|$)")

EXPORT_RE = re.compile(
    r"^[+-]export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:function|const|let|var|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)"
    r"|^[+-]pub\s+(?:fn|struct|trait|enum)\s+([A-Za-z_][\w]*)"
    r"|^[+-]func\s+([A-Z][\w]*)"
)


def git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def diff_path(header: str) -> str | None:
    """Path from a `---`/`+++` header line, or None for `/dev/null`.

    A **deleted** file's `+++` is `/dev/null` and its only name is on the `---`
    line. Reading `+++ b/` alone leaves the parser pointed at the previous file,
    so a deleted module's removed exports are attributed to whichever package
    was parsed before it — a major-bump signal against the wrong package, while
    the package that actually lost the export never appears at all.
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


def owning_package(root: str, rel: str) -> tuple[str, str, bool]:
    """(package dir, package name, published) for the file's nearest manifest."""
    parts = rel.split("/")
    for i in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:i])
        manifest = os.path.join(root, candidate, "package.json")
        if os.path.isfile(manifest):
            try:
                with open(manifest, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                return candidate, candidate, False
            return candidate, data.get("name") or candidate, not data.get("private", False)
    return ".", "(root)", False


def has_prose(blob: str) -> bool:
    """True when a changeset carries a body, not just empty frontmatter."""
    body = re.sub(r"^---[\s\S]*?---", "", blob, count=1).strip()
    return len(body) > 20


def detect_convention(root: str) -> tuple[str, list[str]]:
    """(convention name, recent example entries)."""
    changeset_dir = os.path.join(root, ".changeset")
    if os.path.isdir(changeset_dir):
        examples = []
        # Recent merged changesets are deleted on release, so the git history is
        # the only reliable source of house voice for a repo that has shipped.
        log = git(["log", "-40", "--diff-filter=A", "--name-only", "--format=", "--", ".changeset"])
        # `.changeset/README.md` is the Changesets boilerplate, not an example of
        # anyone's house voice. The directory listing below already excludes it;
        # this loop has to as well, or a young repo — one whose last 40 additions
        # still reach the initial commit — hands the reader the boilerplate and
        # tells them to match its voice.
        for path in [p for p in log.splitlines()
                     if p.endswith(".md") and os.path.basename(p) != "README.md"]:
            if len(examples) >= 4:
                break
            # A released changeset is deleted from HEAD, so `git show HEAD:path`
            # returns nothing. Only entries with prose survive — an empty
            # `---\n---` example teaches the reader nothing about house voice and
            # actively muddies the pattern they are asked to match.
            blob = (git(["show", f"HEAD:{path}"]) or "").strip()
            # An unreleased changeset is reachable both from history and from the
            # directory listing below; without this it is printed twice and reads
            # as though the repo repeats itself.
            if has_prose(blob) and blob not in examples:
                examples.append(blob)
        for name in sorted(os.listdir(changeset_dir)):
            if not name.endswith(".md") or name == "README.md" or len(examples) >= 4:
                continue
            with open(os.path.join(changeset_dir, name), encoding="utf-8") as handle:
                blob = handle.read().strip()
            if has_prose(blob) and blob not in examples:
                examples.append(blob)
        return "Changesets (.changeset/*.md)", examples

    for name in ("CHANGELOG.md", "CHANGES.md", "HISTORY.md"):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                head = handle.read(2500)
            return f"hand-maintained {name}", [head]

    subjects = [s for s in git(["log", "-20", "--format=%s"]).splitlines() if s]
    conventional = sum(
        1 for s in subjects if re.match(r"^(feat|fix|chore|docs|refactor|test|perf|build|ci)(\(.+\))?!?:", s)
    )
    if subjects and conventional / len(subjects) > 0.6:
        return "Conventional Commits (no changeset system detected)", subjects[:6]

    return "NONE DETECTED", subjects[:6]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else default_base()
    root = git(["rev-parse", "--show-toplevel"]).strip() or os.getcwd()
    os.chdir(root)

    added: dict[str, set[str]] = defaultdict(set)
    removed: dict[str, set[str]] = defaultdict(set)
    touched: dict[str, tuple[str, bool]] = {}
    current_pkg: str | None = None
    old_path: str | None = None
    in_hunks = False

    for line in git(["diff", "--unified=0", base, "--"]).splitlines():
        # Headers are read only before a file's first `@@`, so a removed line
        # whose own text begins with `---` cannot be mistaken for one. The file
        # is resolved once here rather than per line, which also spares
        # `owning_package` a filesystem walk for every line of the diff.
        if line.startswith("diff --git "):
            current_pkg, old_path, in_hunks = None, None, False
            continue
        if not in_hunks:
            if line.startswith("--- "):
                old_path = diff_path(line[4:])
            elif line.startswith("+++ "):
                current_pkg = None
                path = diff_path(line[4:]) or old_path
                if path and not SKIP_RE.search(f"/{path}"):
                    pkg_dir, pkg_name, published = owning_package(root, path)
                    touched.setdefault(pkg_dir, (pkg_name, published))
                    # Exports declared in a test file are scaffolding, not
                    # public surface, so the package is recorded as touched but
                    # its symbols are not read.
                    if SOURCE_RE.search(path) and not TEST_RE.search(path):
                        current_pkg = pkg_dir
            elif line.startswith("@@"):
                in_hunks = True
            continue
        if current_pkg is None:
            continue
        m = EXPORT_RE.match(line)
        if not m:
            continue
        symbol = next((g for g in m.groups() if g), None)
        if not symbol:
            continue
        (added if line.startswith("+") else removed)[current_pkg].add(symbol)

    print(f"base: {base}\n")
    if not touched:
        print("No files changed against this base.")
        return 0

    print("── packages touched ──")
    for pkg_dir, (name, published) in sorted(touched.items()):
        flag = "published" if published else "private"
        print(f"  [{flag:>9}] {name}  ({pkg_dir})")

    print("\n── public surface delta ──")
    any_surface = False
    for pkg_dir, (name, published) in sorted(touched.items()):
        new = added[pkg_dir] - removed[pkg_dir]
        gone = removed[pkg_dir] - added[pkg_dir]
        changed = added[pkg_dir] & removed[pkg_dir]
        if not (new or gone or changed):
            continue
        any_surface = True
        print(f"\n  {name} ({'published' if published else 'private'})")
        if gone:
            print(f"    REMOVED   {', '.join(sorted(gone))}")
        if changed:
            print(f"    CHANGED   {', '.join(sorted(changed))}   (definition line edited)")
        if new:
            print(f"    ADDED     {', '.join(sorted(new))}")

    if not any_surface:
        print(
            "  None. No exported symbol was added, removed or redefined.\n"
            "  On surface alone this is a patch — but a changed default or behaviour "
            "under an unchanged signature is invisible here. Check before concluding."
        )

    convention, examples = detect_convention(root)
    print(f"\n── release convention ──\n  {convention}")
    if convention == "NONE DETECTED":
        print(
            "  No changeset directory, changelog file, or consistent commit convention.\n"
            "  Ask before introducing one — do not create .changeset/ unprompted."
        )
    for i, example in enumerate(examples[:3], 1):
        snippet = "\n    ".join(example.splitlines()[:8])
        print(f"\n  example {i}:\n    {snippet}")

    print(
        "\nMatch the voice of the examples above. Bump from the surface delta, not the "
        "diff size: removed or narrowed = major, added only = minor, no delta = patch."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
