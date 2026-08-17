#!/usr/bin/env python3
"""Map a stack trace onto files that actually exist in this repository.

The mechanical half of triage: which frames are yours, which are vendored, which
resolve to a real file, and what git knows about the first one that does. The
judgement half — *why* that line broke — is left to the reader, deliberately.

Reads a trace from a file argument or from stdin when passed `-`. Recognises
Node/V8, Python, Go and Java frame formats; a trace mixing several (a Node
process logging a Python subprocess failure) is handled frame by frame.

Only the standard library, so it runs anywhere python3 does.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

# Frame formats, in the order we try them. Each pattern must yield `file` and
# `line` groups; `fn` is optional and only used for display.
FRAME_PATTERNS = [
    # V8: "at fn (/abs/file.ts:12:34)" / "at /abs/file.js:12:34" / "at fn (file.ts:12)"
    re.compile(
        r"^\s*at\s+(?:(?P<fn>.+?)\s+\()?(?P<file>[^()\s]+?):(?P<line>\d+)(?::\d+)?\)?\s*$"
    ),
    # CPython: '  File "/abs/file.py", line 42, in fn'
    re.compile(
        r'^\s*File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<fn>.+))?\s*$'
    ),
    # JVM: "at com.foo.Bar.baz(Bar.java:42)"
    re.compile(r"^\s*at\s+(?P<fn>[\w$.]+)\((?P<file>[\w$.]+\.java):(?P<line>\d+)\)\s*$"),
    # Go: "\t/abs/file.go:42 +0x1d" — the function is on the preceding line, which
    # we do not need, so it is not captured.
    re.compile(r"^\s+(?P<file>\/[^\s:]+\.go):(?P<line>\d+)(?:\s+\+0x[0-9a-f]+)?\s*$"),
]

# A frame is vendored if its path contains any of these. `node:` and `<anonymous>`
# are runtime-internal rather than on-disk, and are filtered the same way.
VENDOR_MARKERS = (
    "node_modules",
    ".pnpm",
    "site-packages",
    "dist-packages",
    "/vendor/",
    ".venv",
    "/virtualenv",
    "/usr/lib/python",
    "/usr/local/go/src/",
    "/usr/local/lib/",
    "internal/modules/",
    "node:internal",
    "<anonymous>",
    "/.cargo/",
    "/.rustup/",
)


@dataclass
class Frame:
    raw: str
    path: str
    line: int
    fn: str | None
    resolved: str | None = None  # repo-relative, only when the file exists

    @property
    def vendored(self) -> bool:
        return any(m in self.path for m in VENDOR_MARKERS)


def repo_root() -> str:
    """Git top level, or the working directory when this is not a repository."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def parse(text: str) -> list[Frame]:
    frames: list[Frame] = []
    for raw in text.splitlines():
        for pattern in FRAME_PATTERNS:
            m = pattern.match(raw)
            if not m:
                continue
            frames.append(
                Frame(
                    raw=raw.strip(),
                    path=m.group("file"),
                    line=int(m.group("line")),
                    fn=(m.groupdict().get("fn") or None),
                )
            )
            break
    return frames


def resolve(path: str, root: str) -> str | None:
    """Find `path` under `root`, tolerating that the trace came from another machine.

    A CI trace carries absolute paths like `/home/runner/work/app/src/db.ts` that
    exist nowhere locally. Matching progressively shorter suffixes recovers the
    repo-relative path without needing to know the build's directory layout.
    Longest suffix wins, so a two-segment match is preferred to a bare filename —
    which is what keeps `src/index.ts` from resolving to `test/index.ts`.
    """
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]
    for start in range(len(parts)):
        candidate = os.path.join(root, *parts[start:])
        if os.path.isfile(candidate):
            return os.path.relpath(candidate, root)
    return None


def git(args: list[str], root: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=root, check=True
        )
        return out.stdout.rstrip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def report(frames: list[Frame], root: str) -> int:
    if not frames:
        print("No stack frames recognised in the input.")
        print("Supported formats: V8/Node, CPython, Go, JVM.")
        return 2

    print(f"repo root: {root}")
    print(f"{len(frames)} frame(s) parsed\n")

    owning: Frame | None = None
    for i, f in enumerate(frames):
        f.resolved = None if f.vendored else resolve(f.path, root)
        if f.resolved and owning is None:
            owning = f
        kind = "vendor" if f.vendored else ("project" if f.resolved else "unresolved")
        mark = "OWNING" if f is owning else "      "
        where = f.resolved or f.path
        fn = f" — {f.fn}" if f.fn else ""
        print(f"  {mark} [{kind:>10}] {where}:{f.line}{fn}")

    if owning is None:
        print(
            "\nNo project frame resolved to a file on disk.\n"
            "Every frame is vendored, or the trace came from a different build of "
            "this code.\n"
            "Ask for the commit the trace was produced from before going further — "
            "do not diagnose from the vendor frames."
        )
        return 1

    print(f"\n── owning frame: {owning.resolved}:{owning.line} ──\n")

    blame = git(
        ["blame", "-L", f"{owning.line},{owning.line}", "--date=short", "--", owning.resolved],
        root,
    )
    print("git blame:")
    print(f"  {blame}" if blame else "  (unavailable — not a git repository?)")

    log = git(
        ["log", "-3", "--date=short", "--format=%h %ad %an  %s", "--", owning.resolved],
        root,
    )
    print("\nlast commits touching this file:")
    print("\n".join(f"  {ln}" for ln in log.splitlines()) if log else "  (none)")

    print(
        "\nNext: read the owning frame and the frames either side of it. If blame shows "
        "the line is old, its input changed rather than its logic — follow the input."
    )
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <trace-file>|-", file=sys.stderr)
        return 64
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8", errors="replace").read()
    return report(parse(text), repo_root())


if __name__ == "__main__":
    sys.exit(main())
