# `regression-risk-mapper`

Maps what a change can reach — a change being considered as readily as one already made, since the question is usually asked before the edit exists. Finds the symbols involved, traces every call site and importer across the repository, and marks which of those call sites are exercised by a test and which are not. Use when the user asks what something might break, what depends on a symbol they are about to modify, rename or change the return type of, how far the blast radius of a refactor extends, or whether an edit is safe to make. Not for finding usages as an end in itself — with no change in prospect, that is a plain search and answering it with a risk analysis is more than was asked.

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
cp -R developer-workflow/regression-risk-mapper ~/.claude/skills/regression-risk-mapper
```

Or into one repository, as `<repo>/.claude/skills/regression-risk-mapper`. Nothing else in
this pack is required — no skill here references another.
