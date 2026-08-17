# `pr-self-review`

Reviews your own diff before anyone else has to. Inventories every changed file, finds the ones that gained behaviour without gaining a test, flags newly exported surface, and separates what the diff claims to do from what it also did. Use when the user is about to push, open a pull request, or asks for a review of work they just finished.

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
cp -R developer-workflow/pr-self-review ~/.claude/skills/pr-self-review
```

Or into one repository, as `<repo>/.claude/skills/pr-self-review`. Nothing else in
this pack is required — no skill here references another.
