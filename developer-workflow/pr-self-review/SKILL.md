---
name: pr-self-review
description: Reviews your own diff before anyone else has to. Inventories every changed file, finds the ones that gained behaviour without gaining a test, flags newly exported surface, and separates what the diff claims to do from what it also did. Use when the user is about to push, open a pull request, or asks for a review of work they just finished.
allowed-tools: Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(python3:*)
---

# PR self-review

The reviewer you are about to send this to will spend their first ten minutes working out
what actually changed. Do that first, and send them a diff where the surprises are already
labelled.

This is not a code-quality lecture. It is a search for the specific things a diff hides
from its own author: the file you touched incidentally, the export you widened without
meaning to, the behaviour you added without a test.

## Procedure

### 1. Inventory the diff mechanically

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/review_surface.py            # working tree vs merge-base with main
python3 <skill-dir>/scripts/review_surface.py origin/dev # or an explicit base
```

The script prints every changed file with its classification (source, test, config, docs,
generated, lockfile), the added/removed line counts, and four flags per file:

- `NO-TEST` — a source file changed and no test file for it changed in the same diff
- `NEW-EXPORT` — the diff adds an exported symbol
- `DEL-TEST` — the diff removes test cases
- `WIDE` — a hunk over 200 lines, which almost always contains a second change

### 2. Read every `NO-TEST` file and decide, per file

Three legitimate answers, and you must pick one out loud:

- the change is behaviour-preserving (rename, move, formatting) — say which
- the behaviour is covered by an existing test that did not need editing — name the test
- it needs a test — write it now, before the review, not after

Anything else is the gap the reviewer will find.

### 3. Read every `NEW-EXPORT`

A new export is a promise to everyone who imports it. Ask whether it needs to be exported
at all — most do not — and whether its name will still be right in six months. This is the
cheapest moment in the change's life to narrow it.

### 4. Split the diff in your head

State, in one sentence, what this change is for. Then find every hunk that is not that.
Incidental refactors, drive-by formatting, an unrelated fix you noticed — each is fine on
its own and each makes the diff harder to review and impossible to revert cleanly. Decide
per hunk: keep it and mention it in the description, or move it out.

### 5. Write the description from the diff, not from memory

Cover what changed, what it is for, and what a reviewer should look at hardest. If step 4
found extra changes, they go in a "also in this change" list. The reviewer's attention is
the scarce resource — spend it where the risk is.

## Output

A short report, in this order:

1. **What this change is for** — one sentence
2. **Untested behaviour** — the `NO-TEST` files with a decision each, or "none"
3. **New public surface** — the `NEW-EXPORT` list with a keep/narrow call each
4. **Also in this diff** — the hunks that are not the stated purpose
5. **Look here hardest** — the two or three places a reviewer should spend their attention

## What this skill deliberately does not do

- **It does not review code it did not change.** Pre-existing problems in a touched file
  are out of scope; saying so is the point, since a review that wanders makes the diff
  bigger.
- **It does not enforce style.** The linter owns that, runs faster, and does not have
  opinions. If a style point is not mechanically checked in this repo, it is not a review
  finding.
- **It does not restate the diff.** A summary of each hunk is what the diff is for.
- **It does not gate on the `NO-TEST` flag.** A flag is a prompt for a decision, not a
  verdict — behaviour-preserving changes are real and common, and a skill that demands a
  test for every touched file gets muted within a week.
- **It does not open, push, or merge anything.** It reports; the author acts.

## When this is the wrong tool

- **You want to know what *else* the change could reach**, beyond the files in it. That
  means following call sites out of the diff; this review deliberately stays inside it.
- **You are looking for missing tests across the whole repository.** This is diff-scoped
  by design, and repository-wide coverage is a different search.
- **You need the release note.** Describing a change to a consumer is a different job from
  checking it.
