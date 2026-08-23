# `regression-risk-mapper`

Maps what a change can reach — a change being considered as readily as one already made, since the question is usually asked before the edit exists. Finds the symbols involved, traces every call site and importer across the repository, and marks which of those call sites are exercised by a test and which are not. Use when the user asks what something might break, what depends on a symbol they are about to modify, rename or change the return type of, how far the blast radius of a refactor extends, or whether an edit is safe to make. Not for finding usages as an end in itself — with no change in prospect, that is a plain search and answering it with a risk analysis is more than was asked.

**[This skill on the Contexory gallery](https://www.contexory.com/skills/contexory/regression-risk-mapper)** — rendered, with its supporting files.

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
npx skills add Contexory/skills --skill regression-risk-mapper
```

That takes this skill and nothing else. Run inside a repository it installs to
`<repo>/.agents/skills/regression-risk-mapper` and symlinks that into
`<repo>/.claude/skills/regression-risk-mapper`, with a `skills-lock.json` at the repository
root — commit or ignore both directories together, since the bytes are in
`.agents/`. `--global` does the same under your home directory.

Or copy the directory, which puts no third-party tool in the chain:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/regression-risk-mapper ~/.claude/skills/regression-risk-mapper
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there.

Nothing else in this pack is required — no skill here references another.
