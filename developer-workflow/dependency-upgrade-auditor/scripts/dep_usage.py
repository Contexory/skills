#!/usr/bin/env python3
"""Extract the surface of a dependency that a repository actually uses.

An upgrade decision needs the intersection of the package's breaking changes and
your import list. This produces the second half of that intersection: declared
range, importing files, and the specific names in use.

    python3 dep_usage.py <package>     # one package, in detail
    python3 dep_usage.py --all         # every direct dependency, ranked by use

Handles JS/TS (`import`/`require`) and Python (`import`/`from`). Standard library
only; nothing is installed, fetched or modified.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SOURCE_RE = re.compile(r"\.(ts|tsx|js|jsx|mjs|cjs|py)$")
SKIP_RE = re.compile(r"(^|/)(node_modules|dist|build|\.next|coverage|vendor|__pycache__)(/|$)")

MANIFEST_FIELDS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def git_root() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return out.stdout.strip() or os.getcwd()


def manifests(root: str) -> list[str]:
    """Every package.json in the tree, so a monorepo reports per-workspace ranges."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        if "package.json" in filenames:
            found.append(os.path.join(dirpath, "package.json"))
    return found


def declared(root: str, package: str) -> list[tuple[str, str, str]]:
    """(manifest, field, range) for each declaration of `package`."""
    rows = []
    for path in manifests(root):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        for field in MANIFEST_FIELDS:
            spec = (data.get(field) or {}).get(package)
            if spec:
                rows.append((os.path.relpath(path, root), field, spec))
    return rows


def sources(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            if SOURCE_RE.search(rel) and not SKIP_RE.search(f"/{rel}"):
                out.append(rel)
    return out


def usage(root: str, package: str) -> tuple[dict[str, list[int]], set[str], set[str]]:
    """(files → line numbers, named imports, subpath imports)."""
    esc = re.escape(package)
    patterns = [
        # import { a, b } from "pkg" / import x from "pkg/sub"
        re.compile(rf"""import\s+(?P<names>[^'"]+?)\s+from\s+['"](?P<path>{esc}(?:/[^'"]*)?)['"]"""),
        # const { a } = require("pkg")
        re.compile(rf"""(?P<names>(?:const|let|var)\s+[^=]+?)=\s*require\(['"](?P<path>{esc}(?:/[^'"]*)?)['"]\)"""),
        # bare side-effect import
        re.compile(rf"""import\s+['"](?P<path>{esc}(?:/[^'"]*)?)['"]"""),
        # python: from pkg.sub import a, b
        re.compile(rf"""from\s+(?P<path>{esc}(?:\.[\w.]+)?)\s+import\s+(?P<names>.+)"""),
        re.compile(rf"""import\s+(?P<path>{esc}(?:\.[\w.]+)?)\s*$"""),
    ]

    files: dict[str, list[int]] = defaultdict(list)
    names: set[str] = set()
    subpaths: set[str] = set()

    for rel in sources(root):
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                m = pattern.search(line)
                if not m:
                    continue
                files[rel].append(i)
                path = m.groupdict().get("path") or ""
                if path and path not in (package,):
                    subpaths.add(path)
                raw = m.groupdict().get("names") or ""
                for token in re.split(r"[{},*\s]+|as\s+", raw):
                    token = token.strip().strip(";")
                    if token and token not in ("const", "let", "var", "import", "from", "type", "default"):
                        names.add(token)
                break
    return files, names, subpaths


# Module specifiers, split into two passes rather than one alternation.
#
# They cannot share a regex. Alternation is resolved leftmost-first, not
# best-first, so on `import yaml from "js-yaml"` the unquoted Python branch
# matched at column 0 and captured the *binding* `yaml` — the quoted branch was
# never reached. The survey then reported `js-yaml` as imported by zero files and
# printed "usually a build-time or transitive-only dependency", which is the
# worst possible answer from a tool whose job is upgrade safety.
#
# Quoted specifiers are unambiguous, so they are tried first and win outright.
QUOTED_SPECIFIER_RE = re.compile(
    r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]"""
    r"""|require\(\s*['"]([^'"]+)['"]\s*\)"""
)
# Only then the unquoted Python form, and only when the line carries no quote at
# all — `import x from "pkg"` is JavaScript however much its prefix looks like
# Python.
PY_IMPORT_RE = re.compile(r"""^\s*(?:from|import)\s+([A-Za-z_][\w.]*)(?![^\n'"]*['"])""")
IMPORT_NAMES_RE = re.compile(r"""import\s+(?:type\s+)?\{([^}]*)\}|import\s+(?:type\s+)?(\w+)\s+from""")


def package_of(specifier: str) -> str | None:
    """Map a module specifier to the package that owns it.

    `@scope/pkg/sub` → `@scope/pkg`; `pkg/sub` → `pkg`; `pkg.sub` (Python) →
    `pkg`. A relative specifier belongs to no package and returns None.
    """
    if not specifier or specifier.startswith(("." , "/")) or specifier.startswith("node:"):
        return None
    if "." in specifier and "/" not in specifier and not specifier.startswith("@"):
        return specifier.split(".", 1)[0]
    parts = specifier.split("/")
    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else specifier
    return parts[0]


def scan_all(root: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Single pass: package → importing files, and package → named imports."""
    files: dict[str, set[str]] = defaultdict(set)
    names: dict[str, set[str]] = defaultdict(set)

    for rel in sources(root):
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
                content = handle.read()
        except OSError:
            continue
        for line in content.splitlines():
            m = QUOTED_SPECIFIER_RE.search(line) or PY_IMPORT_RE.search(line)
            if not m:
                continue
            specifier = next((g for g in m.groups() if g), "")
            package = package_of(specifier)
            if not package:
                continue
            files[package].add(rel)
            n = IMPORT_NAMES_RE.search(line)
            if n:
                raw = n.group(1) or n.group(2) or ""
                for token in re.split(r"[,\s]+|as\s+", raw):
                    token = token.strip()
                    if token and token not in ("type", "default"):
                        names[package].add(token)
    return files, names


def report_one(root: str, package: str) -> int:
    decls = declared(root, package)
    files, names, subpaths = usage(root, package)

    print(f"package: {package}\n")
    if decls:
        print("declared:")
        for manifest, field, spec in decls:
            print(f"  {spec:<16} {field:<18} {manifest}")
    else:
        print("declared: not found in any package.json (transitive, or not a JS package)")

    total = sum(len(v) for v in files.values())
    print(f"\nimported in {len(files)} file(s), {total} import site(s)")
    for rel in sorted(files)[:30]:
        print(f"  {rel}:{','.join(str(n) for n in files[rel][:6])}")
    if len(files) > 30:
        print(f"  … and {len(files) - 30} more files")

    if subpaths:
        print("\nsubpath imports (each is its own compatibility surface):")
        for path in sorted(subpaths):
            print(f"  {path}")

    print(f"\nnamed imports in use ({len(names)}):")
    print("  " + (", ".join(sorted(names)) if names else "(none — side-effect or default import only)"))

    print(
        "\nThis is the list to check the changelog against. A breaking change that "
        "touches none of these names does not apply to you — count it and move on.\n"
        "Names alone cannot catch a changed default under an unchanged signature; "
        "check behaviour changes separately."
    )
    return 0


def report_all(root: str) -> int:
    seen: dict[str, str] = {}
    for path in manifests(root):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        for field in ("dependencies", "devDependencies"):
            for name, spec in (data.get(field) or {}).items():
                seen.setdefault(name, spec)

    if not seen:
        print("No package.json dependencies found.")
        return 0

    print(f"{len(seen)} direct dependencies\n")
    # One pass over the tree, attributing every import to a package — not one
    # pass per package. The naive form was O(files × dependencies) and took 94
    # seconds on a 112-dependency monorepo, which is long enough that nobody
    # runs the survey twice.
    per_files, per_names = scan_all(root)
    rows = [
        (name, seen[name], len(per_files.get(name, ())), len(per_names.get(name, ())))
        for name in seen
    ]
    rows.sort(key=lambda r: -r[2])

    print(f"{'files':>6}  {'names':>6}  {'range':<16} package")
    for name, spec, n_files, n_names in rows:
        print(f"{n_files:>6}  {n_names:>6}  {spec:<16} {name}")
    print("\nZero files usually means a build-time or transitive-only dependency.")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <package>|--all", file=sys.stderr)
        return 64
    root = git_root()
    return report_all(root) if sys.argv[1] == "--all" else report_one(root, sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
