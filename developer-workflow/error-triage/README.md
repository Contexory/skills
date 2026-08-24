# `error-triage`

Locates the cause of a runtime failure inside this repository. Maps stack frames to real source files, separates first-party code from vendored frames, and surfaces the recent changes to the line that owns the failure. A pasted stack trace is the fastest input but not a requirement — it works from a CI or crash log, or from a failure the user only describes, in which case its first step is establishing what to capture. Use when something has already failed at runtime and the user wants to know why — a pasted exception, a job log, or a fault that appears in one environment and not another. Not for a failure the user describes as intermittent, where the rate has to be measured before anything can be diagnosed.

**[This skill on the Contexory gallery](https://www.contexory.com/skills/contexory/error-triage)** — rendered, with its supporting files.

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
npx skills add Contexory/skills --skill error-triage
```

That takes this skill and nothing else. Run inside a repository it installs to
`<repo>/.agents/skills/error-triage` and symlinks that into
`<repo>/.claude/skills/error-triage`, with a `skills-lock.json` at the repository
root — commit or ignore both directories together, since the bytes are in
`.agents/`. `--global` does the same under your home directory.

Or copy the directory, which puts no third-party tool in the chain:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/error-triage ~/.claude/skills/error-triage
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there.

Nothing else in this pack is required — no skill here references another.
