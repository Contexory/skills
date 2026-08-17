---
name: flaky-test-finder
description: Proves whether a test is flaky instead of reasoning about it, by re-running it many times and reporting the observed failure rate, then narrowing the cause to ordering, shared state, timing or environment. Use when a test fails intermittently, passes on retry, fails only in CI, or the user suspects flakiness.
allowed-tools: Read Grep Glob Bash(git log:*) Bash(bash:*)
---

# Flaky test finder

Flakiness is an empirical claim, and it is the one kind of test problem where reasoning
from the source is actively misleading. A test that looks obviously order-dependent may be
solid; a test that looks pure may fail one run in forty on a loaded machine.

So this skill measures first and reads second.

## Procedure

### 1. Measure the rate

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
bash <skill-dir>/scripts/rerun.sh "pnpm vitest run path/to/file.test.ts" 30
```

Runs the command N times, reports pass/fail per run, the observed failure rate, and a
Wilson confidence interval for the true rate. **The interval is the point**: three failures
in ten runs and three in a hundred are very different findings, and a bare percentage hides
which one you have.

If the failure rate is 0 over a decent number of runs, say so plainly — "not reproduced in
N runs" is a real result. Do not go on to diagnose a flake you could not observe.

### 2. Split ordering from isolation

The two commonest causes look identical from the failure message. Distinguish them:

- Run the single test **alone**, many times. Failing alone means it is not
  order-dependent — look at timing, environment and external state.
- Run the whole file, then the whole suite. If it only fails in the larger set, it is
  **shared state or ordering** — something before it leaves a mutation behind.
- If the runner supports a random seed, vary it. A failure rate that moves with the seed is
  ordering by definition.

### 3. Find the shared thing

When it is ordering or isolation, the cause is almost always one of a short list, and it
is worth checking them in order rather than reading the test top to bottom:

- module-level mutable state, a cache, or a singleton that survives between tests
- a fake clock, timezone or locale set by one test and not restored
- database or filesystem state without a per-test transaction or temp directory
- an unawaited promise from an earlier test landing during this one
- a shared port, fixture file, or environment variable

### 4. Prove the fix by re-measuring

Apply the fix, then run step 1 again with at least as many iterations. The claim "fixed" is
only supported by a second measurement with a comparable interval. A single green run
proves nothing about a test that failed one time in twenty.

### 5. If it cannot be fixed now, quarantine deliberately

Say so explicitly, with the rate, and prefer an annotation the runner reports over a silent
skip. A quarantined test that nobody can see becomes a deleted test.

## Output

1. **Rate** — failures over runs, with the interval, and the exact command measured
2. **Class** — ordering, isolation, timing, environment, or not reproduced
3. **Evidence** — which of the step-2 runs differed, and how
4. **Cause** — the specific shared thing, with the line
5. **Post-fix rate** — the second measurement, or an explicit "not yet re-measured"

## What this skill deliberately does not do

- **It does not diagnose from the source without measuring.** That is the failure mode
  this skill exists to replace.
- **It does not add a retry.** Retries hide the rate and convert a known flake into an
  unknown one. If a retry is genuinely the right call, that is the author's decision to
  make explicitly, not a fix to apply quietly.
- **It does not delete or `skip` a test to make a suite green.**
- **It does not claim a fix from one passing run.**
- **It does not run suites that mutate shared infrastructure** — a test command touching a
  shared database, a live API or a deployment is not re-run thirty times. It says why and
  asks for an isolated target.
- **It does not report a rate without saying how many runs produced it.**

## When this is the wrong tool

- **The test fails every single time.** That is not flakiness, it is a bug with a
  reproduction already in hand — diagnose it from the failure instead. Measuring a 100%
  rate tells you nothing you did not already know.
- **The test does not exist yet** and you are deciding what to cover. That is a coverage
  question, not a reliability one.
- **The failures started immediately after a dependency bump.** Check the bump first: a
  changed default explains a whole class of new intermittency.
