# `flaky-test-finder`

Proves whether a test is flaky instead of reasoning about it, by re-running it many times and reporting the observed failure rate, then narrowing the cause to ordering, shared state, timing or environment. Use when a test fails intermittently, passes on retry, fails only in CI, or the user suspects flakiness.

_Not yet published to the [Contexory gallery](https://contexory.com/skills). The URL is recorded in [`gallery-links.json`](../../gallery-links.json) rather than guessed, because a skill's public slug is allocated on its first publish._

- [`SKILL.md`](./SKILL.md) — the skill itself
- [`scripts/`](./scripts) — the deterministic half

## Trigger tests

This skill was tested on the prompts it should fire on and the prompts it should
stay out of, with the other eight skills in this pack competing for each one.
Those cases are authored and run inside Contexory, in the private workspace that
owns the skill — **no link on this page or in this repository reaches them, and
publishing the skill to the gallery does not change that.** What is published is
the skill; the case-by-case evidence is not public today by any route.

The repository README states the aggregate result and says the same thing about
it: [The evidence, and where it is](../../README.md#the-evidence-and-where-it-is).

## Install

```bash
cp -R developer-workflow/flaky-test-finder ~/.claude/skills/flaky-test-finder
```

Or into one repository, as `<repo>/.claude/skills/flaky-test-finder`. Nothing else in
this pack is required — no skill here references another.
