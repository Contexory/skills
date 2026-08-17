# Nine skills tested for when they should *not* fire

Agent skills for Claude Code and compatible hosts. Nine of them, for the things
developers actually reach for — triage a failure, review your own diff, find the
untested branch, work out what an upgrade breaks.

There are a lot of skill packs. The difference here is not the ideas, which are
mostly the same ideas everyone else had. It is that **every skill here has been
run against the prompts it should fire on _and_ the prompts it should stay out
of**, with the other eight competing for the same prompt.

That matters because of the way skills fail. The mechanism is over-triggering: a
skill that fires on everything adjacent to its topic is a tax on every unrelated
turn, and you cannot see that from a description — a description is written by
someone who wants their skill to be used.

We know because we measured it on this pack, and it was bad.
`repo-onboarding-map` answered "where is the login form component?" — a question
about one file — with a whole-repository survey, often enough that narrowing one
sentence of its description was worth doing. It has not gone away entirely.
Reading the description would never have caught it; only the negative cases did.

So the negative cases are the product. **They are not in this repository, and
they are not public anywhere else either** — that is the first thing to know
about the numbers below, and it is stated here rather than further down because
it changes how much weight they can carry. They are authored and re-run in
[Contexory](https://contexory.com), against a live dispatcher with every sibling
skill offered alongside — which is the only setting in which over-triggering
appears at all, and not a thing a Markdown table in a git repository can
demonstrate. They are not shipped here because they are test cases: they are not
consumed by the skill, and a stranger installing `error-triage` should get a
skill rather than somebody else's test corpus. Read
[The evidence, and where it is](#the-evidence-and-where-it-is) before judging any
figure in this README.

## The nine

| Skill | What it does |
| :--- | :--- |
| [`error-triage`](./developer-workflow/error-triage) | Finds the frame that owns a runtime failure in *your* repo and checks whether that line is new — from a pasted trace, a CI log, or a failure you can only describe |
| [`pr-self-review`](./developer-workflow/pr-self-review) | Runs the reviewer pass on your own diff before you push — the behaviour that changed without gaining a test, the surface you newly exported |
| [`test-gap-finder`](./developer-workflow/test-gap-finder) | Ranks untested code by how often it changes, so the gaps you close are the ones that bite |
| [`regression-risk-mapper`](./developer-workflow/regression-risk-mapper) | Traces every call site and importer a change can reach — before you make it, or after — and marks which are covered by a test |
| [`dependency-upgrade-auditor`](./developer-workflow/dependency-upgrade-auditor) | Reads release notes against the specific APIs your code imports, rather than in general |
| [`flaky-test-finder`](./developer-workflow/flaky-test-finder) | Re-runs a test enough times to report an observed failure rate, then narrows the cause |
| [`repo-onboarding-map`](./developer-workflow/repo-onboarding-map) | The first-thirty-minutes map of an unfamiliar codebase, read from what it does rather than what its README claims |
| [`changeset-writer`](./developer-workflow/changeset-writer) | Detects the repository's own release convention and picks the bump from what changed in the public surface |
| [`doc-drift-detector`](./developer-workflow/doc-drift-detector) | Checks a document's *checkable* claims — paths, commands, flags, versions — and stays quiet about prose |

## Install

```bash
npx skills add Contexory/skills
```

That is the [`skills` CLI](https://github.com/vercel-labs/skills) — the one
[skills.sh](https://skills.sh) documents, and the line
[vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) and
[gitshot](https://github.com/vipulgupta2048/gitshot) publish for their own
skills. It clones this repository, finds all nine, and asks which you want;
inside an agent session it skips the question and takes all nine. To pick one
either way:

```bash
npx skills add Contexory/skills --skill error-triage
```

To take several, repeat the flag —
`--skill error-triage --skill pr-self-review`. `--skill '*'` takes all nine.

Run inside a repository it installs to `<repo>/.agents/skills/<name>` and
symlinks that into `<repo>/.claude/skills/<name>`, with a `skills-lock.json` at
the repository root — **commit or ignore the two directories together**, because
the bytes are in `.agents/` and a teammate who gets only `.claude/` clones a
dangling symlink. `--global` does the same under your home directory, and prints
a `✗ … does not support global skill installation` line for each agent that has
no global location; it exits 0 all the same. Claude Code is one of several agents
the CLI installs for — `--agent` picks one, and skills.sh lists what it supports.

**Checked against this repository, not assumed.** On 2026-08-17, with
`skills@1.5.22`: all nine are discovered even though they sit a level down under
`developer-workflow/` rather than at the root; one skill can be taken rather than
the whole pack; each arrives whole — `SKILL.md`, its `README.md`, and its
`scripts/` directory beside them; and the destinations are the ones written
above, symlink included. Nesting is the thing most worth checking, because a
directory layout is exactly what a discovery rule can quietly not reach.

### Or copy the directory

The fallback with no third-party tool in the chain. Each skill directory is
self-contained:

```bash
git clone https://github.com/Contexory/skills.git
mkdir -p ~/.claude/skills
cp -R skills/developer-workflow/error-triage ~/.claude/skills/error-triage
```

The `mkdir` is not padding: `cp` creates no intermediate directories, and
`~/.claude/skills` does not exist until something puts a skill there — so on the
machine of the person most likely to be reading this, the copy fails without it.
Point the destination at `<your-repo>/.claude/skills/<name>` instead to install
for one repository rather than for yourself. A copied skill is a plain directory
with nothing pointing at it, so there is no second location to keep in step.

### Either way

Take one, take three, take all nine — **no skill in this pack references
another**, so nothing breaks when you install a subset.

Skill bodies name their script as `<skill-dir>/scripts/…`, where `<skill-dir>`
is wherever you installed it. That is deliberate: a skill runs with *your
project* as its working directory, so a relative `python3 scripts/x.py` would
resolve to nothing — and [CI fails a skill that writes one](#the-three-rules-about-a-skills-script).

The Python scripts need `python3` and nothing else — no packages to install. The
skills detect the surrounding ecosystem and degrade rather than fail outside
Node/TypeScript: run against a repository with no Node in it, seven of the nine
exit cleanly with a message saying what they could not find, and the other two
exit with a usage code. None crashes.

Nothing here measures whether a skill's *output* is good. What was measured is
triggering — whether the right skill fires — which is a different question from
whether it then does useful work, and we have published no evidence on the
second one. See [The evidence, and where it is](#the-evidence-and-where-it-is).

## Not the Contexory plugin

Two different things, and the difference is what each one does after you install
it. **This repository is nine fixed skills.** You install them, the copies are
yours, and they change when you install again.

The [Contexory](https://contexory.com) plugin for Claude Code is not these nine
at all — it syncs *your own* workspace's skills into Claude Code and keeps them
current as your team publishes new versions:

```
/plugin marketplace add https://www.contexory.com/claude/marketplace.json
/plugin install contexory@contexory
```

It manages its own directory rather than `~/.claude/skills`, so it neither
installs these nine nor disturbs them if you have. Nothing in this repository
requires it, and installing it does not get you this pack.

## Layout

```
developer-workflow/            # a pack
  <skill-name>/
    SKILL.md                   # frontmatter + body
    README.md                  # what GitHub shows when you open the directory
    scripts/<one file>         # the deterministic half
gallery-links.json             # skill -> its page on the Contexory gallery
tools/                         # the lint, and the lint's own tests
```

**A skill directory holds only what the skill uses.** Its trigger tests live in
Contexory ([why](#the-evidence-and-where-it-is)), and so does our positioning
against anyone else's skill. Installing one of these should put a tool on your
machine, not files you have to work out whether to delete.

**Skills sit under a pack directory, never at the root.** This repository is
named for what it holds rather than for one pack's topic, so a second pack is a
new directory beside `developer-workflow/` — additive, with no existing path
moving. Every skill's URL contains that segment, and those URLs get linked from
places we do not control, so the level exists from day one rather than being
retrofitted the first time it is needed.

There is no `assets/` directory anywhere, and CI fails a skill that grows one —
asset files do not survive a sync back into a skill-management tool, so a skill
that depended on one could not round-trip.

## What CI enforces

`node tools/lint-cli.mjs .` runs on every pull request and every push to `main`
([workflow](./.github/workflows/lint.yml)). It is zero-dependency — `node:`
builtins only, no lockfile, nothing to audit. It fails on:

| | |
| :--- | :--- |
| **Frontmatter** | missing `name` or `description`; a `name` that does not match its directory; a description over 1024 characters |
| **`allowed-tools`** | a malformed token; no token whose scope contains a space |
| **Files** | no `scripts/` file; no `README.md`; a `README.md` whose first heading names a different skill; an `assets/` file present |
| **The body** | it runs no `<skill-dir>/scripts/…` file; it runs one that is not there; it writes a script path relatively |
| **Layout** | a skill sitting at the repository root instead of inside a pack |
| **This page** | a skill this README links nowhere, or a link into a pack that points at no skill |
| **Gallery links** | a skill with no entry in `gallery-links.json`, an entry for a skill that does not exist, or a malformed URL |
| **Scripts** | a Python or shell script that does not parse |
| **The linter itself** | its own test suite below 100% line, branch or function coverage |

**Nothing there counts anything.** There is no rule that this repository holds
nine skills, or that a pack holds any particular number: a second pack is meant
to be additive, and a pinned count is a line whoever adds one has to edit. The
rules are stated per skill instead — carry your own README, run your own script,
and appear in [the table at the top of this page](#the-nine). That last one is
the count problem in the only form a linter can check, and it puts a contributor
in the paragraph where a stale "Nine skills…" is sitting.

### The three rules about a skill's script

They are one rule really: **the script is the skill's mechanical half, so the
body has to run it.**

```
python3 <skill-dir>/scripts/trace_map.py -     # what a body writes
python3 scripts/trace_map.py -                 # CI fails this
```

The second one is not a style preference. A skill runs with **your project** as
its working directory, not its own install directory, so a relative path looks
for the script in your repository and does not find it. The rule fires only on a
path that is one of the skill's own files — a body may perfectly well talk about
`scripts/deploy.sh` in *your* repo, which is prose about your project rather than
a broken reference to ours.

The other two are what a syntax check cannot see: a script no instruction ever
runs (it parses fine, and does nothing), and a body still naming a script that
was renamed (the script that remains parses fine too).

### What CI warns about, without failing

One rule, and it is a warning on purpose:

| | |
| :--- | :--- |
| `description-no-trigger` | the description contains none of `use this skill`, `when the user`, `for tasks involving`, `use when` |

That is a **literal substring list**, printed on every run and never a build
failure. The four phrases are written out here because the check cannot do what
its name claims: "Use this when a stack trace is pasted" states its trigger
exactly and matches none of them. Contexory's own validator returns this at
`warning` for the same reason, and this repository's linter is bound to that
severity by a test rather than deciding for itself.

It stays *visible* because triggering is the pack's whole subject — but if you
read the warning, look at your description and conclude it already says when to
fire, the warning is the thing that is wrong. **Do not paste one of the four
phrases in to silence it.** That optimizes the description for a substring check
instead of for the dispatcher, which is precisely the failure this pack was built
to measure.

### The `allowed-tools` line deserves its own paragraph

The field is whitespace-separated, but a token's *scope* may itself contain
spaces — `Bash(pnpm test:*)` and `Bash(git add *)` are both ordinary Claude Code
syntax. Splitting the field on whitespace tears the first into `Bash(pnpm` and
`test:*)`, and a linter that did so would report two errors for one correct
token.

We know because we shipped that bug, more than once, in more than one reader of
the same field — every time by someone re-implementing the split locally,
because it looks like one line of code. Every copy passed its own tests, because
the fixture everyone reaches for (`Bash(git:*)`) has no space in it. That is the
whole trap: the test you would naturally write goes green.

So this repository's linter is tokenizer-based, its
[test suite](./tools/lint.test.mjs) leads with a scope that contains a space,
and every skill here declares at least one multi-word scope — which makes the
pack itself a standing fixture for the bug.

Both spellings of the field are accepted, because both are real:

```yaml
allowed-tools: Read Grep Bash(git log:*)     # scalar
allowed-tools: [Read, Grep, "Bash(git log:*)"]  # sequence
```

The second one is the same bug in a different hat. Readers that gated on "is
this a string?" reported a sequence as *no tools at all* — the file keeps its
tools, every derived surface disagrees, and nothing raises an error. A linter
that rejected it would be wrong about documented input, so this one reads both
and tokenizes each entry.

## The evidence, and where it is

**Every number below is a claim you cannot currently check, and that is the most
important sentence in this README.**

The per-case evidence — each prompt, each verdict it drew, and the dispatcher's
own stated reasoning — is recorded in [Contexory](https://contexory.com), which
is where these cases are authored and where they are re-run whenever a
description changes. It sits in the private workspace that owns these skills.

**There is no public route to it, and we are not claiming there will be one.**
In particular, publishing a skill to the Contexory gallery does not expose it:
the gallery serves the skill — its body and its supporting files — and not the
workspace around it. Test cases are not readable by an anonymous visitor there,
by design and at the database level. The nine skills **are** published to the
gallery now, and the `gallery-links.json` entries in this repository resolve —
so this is no longer a prediction about what a link would show, but a statement
about pages you can open. Each one links **the skill**, and each skill's README
says exactly that. None of them promises the evidence, and opening one confirms
it: what is there is the skill body and its scripts.

That leaves the numbers below resting on our word, which is worth saying in
those terms rather than dressing up. They are published because withholding a
measurement we made and acted on would be worse, and because the parts you *can*
check are the ones that most determine whether the figure means anything:

- **The method is fully stated below** — harness, mode, model, thinking setting,
  dispatcher prompt, date. It is enough to run the same shape of test yourself,
  and to see which choices flatter the result and which do not.
- **The skills are here.** The descriptions these numbers measure are the
  `SKILL.md` files in this repository, unmodified. What was measured is in your
  hands even though the measurement is not.
- **The results that go against us are in the table.** A pack reporting 90% with
  its worst skill at 6/12 on its own fire cases is not a table anyone would
  construct to persuade you.

If that is not enough for you, it should not be — treat the figure as a claim
awaiting evidence, install one skill, and see whether it stays quiet.

### The method

| | |
| :--- | :--- |
| **Harness** | 90 cases — 10 per skill (4–6 fire, 4–6 skip) — each run **3 times** = 270 verdicts |
| **Mode** | **Workspace** — all nine skills offered to the dispatcher at once |
| **Model** | `deepseek-v4-flash`, the `smart` tier |
| **Thinking** | **enabled, effort `low`** (`AI_DEEPSEEK_THINKING=low`) |
| **Dispatcher prompt** | the built-in default template, no custom one |
| **Date** | 2026-08-16 |

Each case is one prompt plus the verdict it *should* draw — `fire` if this skill
is the right one for it, `skip` if it is not. A skip case is usually a border
with a neighbouring skill: "what could break if I change this function's
signature?" is a real question, and it belongs to `regression-risk-mapper`
rather than `error-triage`, because nothing has failed yet.

**Workspace mode is the hard version of this test.** Each skill competes against
its eight siblings for every prompt, which is the only way over-triggering shows
up — the skip cases mostly guard those borders, and a skill measured alone never
meets them. A number produced by testing one skill in isolation is not
comparable to these and will be higher.

**Thinking is on, and it is not a detail.** `low` is the product default, but the
default is *enabled*, not off — our own routing eval moved accuracy from 75% to
94% across five fixtures by turning DeepSeek thinking on. Reproducing this with
`AI_DEEPSEEK_THINKING=off` should be expected to score lower; it is a different
measurement, not a failed replication.

Three passes rather than one because a verdict is a model sample, not a
deterministic output — a single run publishes a coin-flip as a fact.

### The results

**244 of 270 verdicts correct (90%) — recorded per case and per run in a
Contexory workspace you cannot read, and not published anywhere you can.**

| Skill | Fire | Skip |
| :--- | :--- | :--- |
| `error-triage` | 12/12 | 18/18 |
| `flaky-test-finder` | 12/12 | 18/18 |
| `dependency-upgrade-auditor` | 12/12 | 17/18 |
| `doc-drift-detector` | 12/12 | 17/18 |
| `test-gap-finder` | 12/12 | 16/18 |
| `changeset-writer` | 9/12 | 16/18 |
| `pr-self-review` | 12/12 | 13/18 |
| `regression-risk-mapper` | 6/12 | 17/18 |
| `repo-onboarding-map` | 15/15 | 10/15 |
| **Total** | **102/111** | **142/159** |

The same caveat applies to every row of it, and to each of the observations
below. They are published rather than dropped because a results table edited
down to its good rows is worse than one you cannot yet audit.

`repo-onboarding-map` has different denominators because one of its cases moved
from skip to fire: "write an ONBOARDING.md for this repo" was testing whether
the skill writes files rather than whether it should trigger, and the skill's
answer — produce the map, commit nothing — is the right one.

The candidate list was exactly these nine, constructed from the nine `SKILL.md`
files and asserted to be nine before any prompt was sent. That matters for one
`regression-risk-mapper` verdict, where the dispatcher returned a skill called
`git`: **no such skill was offered, and none exists.** The model invented the
name, and said so in the same call — its reasoning is recorded beside that
verdict in Contexory. It is reported rather than quietly dropped because it is a
fair sample of what a dispatcher does under competition, and because a table
that silently omitted it would be a table we had edited.

**Every remaining fire-side failure is the same thing, and it is not the skill.**
Nine of the 111 fire verdicts came back wrong, across **five** distinct cases
(one in `changeset-writer`, four in `regression-risk-mapper`) — the table counts
verdicts, so both numbers describe the same nine failures. In none of them did
the dispatcher reject the skill: it asked what the prompt referred to, because
each names its subject deictically — "this", "this function" — with nothing
attached. On one of the four `regression-risk-mapper` cases it named the skill
while doing so:

> That matches the regression-risk-mapper skill, but I need to know which
> function you mean before I can trace its call sites and importers.

That is quoted verbatim from the run's recorded reasoning, which — like every
other verdict here — sits beside its case in the workspace described above,
where you cannot check it. This is the dispatcher instruction working as
written — "if the user's intent is
ambiguous, ask a clarifying question instead" — and in a real session the
referent is already in context. The prompts were left alone, because rewriting
them to carry their own context would raise the score without changing anything
about the skill.

`repo-onboarding-map` is the weakest skip score at 10/15, and it is the one
worth watching: it still occasionally answers "where is the login form
component?" with a whole-repository survey. Its description was narrowed on
2026-08-16 after an earlier run scored it worse.

### What this does and does not measure

- It **is** a measurement of the frontmatter `description` — whether a
  dispatcher picks the right skill from nine competing one-line descriptions. It
  is **not** a measurement of whether the skill, once fired, does good work.
  Nothing here measures output quality, and we have published no evidence on it.
- It **is** one model on one date. A different dispatcher model will produce
  different numbers.
- Run the cases the way they were run here — **with your other skills
  installed** — for the reason given above. A skill tested alone never meets the
  borders its skip cases guard.

### What would have to change for you to check this

Two separate things, and neither is done:

- **An export.** Contexory's GitHub sync carries a skill's body and its
  supporting files; it does not carry trigger-test metadata. When it does, these
  cases can arrive here as an export alongside the skills — generated, not
  hand-kept, so it cannot disagree with the runs it describes.
- **A public read path.** Test cases are not exposed to anonymous visitors by
  the gallery, so publishing these skills there did not make the evidence
  readable — and they *are* published now, so that is an observation rather than
  a forecast. That is a deliberate boundary — publishing a skill exposes the
  skill, not the workspace around it — so opening it is a decision somebody has
  to take on purpose, not a step that happens on the way to something else.

Until both land, the figures above are ours and unverified, and this section
exists so that nobody has to work that out for themselves.

## Contributing

Open an issue or a pull request. CI is the whole review checklist, and it is
three commands — these, exactly as [the workflow](./.github/workflows/lint.yml)
runs them:

```bash
# 1. the linter's own tests, at 100% coverage or the build fails
node --test --experimental-test-coverage \
  --test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100 \
  --test-coverage-exclude='**/*.test.mjs' --test-coverage-exclude='**/*-cli.mjs' \
  'tools/**/*.test.mjs'

# 2. the linter, over every skill
node tools/lint-cli.mjs .

# 3. every skill script parses
bash tools/check-scripts.sh
```

The coverage flags in the first one are not optional garnish — without them the
command passes while CI fails, which is exactly how a red first build happened
here once. If you would rather not paste them, copy the `run:` lines straight
out of the workflow; they are single-line on purpose.

## License

[MIT](./LICENSE). Built by [Contexory](https://contexory.com), which is where
these were authored, versioned and tested.
