# `doc-drift-detector`

Checks a document's checkable claims against the code it describes — file paths that no longer exist, commands that are no longer defined, flags and symbols that have been renamed, version numbers that have moved on. Reports what is provably stale and stays quiet about prose. Use when the user asks whether docs are still accurate, suspects a README or guide is out of date, or is reviewing documentation against a codebase.

**[This skill on the Contexory gallery](https://www.contexory.com/skills/contexory-m4td4h/doc-drift-detector)** — rendered, with its supporting files.

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
npx skills add Contexory/skills --skill doc-drift-detector
```

That takes this skill and nothing else. Run inside a repository it installs to
`<repo>/.agents/skills/doc-drift-detector` and symlinks that into
`<repo>/.claude/skills/doc-drift-detector`, with a `skills-lock.json` at the repository
root — commit or ignore both directories together, since the bytes are in
`.agents/`. `--global` does the same under your home directory.

Or copy the directory, which puts no third-party tool in the chain:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/doc-drift-detector ~/.claude/skills/doc-drift-detector
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there.

Nothing else in this pack is required — no skill here references another.
