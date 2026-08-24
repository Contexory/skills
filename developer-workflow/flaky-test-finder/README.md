# `flaky-test-finder`

Proves whether a test is flaky instead of reasoning about it, by re-running it many times and reporting the observed failure rate, then narrowing the cause to ordering, shared state, timing or environment. Use when a test fails intermittently, passes on retry, fails only in CI, or the user suspects flakiness.

**[This skill on the Contexory gallery](https://www.contexory.com/skills/contexory/flaky-test-finder)** — rendered, with its supporting files.

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
npx skills add Contexory/skills --skill flaky-test-finder
```

That takes this skill and nothing else. Run inside a repository it installs to
`<repo>/.agents/skills/flaky-test-finder` and symlinks that into
`<repo>/.claude/skills/flaky-test-finder`, with a `skills-lock.json` at the repository
root — commit or ignore both directories together, since the bytes are in
`.agents/`. `--global` does the same under your home directory.

Or copy the directory, which puts no third-party tool in the chain:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/flaky-test-finder ~/.claude/skills/flaky-test-finder
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there.

Nothing else in this pack is required — no skill here references another.
