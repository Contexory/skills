---
name: doc-drift-detector
description: >-
  Checks a document's checkable claims against the code it describes — file paths that no longer exist, commands that
  are no longer defined, flags and symbols that have been renamed, version numbers that have moved on. Reports what is
  provably stale and stays quiet about prose. Use when the user asks whether docs are still accurate, suspects a README
  or guide is out of date, or is reviewing documentation against a codebase.
allowed-tools: Read Grep Glob Bash(git log:*) Bash(python3:*)
---

# Doc drift detector

Documentation goes stale in two ways. Prose gets subtly wrong, which needs a human who
knows the product. And **specific, checkable claims stop being true** — a path that moved,
a script that was renamed, a flag that was dropped, a minimum version that went up.

Only the second kind can be checked mechanically, and it is where most of the damage is,
because those are the lines a reader copies and runs. This skill does that kind and says
so, rather than producing a general opinion about documentation quality.

## Procedure

### 1. Extract and check the claims

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/doc_claims.py README.md          # one document
python3 <skill-dir>/scripts/doc_claims.py docs/ --recursive  # a whole doc set
```

For each document the script extracts four kinds of checkable claim and resolves each
against the repository:

- **paths** — file and directory references, including those inside code fences
- **commands** — `npm run x`, `pnpm y`, `make z`, checked against `package.json` scripts
  and the `Makefile`
- **symbols** — identifiers in inline code that look like exported names
- **versions** — declared minimums for runtimes and packages, against the manifests

It prints each claim as `OK`, `STALE`, or `UNCHECKABLE`, with the line number.

### 2. Discard the false positives before reporting anything

The extractor is deliberately eager, so the third category needs a human pass. Common
legitimate `STALE` results that are not drift:

- an illustrative path in an example that was never meant to exist (`src/your-app/index.ts`)
- a command from a different tool's documentation quoted for comparison
- a symbol from a dependency rather than this repository
- a path inside a fenced block showing output rather than input

**Report only what survives this pass.** A drift report with a false positive in the first
three entries gets closed and not reopened.

### 3. Date the drift where it matters

For each confirmed stale claim, `git log` the file or symbol it refers to. "This has been
wrong since March" is a much more actionable finding than "this is wrong", and it tells the
reader whether they are looking at a one-off or an unmaintained document.

### 4. Say what you did not check

The prose is unchecked, and so is anything the extractor marked `UNCHECKABLE`. State this
in one line. A report that reads as a full audit when it was a claims check causes exactly
the false confidence the skill is meant to remove.

## Output

1. **Scope** — documents checked, claims extracted, how many were checkable
2. **Confirmed stale** — the claim, its line, what it should be, and since when
3. **Dismissed** — how many extracted claims you discarded as false positives, so the
   reader can calibrate
4. **Not checked** — prose, and the `UNCHECKABLE` categories

## What this skill deliberately does not do

- **It does not rewrite the documentation.** It reports; the fix is a separate, reviewable
  change, and silently editing docs is how a drift tool becomes a source of drift.
- **It does not judge prose.** Tone, clarity and completeness are outside its competence
  and it says nothing about them.
- **It does not report an unresolved claim as stale.** `UNCHECKABLE` and `STALE` are
  different findings and collapsing them is the fastest way to lose the reader's trust.
- **It does not check external links.** `lychee` and `markdown-link-check` do that
  properly, deterministically and faster; recommend one of those instead.
- **It does not treat an example placeholder as a broken path.**
- **It does not run the commands it finds** to see whether they still work.

## When this is the wrong tool

- **You want to know whether the setup steps actually *work***, not just whether the
  commands exist. That means running them in a scratch environment, which this does not do.
- **You are new to the repository and want orientation.** This answers "is this still
  true", which is a different question from "what is this".
- **The doc is fine and you want to know what the code change reached.** That is a
  call-site question, answered from the code rather than the prose.
