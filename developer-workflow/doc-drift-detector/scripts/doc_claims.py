#!/usr/bin/env python3
"""Extract a document's checkable claims and resolve each against the repository.

Paths, commands, symbols and version floors are the claims that can be verified
mechanically, and they are the lines readers copy and run. Prose is left alone —
this reports `OK`, `STALE` or `UNCHECKABLE` per claim and never an opinion.

    python3 doc_claims.py README.md
    python3 doc_claims.py docs/ --recursive

`UNCHECKABLE` is a first-class result rather than a quiet stale: a claim the
extractor could not resolve is not evidence of drift, and merging the two is the
fastest way to lose a reader who checks the first finding by hand.
Standard library only; nothing is written or executed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

SKIP_RE = re.compile(r"(^|/)(node_modules|dist|build|\.next|coverage|vendor|\.git)(/|$)")

# A path-shaped token: has a slash or a known extension, no spaces.
PATH_RE = re.compile(r"`([A-Za-z0-9_./@-]+/[A-Za-z0-9_./@-]+|[A-Za-z0-9_.-]+\.[a-z]{2,4})`")
# `pnpm test`, `npm run build`, `make deploy`, `yarn lint`
COMMAND_RE = re.compile(r"`(?:(npm|pnpm|yarn|bun)\s+(?:run\s+)?([\w:-]+)|(make)\s+([\w:-]+))[^`]*`")
# An identifier in inline code that looks like a symbol rather than prose.
SYMBOL_RE = re.compile(r"`([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*|[A-Z][a-zA-Z0-9]{2,})`")
# "Node 18+", "requires Python 3.11", "node >= 20"
VERSION_RE = re.compile(
    r"\b(node|python|go|rust|java|deno|bun)\s*(?:>=|>|v|version\s*)?\s*(\d+(?:\.\d+)*)\s*\+?",
    re.IGNORECASE,
)

# Placeholders that are examples by construction, never real paths.
PLACEHOLDER_RE = re.compile(
    r"(your-|my-|example|foo|bar|baz|<[^>]+>|\.\.\.|path/to|somewhere)", re.IGNORECASE
)

DOC_EXT = (".md", ".mdx", ".rst", ".txt")

# Real file extensions. The path pattern's second branch matches anything shaped
# like `name.ext`, which swept up member expressions — `t.rich`, `DocsTable.head`,
# `typescript.sys` — and reported each as a missing file.
KNOWN_EXT = {
    "ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "md", "mdx", "yml", "yaml",
    "toml", "lock", "sh", "bash", "py", "go", "rs", "rb", "java", "kt", "css",
    "scss", "html", "xml", "svg", "png", "jpg", "webp", "sql", "txt",
    "cfg", "ini", "conf", "prisma", "graphql", "proto", "csv", "pdf", "d",
}

# Package-manager words that follow the runner but are not script names. Without
# these, `pnpm exec turbo run typecheck` reports `exec` as a missing script.
NOT_SCRIPTS = {
    "exec", "dlx", "install", "add", "remove", "why", "run", "create", "init",
    "publish", "pack", "link", "update", "outdated", "audit", "list", "ls", "test",
}


def index_paths(root: str) -> dict[str, list[str]]:
    """Every repository path, bucketed by last segment for suffix resolution.

    Docs routinely write a path relative to a package rather than to the
    repository — `components/button.tsx` meaning `src/ui/components/button.tsx`.
    Treating those as missing produced most of the false positives in the first
    run, and a drift report that is mostly false positives is worse than none.
    """
    buckets: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        for name in list(dirnames) + list(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            buckets.setdefault(name, []).append(rel)
    return buckets


def dependency_names(root: str) -> set[str]:
    """Declared dependencies, so a module specifier is never read as a path."""
    names: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        if "package.json" not in filenames:
            continue
        try:
            with open(os.path.join(dirpath, "package.json"), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        for field in ("dependencies", "devDependencies", "peerDependencies"):
            names.update((data.get(field) or {}).keys())
        if data.get("name"):
            names.add(data["name"])
    return names


def classify_path(claim: str, root: str, doc_dir: str, paths: dict[str, list[str]], deps: set[str]):
    """(verdict, detail) for a path-shaped claim.

    The order matters. Anything that is not a filesystem path at all — a module
    specifier, an alias, a relative import, a URL route — is `UNCHECKABLE`
    rather than `STALE`, because the extractor has no business asserting drift
    about a string it cannot resolve by design.
    """
    if claim.startswith(("@/", "~/", "./", "../")):
        return "UNCHECKABLE", f"{claim} (import specifier or alias, not a filesystem path)"
    if claim.startswith("@"):
        return "UNCHECKABLE", f"{claim} (scoped package name)"
    head = claim.split("/")[0]
    if head in deps:
        return "UNCHECKABLE", f"{claim} (module specifier for a declared dependency)"
    if claim.startswith("/") and "." not in os.path.basename(claim.rstrip("/")):
        return "UNCHECKABLE", f"{claim} (URL path, not a file)"

    # A leading `/` is a URL route or an absolute path from another machine —
    # never a path relative to this checkout. It still gets probed as
    # repo-relative, so a doc writing `/src/server/proxy.ts` resolves, but the
    # leading slash has to come off first: `os.path.join(root, "/docs/x.md")`
    # discards `root` and probes the real filesystem root instead.
    rooted = claim.lstrip("/")

    if os.path.exists(os.path.join(root, rooted)) or os.path.exists(os.path.join(doc_dir, rooted)):
        return "OK", claim

    trimmed = rooted.rstrip("/")
    last = trimmed.split("/")[-1]
    for candidate in paths.get(last, ()):
        if candidate == trimmed or candidate.endswith("/" + trimmed):
            return "OK", f"{claim} → {candidate}"

    if PLACEHOLDER_RE.search(claim):
        return "UNCHECKABLE", f"{claim} (looks like a placeholder)"

    # Precision over recall, deliberately. An unresolved token with no file
    # extension is more often a lint-rule id (`react-hooks/exhaustive-deps`), a
    # module specifier, or a path the prose is discussing in the past tense than
    # it is live drift. Calling those STALE cost 100+ false positives on one
    # well-maintained file; the trade is that a renamed extensionless directory
    # is now reported as uncheckable rather than stale.
    ext = os.path.splitext(claim.rstrip("/"))[1].lstrip(".").lower()
    if ext not in KNOWN_EXT:
        return "UNCHECKABLE", f"{claim} (unresolved, no file extension — rule id, specifier, or historical reference)"

    # STALE is reserved for the highest-confidence class: a path with directory
    # context whose first segment is a real top-level entry here. Everything else
    # measured as a false positive on a maintained file — `lib/version.cjs` was a
    # dependency's internal export, `sitemap.xml` generated output, `notes.md` an
    # illustrative rename. A bare filename with no directory context is too weak a
    # claim to assert drift on.
    if "/" not in claim:
        return "UNCHECKABLE", f"{claim} (bare filename, no directory context — often illustrative or generated)"
    # An unresolved leading-slash claim is unattributable by construction: a URL
    # route that happens to end in an extension — a site serving `.md` twins at
    # `/docs/<slug>.md`, say — is indistinguishable from a real absolute path,
    # and asserting drift on either would be the false-positive class this
    # function is ordered to avoid.
    if claim.startswith("/"):
        return "UNCHECKABLE", f"{claim} (leading slash — a URL route or another machine's absolute path)"
    if not os.path.exists(os.path.join(root, claim.split("/")[0])):
        return "UNCHECKABLE", f"{claim} (first segment is not a top-level entry here — likely another project's path)"

    return "STALE", f"{claim} — no such file or directory"


def git_root() -> str:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return out.stdout.strip() or os.getcwd()


def load_scripts(root: str) -> set[str]:
    """Every script name declared in any package.json, plus Makefile targets."""
    names: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        if "package.json" in filenames:
            try:
                with open(os.path.join(dirpath, "package.json"), encoding="utf-8") as handle:
                    names.update((json.load(handle).get("scripts") or {}).keys())
            except (OSError, json.JSONDecodeError):
                pass
        if "Makefile" in filenames:
            try:
                with open(os.path.join(dirpath, "Makefile"), encoding="utf-8") as handle:
                    for line in handle:
                        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)", line)
                        if m:
                            names.add(m.group(1))
            except OSError:
                pass
    return names


def index_symbols(root: str) -> set[str]:
    """Exported identifiers across the repository, for symbol resolution."""
    found: set[str] = set()
    pattern = re.compile(
        r"^\s*(?:export\s+(?:default\s+)?(?:async\s+)?"
        r"(?:function|const|let|var|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)"
        r"|def\s+([a-z_][\w]*)"
        r"|(?:pub\s+)?(?:fn|struct|trait)\s+([A-Za-z_][\w]*))"
    )
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
        for name in filenames:
            if not name.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".py", ".go", ".rs")):
                continue
            try:
                with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        m = pattern.match(line)
                        if m:
                            found.add(next(g for g in m.groups() if g))
            except OSError:
                continue
    return found


def runtime_floor(root: str) -> dict[str, str]:
    """Declared runtime minimums, for comparison against documented ones."""
    floors: dict[str, str] = {}
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg, encoding="utf-8") as handle:
                engines = (json.load(handle).get("engines") or {})
            for name, spec in engines.items():
                m = re.search(r"(\d+(?:\.\d+)*)", str(spec))
                if m:
                    floors[name.lower()] = m.group(1)
        except (OSError, json.JSONDecodeError):
            pass
    nvmrc = os.path.join(root, ".nvmrc")
    if os.path.isfile(nvmrc):
        with open(nvmrc, encoding="utf-8") as handle:
            m = re.search(r"(\d+(?:\.\d+)*)", handle.read())
            if m:
                floors.setdefault("node", m.group(1))
    return floors


def check_doc(path: str, root: str, scripts: set[str], symbols: set[str],
              floors: dict[str, str], paths: dict[str, list[str]], deps: set[str]):
    rel_doc = os.path.relpath(path, root)
    doc_dir = os.path.dirname(path)
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()

    results: list[tuple[int, str, str, str]] = []  # (line, verdict, kind, detail)

    for i, line in enumerate(lines, 1):
        for m in PATH_RE.finditer(line):
            claim = m.group(1)
            # `t.rich` is a member expression, not a file. Only the slash form or
            # a genuine extension makes it past here.
            if "/" not in claim and os.path.splitext(claim)[1].lstrip(".").lower() not in KNOWN_EXT:
                continue
            verdict, detail = classify_path(claim, root, doc_dir, paths, deps)
            results.append((i, verdict, "path", detail))

        for m in COMMAND_RE.finditer(line):
            name = m.group(2) or m.group(4)
            runner = m.group(1) or m.group(3)
            if not name or name in NOT_SCRIPTS or name.startswith("-"):
                continue
            if name in scripts:
                results.append((i, "OK", "command", f"{runner} {name}"))
            else:
                results.append((i, "STALE", "command", f"{runner} {name} — no such script or target"))

        for m in SYMBOL_RE.finditer(line):
            claim = m.group(1)
            if claim in symbols:
                results.append((i, "OK", "symbol", claim))
            else:
                results.append((i, "UNCHECKABLE", "symbol", f"{claim} (not an export here — may be a dependency's)"))

        for m in VERSION_RE.finditer(line):
            runtime, documented = m.group(1).lower(), m.group(2)
            actual = floors.get(runtime)
            if not actual:
                results.append((i, "UNCHECKABLE", "version", f"{runtime} {documented} (no declared floor to compare)"))
            elif actual.split(".")[0] != documented.split(".")[0]:
                results.append((i, "STALE", "version", f"{runtime} {documented} documented, {actual} declared"))
            else:
                results.append((i, "OK", "version", f"{runtime} {documented}"))

    return rel_doc, results


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <file|dir> [--recursive]", file=sys.stderr)
        return 64

    target = sys.argv[1]
    recursive = "--recursive" in sys.argv
    root = git_root()

    docs: list[str] = []
    if os.path.isdir(target):
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and not SKIP_RE.search(f"/{d}/")]
            docs.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(DOC_EXT))
            if not recursive:
                break
    else:
        docs = [target]

    if not docs:
        print(f"No documents found at {target}")
        return 0

    print("indexing repository…", file=sys.stderr)
    scripts, symbols, floors = load_scripts(root), index_symbols(root), runtime_floor(root)
    paths, deps = index_paths(root), dependency_names(root)

    totals = {"OK": 0, "STALE": 0, "UNCHECKABLE": 0}
    for doc in sorted(docs):
        rel, results = check_doc(doc, root, scripts, symbols, floors, paths, deps)
        stale = [r for r in results if r[1] == "STALE"]
        unchecked = [r for r in results if r[1] == "UNCHECKABLE"]
        for _, verdict, _, _ in results:
            totals[verdict] += 1

        print(f"\n── {rel} — {len(results)} claim(s): "
              f"{len(results) - len(stale) - len(unchecked)} ok, {len(stale)} stale, "
              f"{len(unchecked)} uncheckable ──")
        for line_no, _, kind, detail in stale:
            print(f"  STALE       {rel}:{line_no}  [{kind}] {detail}")
        for line_no, _, kind, detail in unchecked[:8]:
            print(f"  uncheckable {rel}:{line_no}  [{kind}] {detail}")
        if len(unchecked) > 8:
            print(f"  … and {len(unchecked) - 8} more uncheckable")

    print(
        f"\ntotals: {totals['OK']} ok, {totals['STALE']} stale, "
        f"{totals['UNCHECKABLE']} uncheckable\n"
        "\nUNCHECKABLE is not drift — it is a claim this extractor could not resolve.\n"
        "Discard the false positives (illustrative paths, dependency symbols, quoted\n"
        "output) before reporting, and say how many you discarded. Prose was not checked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
