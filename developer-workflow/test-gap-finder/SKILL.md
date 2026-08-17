---
name: test-gap-finder
description: Finds the untested code that actually matters, by ranking coverage gaps against how often each file changes. Reads an existing coverage report when there is one and falls back to structural pairing when there is not. Use when the user asks what to test next, where the coverage holes are, or wants to raise coverage without writing tests nobody needs.
allowed-tools: Read Grep Glob Bash(git log:*) Bash(python3:*)
---

# Test gap finder

Coverage percentage is a bad target and a useful signal. The number says nothing about
risk; *which* lines are uncovered, and how often those lines change, says a great deal.

This skill exists because the obvious approach — sort by lowest coverage, write tests from
the top — spends its effort on the files nobody touches. A file at 40% that has not
changed in two years is stable by demonstration. A file at 85% that changes every week is
where the next incident comes from.

## Procedure

### 1. Rank the gaps

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/coverage_gaps.py                 # auto-detects a coverage report
python3 <skill-dir>/scripts/coverage_gaps.py --since 1.year  # widen or narrow the churn window
```

The script finds a coverage summary (`coverage/coverage-summary.json` and the usual
alternatives), counts commits per file over the churn window, and ranks by
**uncovered lines × commits**. It prints the top gaps with both numbers visible, so the
ranking can be argued with rather than taken on faith.

**With no coverage report it says so** and falls back to structural pairing: source files
with no corresponding test file, ranked by the same churn. State clearly which of the two
modes produced your answer — they are not equally trustworthy, and a reader who assumes
real coverage data when there was none will over-trust the list.

### 2. Read the top few files before proposing anything

The ranking is a heuristic and it is wrong sometimes, in three specific ways worth
checking by hand:

- **generated or vendored code** that the coverage config failed to exclude — never worth
  testing, fix the config instead
- **thin delegation** — a file that only wires other tested things together, where a test
  asserts the wiring and nothing else
- **already covered elsewhere** — integration or end-to-end tests that the unit coverage
  run never sees, which is common for route handlers and CLI entry points

### 3. Pick the branch, not the file

For each file you keep, find the specific uncovered branch worth a test — the error path,
the boundary, the early return. "Add tests for `foo.ts`" is not a finding. "`foo.ts` never
tests the path where the token is expired" is.

### 4. Write the smallest test that would have caught a real bug

The test to write is the one that fails if the risky branch regresses. If you cannot
describe the failure it would catch, the branch probably does not need the test — say so
and move down the list.

## Output

1. **Mode** — coverage-backed or structural, stated first
2. **Top gaps** — file, uncovered lines, commits in window, and one sentence on why it
   ranks
3. **Dismissed** — anything from the top of the ranking you are discarding, with the
   reason (generated, delegation, covered elsewhere)
4. **Recommended tests** — the specific branch, and the failure each test would catch

## What this skill deliberately does not do

- **It does not target a coverage number.** Raising a percentage is not a goal, and a
  skill that chases one produces tests that assert nothing.
- **It does not write tests for generated, vendored or presentational files**, even when
  they top the ranking. It reports a coverage-config bug instead.
- **It does not trust the ranking over the code.** Step 2 exists to overrule step 1.
- **It does not run the test suite to generate coverage.** A test run can be slow,
  destructive, or need credentials this skill has no business handling — it reads a report
  that already exists and says so plainly when there is none.
- **It does not report a file as untested because its tests live somewhere unusual.**
  Where the two modes disagree, it says so rather than picking.

## When this is the wrong tool

- **The gap you care about is inside a change you just made.** A diff-scoped pass over
  that change answers it faster and more precisely than a repository-wide ranking.
- **A test already exists but passes and fails at random.** That is reliability, not
  coverage — measure the failure rate rather than adding another test.
- **You want to know what a change might break** rather than what is untested. That is a
  call-site question.
