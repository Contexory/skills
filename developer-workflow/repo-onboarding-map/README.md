# `repo-onboarding-map`

Produces the first-thirty-minutes map of a whole repository — how it is laid out, how to run and test it, which files carry the most change, and where the decisions were written down. Reads what the repository actually does rather than what its README claims. Use when the user needs to get oriented in an entire codebase they do not know — joining one, reviewing one they do not own, or asking how a project is structured and how to get it running. It is a survey, so it does not apply to a question about one part of a codebase — locating a single file, explaining one function, or asking how to carry out a specific change are each one lookup, and a whole-repository map is a disproportionate answer to them.

**[This skill on the Contexory gallery](https://www.contexory.com/skills/contexory/repo-onboarding-map)** — rendered, with its supporting files.

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
npx skills add Contexory/skills --skill repo-onboarding-map
```

That takes this skill and nothing else. Run inside a repository it installs to
`<repo>/.agents/skills/repo-onboarding-map` and symlinks that into
`<repo>/.claude/skills/repo-onboarding-map`, with a `skills-lock.json` at the repository
root — commit or ignore both directories together, since the bytes are in
`.agents/`. `--global` does the same under your home directory.

Or copy the directory, which puts no third-party tool in the chain:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/repo-onboarding-map ~/.claude/skills/repo-onboarding-map
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there.

Nothing else in this pack is required — no skill here references another.
