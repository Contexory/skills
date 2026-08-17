#!/usr/bin/env python3
"""Report what a repository is, from its manifests and its history.

The mechanical half of onboarding: stack, workspaces, declared commands, entry
points, the files that actually change, and where the conventions are written
down. Everything here is observed — a missing test command is reported missing
rather than filled in with a plausible default, because a newcomer cannot tell
the difference between the two and will run whatever they are given.

    python3 repo_map.py [--top 15] [--since 1.year] [--root .]

Standard library only. Reads; never installs, builds or executes project code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter

SKIP_RE = re.compile(
    r"(^|/)(node_modules|dist|build|\.next|coverage|vendor|__pycache__|\.git|\.turbo)(/|$)"
)

# Manifest → the stack it implies. Order matters only for display.
STACK_MANIFESTS = {
    "package.json": "JavaScript / TypeScript",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "Gemfile": "Ruby",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "composer.json": "PHP",
    "*.csproj": ".NET",
}

INSTRUCTION_FILES = (
    "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "CONVENTIONS.md",
    ".cursorrules", ".windsurfrules", "GEMINI.md", ".github/copilot-instructions.md",
)

ENTRY_HINTS = (
    "main.py", "__main__.py", "main.go", "main.rs", "index.ts", "index.js",
    "app.py", "server.ts", "server.js", "cli.ts", "cli.py", "Makefile", "Dockerfile",
)

# Command scripts worth surfacing, in the order a newcomer needs them.
COMMAND_KEYS = ("install", "setup", "dev", "start", "build", "test", "lint", "typecheck", "migrate")


def git(args: list[str], root: str) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=root)
    return out.stdout if out.returncode == 0 else ""


def in_dot_dir(rel: str) -> bool:
    """True when any *directory* component is a dot-directory.

    Dot-*files* are kept — `.env.example` and `.gitignore` are things a newcomer
    should see. `.git` alone was not enough to prune: `.worktrees/` holds entire
    extra checkouts, and because it sorts first its duplicate packages displaced
    the real ones in every capped list on the way out, so the map reported 116k
    files and 25 workspace packages that were all copies. Instruction files under
    `.github/` are probed by name against `root`, never found by this scan, so
    nothing downstream depends on descending into one.
    """
    return any(part.startswith(".") for part in rel.split("/")[:-1])


def walk(root: str) -> list[str]:
    """Files worth mapping — the tracked ones, when this is a git repository.

    `git ls-files` is what "tracked-ish" actually means, and a filesystem walk
    cannot approximate it. A build directory that is generated, gitignored, and
    carries its own `package.json` gets reported as a workspace package
    duplicating the real one. `SKIP_RE` cannot fix that by name: `pkg/` is build
    output in one project and a legitimate source directory in Go, and only the
    repository knows which one it is looking at. `ls-files` prints paths
    relative to the directory it runs in, which is already `root`.

    Falls back to a filesystem walk outside a repository, since a skill has to
    give value on first run rather than refuse.
    """
    listed = git(["ls-files"], root)
    if listed.strip():
        return [
            rel
            for rel in (line.strip() for line in listed.splitlines())
            if rel and not in_dot_dir(rel) and not SKIP_RE.search(f"/{rel}")
        ]

    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            if not SKIP_RE.search(f"/{rel}"):
                out.append(rel)
    return out


def detect_stack(files: list[str]) -> list[str]:
    found = []
    names = {os.path.basename(f) for f in files}
    for manifest, stack in STACK_MANIFESTS.items():
        if manifest.startswith("*"):
            if any(f.endswith(manifest[1:]) for f in files):
                found.append(f"{stack} (*{manifest[1:]})")
        elif manifest in names:
            found.append(f"{stack} ({manifest})")
    return found


def root_package(root: str) -> dict:
    path = os.path.join(root, "package.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def workspaces(root: str, files: list[str]) -> list[tuple[str, str]]:
    """(path, name) for each nested package.json — the real shape of a monorepo."""
    out = []
    for rel in files:
        if os.path.basename(rel) != "package.json" or rel == "package.json":
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        out.append((os.path.dirname(rel), data.get("name") or "(unnamed)"))
    return sorted(out)


def hot_files(root: str, since: str, top: int) -> list[tuple[str, int]]:
    # `git log --name-only` prints repo-root-relative paths from any directory,
    # unlike `git ls-files` above, which prints them relative to the cwd. Mixing
    # the two spaces made `--root <subdir>` report a header naming one root and a
    # most-changed list naming files from elsewhere in the repository.
    top_level = git(["rev-parse", "--show-toplevel"], root).strip()
    prefix = ""
    if top_level:
        rel_root = os.path.relpath(root, top_level).replace("\\", "/")
        if rel_root not in (".", ""):
            prefix = f"{rel_root}/"

    log = git(["log", f"--since={since}", "--name-only", "--format=", "--", "."], root)
    counts: Counter[str] = Counter()
    for line in log.splitlines():
        rel = line.strip()
        if not rel:
            continue
        if prefix:
            if not rel.startswith(prefix):
                continue
            rel = rel[len(prefix) :]
        if not SKIP_RE.search(f"/{rel}"):
            counts[rel] += 1
    # Lockfiles and changelogs churn constantly and teach a newcomer nothing.
    for noisy in list(counts):
        if os.path.basename(noisy) in ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "CHANGELOG.md"):
            del counts[noisy]
    return counts.most_common(top)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--since", default="1.year")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = walk(root)

    print(f"root: {root}")
    print(f"{len(files)} tracked-ish files (excluding build output and vendored code)\n")

    print("── stack ──")
    stack = detect_stack(files)
    print("\n".join(f"  {s}" for s in stack) if stack else "  no recognised manifest")

    pkg = root_package(root)
    if pkg:
        print("\n── declared commands (root package.json) ──")
        scripts = pkg.get("scripts") or {}
        shown = [k for k in COMMAND_KEYS if k in scripts]
        for key in shown:
            print(f"  {key:<10} {scripts[key]}")
        missing = [k for k in ("dev", "test", "build") if k not in scripts]
        if missing:
            print(f"  MISSING: no {', '.join(missing)} script declared — do not assume one exists")
        extra = [k for k in scripts if k not in shown]
        if extra:
            print(f"  ({len(extra)} other scripts: {', '.join(sorted(extra)[:12])})")

    ws = workspaces(root, files)
    if ws:
        print(f"\n── workspace packages ({len(ws)}) ──")
        for path, name in ws[:25]:
            print(f"  {name:<32} {path}")
        if len(ws) > 25:
            print(f"  … and {len(ws) - 25} more")

    print("\n── instruction files (read these first) ──")
    present = [f for f in INSTRUCTION_FILES if os.path.isfile(os.path.join(root, f))]
    print("\n".join(f"  {f}" for f in present) if present else "  none found")

    print("\n── entry-point candidates ──")
    entries = [f for f in files if os.path.basename(f) in ENTRY_HINTS and f.count("/") <= 3]
    print("\n".join(f"  {f}" for f in sorted(entries)[:20]) if entries else "  none matched the usual names")

    print(f"\n── most-changed files (since {args.since}) ──")
    hot = hot_files(root, args.since, args.top)
    if hot:
        for rel, n in hot:
            print(f"  {n:>4}  {rel}")
    else:
        print("  no git history in window")

    docs = sorted({f for f in files if re.search(r"(^|/)docs?/", f) and f.endswith((".md", ".mdx"))})
    print(f"\n── docs ({len(docs)}) ──")
    print("\n".join(f"  {d}" for d in docs[:15]) if docs else "  none under docs/")
    if len(docs) > 15:
        print(f"  … and {len(docs) - 15} more")

    print(
        "\nRead the instruction files, then the top five most-changed files. Anything you "
        "could not determine belongs in 'open questions' rather than in a confident "
        "paragraph — and no command above has been executed to verify it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
