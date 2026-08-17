/**
 * Unit tests for the pack lint. Zero dependencies, `node --test`.
 *
 * The one to read first is the `allowed-tools` block. This linter is a
 * *fourth* parser of that field, and the previous three all shipped the same
 * bug: `split(/\s+/)`, which tears `Bash(pnpm test:*)` into `Bash(pnpm` and
 * `test:*)`. Every copy of that split passed its own tests, because the obvious
 * fixture — `Bash(git:*)` — has no space in it. So the fixtures below lead with
 * a scope that does.
 */

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";

import {
  TRIGGER_PHRASES,
  allowedToolsFrom,
  lintGalleryLinks,
  lintPack,
  lintSkill,
  packDirs,
  skillDirs,
  parseAllowedTools,
  parseFrontmatter,
  runCli,
} from "./lint.mjs";

// ── Fixtures ──────────────────────────────────────────────────────────────

const GOOD_SKILL_MD = `---
name: error-triage
description: Locates the cause of a runtime error inside this repository. Use when the user pastes a stack trace.
allowed-tools: Read Grep Bash(git log:*) Bash(python3:*)
---

# Error triage

Run the mapper on the trace:

\`\`\`
python3 <skill-dir>/scripts/trace_map.py -
\`\`\`
`;

/** The one line of the body that runs the skill's script. */
const RUNS_THE_SCRIPT = "python3 <skill-dir>/scripts/trace_map.py -";

/**
 * The README GitHub renders when someone opens the skill's directory.
 *
 * Generated at assembly upstream, checked in by anyone opening a pull request
 * here — which is exactly why the lint owns it rather than the generator.
 */
const GOOD_SKILL_README = "# `error-triage`\n\nLocates the cause of a runtime error.\n";

/** A skill that lints clean, with per-test overrides. */
function skill(overrides = {}) {
  return {
    dir: "error-triage",
    skillMd: GOOD_SKILL_MD,
    readme: GOOD_SKILL_README,
    files: ["README.md", "SKILL.md", "scripts/trace_map.py"],
    ...overrides,
  };
}

/** Swap one frontmatter line for another (or drop it when `to` is null). */
function reframe(from, to) {
  const replaced = GOOD_SKILL_MD.split("\n")
    .filter((line) => to !== null || !line.startsWith(from))
    .map((line) => (line.startsWith(from) && to !== null ? to : line))
    .join("\n");
  return replaced;
}

const codes = (problems) => problems.map((p) => p.code).sort();

// ── the README's copy of the phrase list ──────────────────────────────────

describe("the trigger phrases the README advertises", () => {
  it("are exactly the ones the linter checks for", () => {
    // `description-no-trigger` is a warning precisely because the whitelist
    // cannot make the judgement its name implies — so the README prints the four
    // phrases, on the argument that a rule a contributor cannot check before
    // pushing is one they discover from a build. That makes the row a *second
    // statement* of `TRIGGER_PHRASES` with nothing holding the two together,
    // which is the same shape as every bug this file exists for. Add a fifth
    // phrase to the linter and the page advertises four; this is what fails.
    //
    // Read relative to this file rather than the working directory, so it holds
    // both here and in the monorepo the repository is assembled from.
    const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");
    const row = readme.split("\n").find((line) => line.includes("`description-no-trigger`"));
    assert.ok(row, "no README row documents description-no-trigger");

    // Backticked items after "none of", so the rule's own name in the first
    // column is not mistaken for a phrase. Order included: the row reads as a
    // list, and a reordered list is a list someone edited without looking here.
    const listed = [...row.slice(row.indexOf("none of")).matchAll(/`([^`]+)`/g)].map((m) => m[1]);
    assert.deepEqual(listed, TRIGGER_PHRASES);
  });
});

// ── parseAllowedTools ─────────────────────────────────────────────────────

describe("parseAllowedTools", () => {
  it("keeps a scope containing a space as ONE token", () => {
    // The whole reason this function exists. `split(/\s+/)` returns two here,
    // and both halves then fail the token regex.
    assert.deepEqual(parseAllowedTools("Bash(pnpm test:*)"), ["Bash(pnpm test:*)"]);
    // The other everyday shape: spaces, no colon. Three tokens under a split.
    assert.deepEqual(parseAllowedTools("Bash(git add *)"), ["Bash(git add *)"]);
  });

  it("does not merge two adjacent scoped tokens across the gap", () => {
    assert.deepEqual(parseAllowedTools("Bash(git log:*) Bash(pnpm run build:*)"), [
      "Bash(git log:*)",
      "Bash(pnpm run build:*)",
    ]);
  });

  it("splits bare tokens and scoped tokens together", () => {
    assert.deepEqual(parseAllowedTools("Read Grep Bash(git diff:*) Bash(python3:*)"), [
      "Read",
      "Grep",
      "Bash(git diff:*)",
      "Bash(python3:*)",
    ]);
  });

  it("returns malformed input as tokens rather than dropping it", () => {
    // Swallowing garbage here would turn a lint error into a silent pass.
    assert.deepEqual(parseAllowedTools("Bash(git:* )"), ["Bash(git:* )"]);
    assert.deepEqual(parseAllowedTools("Bash(git:*"), ["Bash(git:*"]);
  });

  it("tolerates newlines and runs of whitespace", () => {
    assert.deepEqual(parseAllowedTools("Read\n  Grep\t Glob"), ["Read", "Grep", "Glob"]);
  });

  it("returns an empty list for empty input", () => {
    assert.deepEqual(parseAllowedTools(""), []);
    assert.deepEqual(parseAllowedTools("   \n "), []);
  });
});

// ── allowedToolsFrom ──────────────────────────────────────────────────────

describe("allowedToolsFrom", () => {
  it("reads the scalar form", () => {
    assert.deepEqual(allowedToolsFrom("Read Bash(git log:*)"), ["Read", "Bash(git log:*)"]);
  });

  it("reads the sequence form, which the scalar-only gate reported as no tools", () => {
    assert.deepEqual(allowedToolsFrom(["Read", "Bash(git log:*)"]), ["Read", "Bash(git log:*)"]);
  });

  it("tokenizes each entry, so an entry may itself hold several", () => {
    assert.deepEqual(allowedToolsFrom(["Read Grep", "Bash(git add *)"]), [
      "Read",
      "Grep",
      "Bash(git add *)",
    ]);
  });

  it("stringifies a non-string scalar entry rather than dropping it", () => {
    // Same reason the tokenizer returns malformed input: validation reports on
    // whatever comes back, so swallowing it turns an error into a silent pass.
    assert.deepEqual(allowedToolsFrom([42, true, "Read"]), ["42", "true", "Read"]);
  });

  it("yields nothing for entries carrying no readable token", () => {
    assert.deepEqual(allowedToolsFrom([null, { tool: "Read" }, ["nested"]]), []);
  });

  it("yields nothing for shapes that are neither string nor array", () => {
    for (const value of [undefined, null, 42, { Read: true }]) {
      assert.deepEqual(allowedToolsFrom(value), [], String(value));
    }
  });

  it("yields nothing for an empty sequence", () => {
    assert.deepEqual(allowedToolsFrom([]), []);
  });
});

// ── parseFrontmatter ──────────────────────────────────────────────────────

describe("parseFrontmatter", () => {
  it("reads a flat scalar map and returns the body", () => {
    const parsed = parseFrontmatter(GOOD_SKILL_MD);
    assert.equal(parsed.ok, true);
    assert.equal(parsed.frontmatter.name, "error-triage");
    assert.match(parsed.frontmatter.description, /^Locates the cause/);
    assert.equal(parsed.frontmatter["allowed-tools"], "Read Grep Bash(git log:*) Bash(python3:*)");
    assert.match(parsed.body, /^# Error triage/);
  });

  it("splits on the first colon only, so a scope keeps its own", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: Bash(git log:*)\n---\n");
    assert.equal(parsed.frontmatter["allowed-tools"], "Bash(git log:*)");
  });

  it("strips a fully quoted value", () => {
    const parsed = parseFrontmatter(`---\nname: "a-b"\ndescription: 'it''s fine'\n---\n`);
    assert.equal(parsed.frontmatter.name, "a-b");
    assert.equal(parsed.frontmatter.description, "it's fine");
  });

  it("reads the flow-sequence form into a real array", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: [Read, Bash(git log:*)]\n---\n");
    assert.equal(parsed.ok, true);
    assert.deepEqual(parsed.frontmatter["allowed-tools"], ["Read", "Bash(git log:*)"]);
  });

  it("reads an empty flow sequence", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: []\n---\n");
    assert.deepEqual(parsed.frontmatter["allowed-tools"], []);
  });

  it("unquotes entries in a flow sequence", () => {
    const parsed = parseFrontmatter(`---\nallowed-tools: ["Read", 'Grep']\n---\n`);
    assert.deepEqual(parsed.frontmatter["allowed-tools"], ["Read", "Grep"]);
  });

  it("refuses a flow sequence that does not close", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: [Read, Grep\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /does not close/);
  });

  it("refuses a nested sequence or mapping", () => {
    for (const value of ["[Read, [Grep]]", "[Read, {a: b}]"]) {
      const parsed = parseFrontmatter(`---\nallowed-tools: ${value}\n---\n`);
      assert.equal(parsed.ok, false, value);
      assert.match(parsed.problem.message, /nests/);
    }
  });

  it("refuses an empty entry in a flow sequence", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: [Read, , Grep]\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /empty entry/);
  });

  it("refuses a duplicated key declared as a flow sequence", () => {
    const parsed = parseFrontmatter("---\nallowed-tools: [Read]\nallowed-tools: [Grep]\n---\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-duplicate-key");
  });

  it("accepts a key with no value as the empty string", () => {
    const parsed = parseFrontmatter("---\nname:\n---\n");
    assert.equal(parsed.ok, true);
    assert.equal(parsed.frontmatter.name, "");
  });

  it("ignores blank lines and comments", () => {
    const parsed = parseFrontmatter("---\n# a comment\n\nname: x\n---\n");
    assert.equal(parsed.ok, true);
    assert.equal(parsed.frontmatter.name, "x");
  });

  it("reports a missing frontmatter block", () => {
    const parsed = parseFrontmatter("# no frontmatter here\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-missing");
  });

  it("refuses nested keys rather than guessing at them", () => {
    // The pack format is a flat scalar map. A parser that quietly ignored the
    // shapes it does not implement would report a skill as clean while reading
    // half its frontmatter.
    const parsed = parseFrontmatter("---\nmetadata:\n  author: someone\n---\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-unparsed");
    assert.match(parsed.problem.message, /line 2/);
  });

  it("reads a folded block scalar, which is how a two-line description is written", () => {
    const parsed = parseFrontmatter("---\ndescription: >-\n  first line\n  second line\n---\n");
    assert.equal(parsed.ok, true);
    assert.equal(parsed.frontmatter.description, "first line second line");
  });

  it("reads a literal block scalar, keeping its newlines", () => {
    const parsed = parseFrontmatter("---\ndescription: |-\n  first line\n  second line\n---\n");
    assert.equal(parsed.frontmatter.description, "first line\nsecond line");
  });

  it("chomps a block scalar the way YAML does", () => {
    assert.equal(parseFrontmatter("---\nd: >\n  a\n---\n").frontmatter.d, "a\n");
    assert.equal(parseFrontmatter("---\nd: >+\n  a\n---\n").frontmatter.d, "a\n");
    assert.equal(parseFrontmatter("---\nd: >-\n  a\n---\n").frontmatter.d, "a");
  });

  it("keeps every trailing newline under `+`, which is the only thing `+` means", () => {
    // With no trailing blank lines, keep and clip are identical — so a fixture
    // without them cannot tell the two apart, and one without them is exactly
    // what let an approximated `+` ship.
    assert.equal(parseFrontmatter("---\nd: >+\n  a\n\n\n---\n").frontmatter.d, "a\n\n");
    assert.equal(parseFrontmatter("---\nd: >\n  a\n\n\n---\n").frontmatter.d, "a\n");
    assert.equal(parseFrontmatter("---\nd: >-\n  a\n\n\n---\n").frontmatter.d, "a");
    assert.equal(parseFrontmatter("---\nd: |+\n  a\n\n\n---\n").frontmatter.d, "a\n\n");
  });

  it("refuses a tab-indented block, which no YAML reader will load", () => {
    const parsed = parseFrontmatter("---\nd: >-\n\ta\n\tb\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /tab/);
  });

  it("strips a comment after a closed quoted scalar, but not a hash inside one", () => {
    assert.equal(parseFrontmatter(`---\nd: "a thing." # keep short\n---\n`).frontmatter.d, "a thing.");
    assert.equal(parseFrontmatter(`---\nd: "a # b"\n---\n`).frontmatter.d, "a # b");
    assert.equal(parseFrontmatter("---\nd: 'it''s fine' # note\n---\n").frontmatter.d, "it's fine");
    assert.equal(parseFrontmatter(`---\nd: "esc \\" quote" # note\n---\n`).frontmatter.d, `esc \\" quote`);
  });

  it("leaves an unterminated or trailing-content quoted value alone", () => {
    // Reported by the shape checks rather than silently truncated here.
    assert.equal(parseFrontmatter(`---\nd: "unclosed\n---\n`).frontmatter.d, `"unclosed`);
    assert.equal(parseFrontmatter(`---\nd: "a" trailing\n---\n`).frontmatter.d, `"a" trailing`);
  });

  it("folds paragraphs across a blank line", () => {
    const parsed = parseFrontmatter("---\nd: >-\n  one\n  still one\n\n  two\n---\n");
    assert.equal(parsed.frontmatter.d, "one still one\ntwo");
  });

  it("ends a block scalar at the next top-level key", () => {
    const parsed = parseFrontmatter("---\nd: >-\n  a\n  b\nname: x\n---\n");
    assert.equal(parsed.frontmatter.d, "a b");
    assert.equal(parsed.frontmatter.name, "x");
  });

  it("ends a block scalar at a line indented less than its body", () => {
    // js-yaml also rejects this ("bad indentation of a mapping entry"); the
    // block ends and the de-dented line is not a valid top-level key.
    const parsed = parseFrontmatter("---\nd: >-\n    a\n  b\n---\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-unparsed");
  });

  it("drops trailing blank lines from a block scalar", () => {
    assert.equal(parseFrontmatter("---\nd: >-\n  a\n\n\n---\n").frontmatter.d, "a");
  });

  it("refuses a block scalar with no content under it", () => {
    const parsed = parseFrontmatter("---\ndescription: >-\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /no content/);
  });

  it("refuses a folded block whose line is indented further, rather than mis-folding", () => {
    const parsed = parseFrontmatter("---\nd: >-\n  a\n    deeper\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /indented further/);
  });

  it("refuses a block scalar form it does not implement", () => {
    const parsed = parseFrontmatter("---\nd: >2\n   a\n---\n");
    assert.equal(parsed.ok, false);
    assert.match(parsed.problem.message, /does not implement/);
  });

  it("refuses a duplicated key declared as a block scalar", () => {
    const parsed = parseFrontmatter("---\nd: >-\n  a\nd: >-\n  b\n---\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-duplicate-key");
  });

  it("strips a trailing comment, which YAML does not treat as value text", () => {
    // Not cosmetic: the comment used to count toward the 1024-character limit
    // and the trigger-phrase check.
    assert.equal(parseFrontmatter("---\nd: hello there # aside\n---\n").frontmatter.d, "hello there");
    assert.equal(
      parseFrontmatter("---\nd: Read Bash(git log:*) # tools\n---\n").frontmatter.d,
      "Read Bash(git log:*)",
    );
  });

  it("keeps a hash that is not a comment", () => {
    assert.equal(parseFrontmatter("---\nd: colour#1 is fine\n---\n").frontmatter.d, "colour#1 is fine");
    assert.equal(parseFrontmatter(`---\nd: "a # b"\n---\n`).frontmatter.d, "a # b");
  });

  it("refuses a duplicate key", () => {
    const parsed = parseFrontmatter("---\nname: a\nname: b\n---\n");
    assert.equal(parsed.ok, false);
    assert.equal(parsed.problem.code, "frontmatter-duplicate-key");
  });
});

// ── lintSkill ─────────────────────────────────────────────────────────────

describe("lintSkill", () => {
  it("passes a conforming skill", () => {
    assert.deepEqual(lintSkill(skill()), []);
  });

  it("fails an unreadable frontmatter block once, without cascading", () => {
    const problems = lintSkill(skill({ skillMd: "no frontmatter\n" }));
    assert.deepEqual(codes(problems), ["frontmatter-missing"]);
  });

  it("fails a missing name", () => {
    const problems = lintSkill(skill({ skillMd: reframe("name:", null) }));
    assert.ok(codes(problems).includes("name-missing"));
  });

  it("fails a malformed name", () => {
    const problems = lintSkill(skill({ skillMd: reframe("name:", "name: Error_Triage") }));
    assert.ok(codes(problems).includes("name-format"));
  });

  it("fails a name longer than 64 characters", () => {
    const long = "a".repeat(65);
    const problems = lintSkill(
      skill({ dir: long, skillMd: reframe("name:", `name: ${long}`) }),
    );
    assert.ok(codes(problems).includes("name-format"));
  });

  it("fails a reserved name the product would reject on import", () => {
    // `anthropic` and `claude` are refused by Contexory on import. A lint that let
    // them through would pass a pull request the product then rejects.
    for (const reserved of ["claude", "anthropic", "Claude"]) {
      const problems = lintSkill(
        skill({ dir: reserved.toLowerCase(), skillMd: reframe("name:", `name: ${reserved}`) }),
      );
      assert.ok(codes(problems).includes("name-reserved"), reserved);
    }
  });

  it("fails a name that does not match the directory", () => {
    const problems = lintSkill(skill({ dir: "triage-errors" }));
    assert.ok(codes(problems).includes("name-directory-mismatch"));
  });

  it("fails a missing description", () => {
    const problems = lintSkill(skill({ skillMd: reframe("description:", null) }));
    assert.ok(codes(problems).includes("description-missing"));
  });

  it("fails a description past the 1024-character limit", () => {
    const problems = lintSkill(
      skill({ skillMd: reframe("description:", `description: Use when ${"x".repeat(1024)}`) }),
    );
    assert.ok(codes(problems).includes("description-too-long"));
  });

  it("warns — rather than fails — a description with no triggering phrase", () => {
    // `TRIGGER_PHRASES` is a four-substring whitelist, and the product's own
    // `validateSkill` returns this issue at severity `warning`. "Use this when a
    // stack trace is pasted" contains none of the four while reading perfectly
    // and naming its trigger exactly, so a build failure here would red-build a
    // description the product accepts — and the fix a contributor would reach
    // for is to paste one of the four phrases in, which makes the description
    // worse at the only job this pack claims to measure.
    const problems = lintSkill(
      skill({ skillMd: reframe("description:", "description: Triages errors.") }),
    );
    const issue = problems.find((p) => p.code === "description-no-trigger");
    assert.ok(issue);
    assert.equal(issue.severity, "warning");
    // And the phrase list is in the message, because the README documents it as
    // a literal list: a rule a contributor cannot predict is one they discover
    // from a red build.
    assert.match(issue.message, /use when/);
  });

  it("does not warn on the phrasing the whitelist does recognize", () => {
    assert.deepEqual(lintSkill(skill()), []);
  });

  it("marks every other problem as an error", () => {
    // The severity field is not decoration: `runCli` exits on the errors alone,
    // so a rule that forgot to declare itself would stop failing the build.
    const problems = lintSkill(skill({ files: ["README.md", "SKILL.md"] }));
    assert.deepEqual(codes(problems), ["scripts-missing"]);
    assert.equal(problems[0].severity, "error");
  });

  it("passes a skill whose allowed-tools is a sequence", () => {
    const problems = lintSkill(
      skill({ skillMd: reframe("allowed-tools:", "allowed-tools: [Read, Bash(git log:*)]") }),
    );
    assert.deepEqual(problems, []);
  });

  it("fails an empty allowed-tools sequence", () => {
    const problems = lintSkill(
      skill({ skillMd: reframe("allowed-tools:", "allowed-tools: []") }),
    );
    assert.deepEqual(codes(problems), ["allowed-tools-missing"]);
  });

  it("fails a missing allowed-tools field", () => {
    const problems = lintSkill(skill({ skillMd: reframe("allowed-tools:", null) }));
    assert.deepEqual(codes(problems), ["allowed-tools-missing"]);
  });

  it("fails a malformed allowed-tools token", () => {
    const problems = lintSkill(
      skill({ skillMd: reframe("allowed-tools:", "allowed-tools: Read Bash(git log:*) bash(x)") }),
    );
    const bad = problems.find((p) => p.code === "allowed-tools-bad-token");
    assert.ok(bad);
    assert.match(bad.message, /bash\(x\)/);
  });

  it("does NOT report the halves of a space-bearing scope as malformed", () => {
    // The regression this whole file is built around: with a whitespace split,
    // `Bash(pnpm` and `test:*)` are each reported as an invalid token, and a
    // correct skill fails CI.
    const problems = lintSkill(
      skill({ skillMd: reframe("allowed-tools:", "allowed-tools: Read Bash(pnpm test:*)") }),
    );
    assert.deepEqual(problems, []);
  });

  it("fails a skill whose scopes are all single-word", () => {
    const problems = lintSkill(
      skill({ skillMd: reframe("allowed-tools:", "allowed-tools: Read Bash(python3:*)") }),
    );
    assert.deepEqual(codes(problems), ["allowed-tools-no-multiword-scope"]);
  });

  it("fails a skill with no scripts/ file", () => {
    const problems = lintSkill(skill({ files: ["SKILL.md"] }));
    assert.deepEqual(codes(problems), ["scripts-missing"]);
  });

  it("fails a skill with an assets/ file", () => {
    const problems = lintSkill(
      skill({ files: ["README.md", "SKILL.md", "scripts/trace_map.py", "assets/diagram.png"] }),
    );
    assert.deepEqual(codes(problems), ["assets-present"]);
  });
});

// ── the skill's own README ────────────────────────────────────────────────

describe("the directory README", () => {
  it("fails a skill that ships without one", () => {
    // It is the page a reader from a ranking site opens — GitHub renders it when
    // someone opens the directory, before they have seen the repository root.
    const problems = lintSkill(skill({ readme: null, files: ["SKILL.md", "scripts/trace_map.py"] }));
    assert.deepEqual(codes(problems), ["readme-missing"]);
  });

  it("fails a README copied from a sibling skill", () => {
    // The failure mode that actually happens: a contributor copies the nearest
    // skill's directory as a starting point and edits the SKILL.md. The README
    // then advertises — and gives the install command for — a different skill,
    // on the page a stranger lands on.
    const problems = lintSkill(skill({ readme: "# `pr-self-review`\n\nReviews a diff.\n" }));
    assert.deepEqual(codes(problems), ["readme-not-about-skill"]);
  });

  it("fails a README with no heading at all", () => {
    const problems = lintSkill(skill({ readme: "Some prose about error-triage.\n" }));
    assert.deepEqual(codes(problems), ["readme-not-about-skill"]);
  });

  it("accepts a heading that names the skill among other words", () => {
    assert.deepEqual(lintSkill(skill({ readme: "# The `error-triage` skill\n\nBody.\n" })), []);
  });
});

// ── the body's script references ──────────────────────────────────────────

describe("the body's script references", () => {
  it("fails a skill whose body never names its script", () => {
    // The junk-skill hole: a directory with a one-line script nothing invokes
    // passed all three CI steps. A script the prose never runs is not the
    // mechanical half of a skill, it is a file in a directory.
    const problems = lintSkill(
      skill({ skillMd: GOOD_SKILL_MD.replace(RUNS_THE_SCRIPT, "read the trace") }),
    );
    assert.deepEqual(codes(problems), ["script-unreferenced"]);
  });

  it("fails a body naming a script that is not there", () => {
    // The rename that leaves the body pointing at nothing. `check-scripts.sh`
    // cannot see it: the script it parses is the one that still exists.
    const problems = lintSkill(
      skill({ skillMd: GOOD_SKILL_MD.replace("trace_map.py", "mapper.py") }),
    );
    const missing = problems.find((p) => p.code === "script-not-found");
    assert.ok(missing);
    assert.match(missing.message, /mapper\.py/);
    // Reported once, not once per mention.
    assert.equal(problems.filter((p) => p.code === "script-not-found").length, 1);
  });

  it("fails a bare `scripts/…` path, which resolves to nothing at run time", () => {
    // A skill runs with the *user's project* as its working directory, so a
    // relative `python3 scripts/x.py` looks for a script in their repository.
    // The README states this; nothing checked it.
    const problems = lintSkill({
      ...skill(),
      skillMd: GOOD_SKILL_MD.replace("<skill-dir>/scripts/", "scripts/"),
    });
    assert.deepEqual(codes(problems), ["script-path-relative", "script-unreferenced"]);
  });

  it("reports a path written correctly once and relatively once", () => {
    // The realistic version of the relative-path bug: the code fence is right
    // and a later sentence is not. Reporting only the first mention would call
    // the skill clean while one of its two instructions runs nothing.
    const problems = lintSkill({
      ...skill(),
      skillMd: `${GOOD_SKILL_MD}\nRe-run scripts/trace_map.py afterwards.\n`,
    });
    assert.deepEqual(codes(problems), ["script-path-relative"]);
  });

  it("says nothing about a bare path that is not one of the skill's own files", () => {
    // "look in your repo's scripts/deploy.sh" is prose about the user's project,
    // not a broken reference — the rule keys off the skill's own file list.
    const problems = lintSkill({
      ...skill(),
      skillMd: `${GOOD_SKILL_MD}\nCheck the project's own scripts/deploy.sh too.\n`,
    });
    assert.deepEqual(problems, []);
  });

  it("accepts a nested helper the body does not name", () => {
    // `scripts/lib/util.py` is imported by the script the body runs. Requiring
    // every file to appear in prose would red-build a legitimate layout.
    const problems = lintSkill(
      skill({ files: ["README.md", "SKILL.md", "scripts/trace_map.py", "scripts/lib/util.py"] }),
    );
    assert.deepEqual(problems, []);
  });

  it("checks nothing about references when there is no script to reference", () => {
    // One cause, one message: a skill with no `scripts/` file is reported as
    // that, not as three consequences of it.
    const problems = lintSkill(
      skill({
        skillMd: GOOD_SKILL_MD.replace(RUNS_THE_SCRIPT, "read the trace"),
        files: ["README.md", "SKILL.md"],
      }),
    );
    assert.deepEqual(codes(problems), ["scripts-missing"]);
  });
});

// ── lintPack + runCli (the filesystem half) ───────────────────────────────

const temps = [];

/** Materialize `{ path: contents }` under a fresh temp directory. */
function fixtureTree(tree) {
  const root = mkdtempSync(join(tmpdir(), "pack-lint-"));
  temps.push(root);
  for (const [path, contents] of Object.entries(tree)) {
    const full = join(root, path);
    mkdirSync(join(full, ".."), { recursive: true });
    writeFileSync(full, contents);
  }
  return root;
}

after(() => {
  for (const root of temps) rmSync(root, { recursive: true, force: true });
});

const LINKS_PENDING = JSON.stringify({ status: "pending", links: { "error-triage": null } });

/** The repository's front page, which has to list every skill it holds. */
const REPO_README = `# A pack

| Skill | What it does |
| :--- | :--- |
| [\`error-triage\`](./developer-workflow/error-triage) | Finds the frame that owns a failure |
`;

/** A repository holding one pack of one skill. Skills live at <pack>/<skill>/. */
const GOOD_TREE = {
  "README.md": REPO_README,
  "gallery-links.json": LINKS_PENDING,
  "developer-workflow/error-triage/README.md": GOOD_SKILL_README,
  "developer-workflow/error-triage/SKILL.md": GOOD_SKILL_MD,
  "developer-workflow/error-triage/scripts/trace_map.py": "print(1)\n",
};

describe("lintPack", () => {
  it("finds no problems in a conforming repository", () => {
    assert.deepEqual(lintPack(fixtureTree(GOOD_TREE)), []);
  });

  it("ignores root directories that contain no skills", () => {
    const root = fixtureTree({ ...GOOD_TREE, "tools/lint.mjs": "// not a skill\n" });
    assert.deepEqual(lintPack(root), []);
    assert.deepEqual(packDirs(root), ["developer-workflow"]);
  });

  it("fails a repository with no packs at all, and still checks the mapping", () => {
    // The gallery check used to be suppressed by an early return here — in the
    // one case where it has the most to say, namely which skills the mapping
    // still lists that the repository no longer has.
    const root = fixtureTree({ "README.md": "# empty\n", "gallery-links.json": LINKS_PENDING });
    assert.deepEqual(codes(lintPack(root)), ["gallery-link-orphan", "pack-empty"]);
  });

  it("fails a repository with no README at all", () => {
    const root = fixtureTree({
      "gallery-links.json": LINKS_PENDING,
      "developer-workflow/error-triage/README.md": GOOD_SKILL_README,
      "developer-workflow/error-triage/SKILL.md": GOOD_SKILL_MD,
      "developer-workflow/error-triage/scripts/trace_map.py": "print(1)\n",
    });
    assert.deepEqual(codes(lintPack(root)), ["repo-readme-missing"]);
  });

  it("fails a skill the repository README does not link", () => {
    // The other half of the count problem, stated per skill instead of as a
    // number: a skill nobody listed is a skill nobody finds, and the moment a
    // contributor has to add the row is the moment the prose around it — "Nine
    // skills…", the results table — is in front of them.
    const root = fixtureTree({ ...GOOD_TREE, "README.md": "# A pack\n\nNothing linked.\n" });
    assert.deepEqual(codes(lintPack(root)), ["readme-skill-unlisted"]);
  });

  it("fails a README link to a skill that is not there", () => {
    // A skill removed without touching the README leaves a 404 on the front
    // page. Only Markdown link targets are read, so prose naming a path is not
    // mistaken for a claim that it exists.
    const root = fixtureTree({
      ...GOOD_TREE,
      "README.md": `${REPO_README}| [\`ghost\`](./developer-workflow/ghost) | Gone |\n`,
    });
    const problems = lintPack(root);
    assert.deepEqual(codes(problems), ["readme-link-dead"]);
    assert.match(problems[0].message, /ghost/);
  });

  it("declares a severity on every problem it can produce", () => {
    // `runCli` decides the exit code from this field, so a rule that forgot to
    // set it would stop failing the build the day the default changed. Asserted
    // over a tree that trips as many rules at once as one tree can.
    const root = fixtureTree({
      "gallery-links.json": "{ not json",
      "stray-skill/SKILL.md": GOOD_SKILL_MD,
      "developer-workflow/error-triage/SKILL.md": GOOD_SKILL_MD.replace(
        /^description:.*$/m,
        "description: Triages errors.",
      ),
    });
    const problems = lintPack(root);
    assert.ok(problems.length > 4);
    for (const problem of problems) {
      assert.ok(["error", "warning"].includes(problem.severity), `${problem.code}: ${problem.severity}`);
    }
  });

  it("fails a skill sitting at the repository root instead of inside a pack", () => {
    // The layout mistake that would force a URL-breaking reorganization later:
    // every skill's public path has to stay <pack>/<skill> so a second pack is
    // purely additive.
    const root = fixtureTree({ ...GOOD_TREE, "stray-skill/SKILL.md": GOOD_SKILL_MD });
    const problems = lintPack(root);
    assert.ok(codes(problems).includes("skill-outside-pack"));
    assert.equal(problems.find((p) => p.code === "skill-outside-pack").dir, "stray-skill");
  });

  it("names a broken skill by its pack-qualified path", () => {
    const root = fixtureTree({
      ...GOOD_TREE,
      "README.md": `${REPO_README}| [\`doc-drift-detector\`](./developer-workflow/doc-drift-detector) | Reads a doc |\n`,
      "developer-workflow/doc-drift-detector/README.md": "# `doc-drift-detector`\n",
      "developer-workflow/doc-drift-detector/SKILL.md": GOOD_SKILL_MD.replace(
        "trace_map.py",
        "x.py",
      ),
      "developer-workflow/doc-drift-detector/scripts/x.py": "",
    });
    const problems = lintPack(root);
    assert.deepEqual(codes(problems), ["gallery-link-missing", "name-directory-mismatch"]);
    const mismatch = problems.find((p) => p.code === "name-directory-mismatch");
    assert.equal(mismatch.dir, "developer-workflow/doc-drift-detector");
  });

  it("walks nested directories when collecting a skill's files", () => {
    const root = fixtureTree({
      ...GOOD_TREE,
      "developer-workflow/error-triage/assets/nested/deep/diagram.png": "",
    });
    assert.deepEqual(codes(lintPack(root)), ["assets-present"]);
  });

  it("lists skills directly under a root when no pack is named", () => {
    // `skillDirs(root)` with no pack is the shape the assembler uses upstream,
    // where the nine live at the root before the pack level is added.
    const root = fixtureTree({
      "error-triage/SKILL.md": GOOD_SKILL_MD,
      "not-a-skill/notes.md": "",
    });
    assert.deepEqual(skillDirs(root), ["error-triage"]);
  });

  it("lints two packs side by side", () => {
    const root = fixtureTree({
      ...GOOD_TREE,
      "README.md": `${REPO_README}| [\`other-skill\`](./second-pack/other-skill) | Something else |\n`,
      "gallery-links.json": JSON.stringify({
        status: "pending",
        links: { "error-triage": null, "other-skill": null },
      }),
      "second-pack/other-skill/README.md": "# `other-skill`\n",
      "second-pack/other-skill/SKILL.md": reframe("name:", "name: other-skill").replace(
        "trace_map.py",
        "x.py",
      ),
      "second-pack/other-skill/scripts/x.py": "",
    });
    assert.deepEqual(lintPack(root), []);
    assert.deepEqual(packDirs(root), ["developer-workflow", "second-pack"]);
  });
});

// ── gallery links ─────────────────────────────────────────────────────────

describe("lintGalleryLinks", () => {
  const skills = ["error-triage", "pr-self-review"];

  it("accepts every skill mapped to null while the gallery is pending", () => {
    // `publicSlug` is derived once, on first publish, and is a permalink. Until
    // a skill is actually published there is no slug to point at, and a guessed
    // URL is a 404 on a repository whose first impression is the whole point.
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({
        status: "pending",
        links: { "error-triage": null, "pr-self-review": null },
      }),
    });
    assert.deepEqual(lintGalleryLinks(root, skills), []);
  });

  it("accepts real https URLs", () => {
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({
        status: "published",
        links: {
          "error-triage": "https://contexory.com/skills/acme/error-triage",
          "pr-self-review": "https://contexory.com/skills/acme/pr-self-review",
        },
      }),
    });
    assert.deepEqual(lintGalleryLinks(root, skills), []);
  });

  it("fails when the mapping file is absent", () => {
    assert.deepEqual(codes(lintGalleryLinks(fixtureTree({ "a.md": "" }), skills)), [
      "gallery-links-missing",
    ]);
  });

  it("fails when the mapping file is not valid JSON", () => {
    const root = fixtureTree({ "gallery-links.json": "{ not json" });
    assert.deepEqual(codes(lintGalleryLinks(root, skills)), ["gallery-links-unparsed"]);
  });

  it("fails an unrecognized status", () => {
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({ status: "soon", links: {} }),
    });
    assert.ok(codes(lintGalleryLinks(root, skills)).includes("gallery-links-status"));
  });

  it("treats a mapping with no `links` key as having no entries", () => {
    const root = fixtureTree({ "gallery-links.json": JSON.stringify({ status: "pending" }) });
    assert.deepEqual(codes(lintGalleryLinks(root, skills)), [
      "gallery-link-missing",
      "gallery-link-missing",
    ]);
  });

  it("fails a skill with no entry at all", () => {
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({ status: "pending", links: { "error-triage": null } }),
    });
    const problems = lintGalleryLinks(root, skills);
    assert.deepEqual(codes(problems), ["gallery-link-missing"]);
    assert.match(problems[0].message, /pr-self-review/);
  });

  it("fails an entry for a skill that does not exist", () => {
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({
        status: "pending",
        links: { "error-triage": null, "pr-self-review": null, "ghost-skill": null },
      }),
    });
    const problems = lintGalleryLinks(root, skills);
    assert.deepEqual(codes(problems), ["gallery-link-orphan"]);
    assert.match(problems[0].message, /ghost-skill/);
  });

  it("fails a malformed URL", () => {
    for (const bad of ["http://contexory.com/skills/a/b", "/skills/a/b", "not a url", 42]) {
      const root = fixtureTree({
        "gallery-links.json": JSON.stringify({
          status: "pending",
          links: { "error-triage": bad, "pr-self-review": null },
        }),
      });
      assert.deepEqual(codes(lintGalleryLinks(root, skills)), ["gallery-link-malformed"], String(bad));
    }
  });

  it("fails a URL that is not a gallery skill path", () => {
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({
        status: "pending",
        links: { "error-triage": "https://contexory.com/pricing", "pr-self-review": null },
      }),
    });
    assert.deepEqual(codes(lintGalleryLinks(root, skills)), ["gallery-link-malformed"]);
  });

  it("fails a pending entry once the mapping declares itself published", () => {
    // The single switch to flip after the gallery is seeded: it turns "not yet"
    // from an accepted state into a build failure, so the placeholders cannot
    // outlive the reason for them.
    const root = fixtureTree({
      "gallery-links.json": JSON.stringify({
        status: "published",
        links: {
          "error-triage": "https://contexory.com/skills/acme/error-triage",
          "pr-self-review": null,
        },
      }),
    });
    assert.deepEqual(codes(lintGalleryLinks(root, skills)), ["gallery-link-pending"]);
  });
});

describe("runCli", () => {
  it("prints a pass line and exits 0 on a clean repository", () => {
    const out = [];
    const code = runCli({ argv: [fixtureTree(GOOD_TREE)], cwd: "/nowhere", log: (m) => out.push(m) });
    assert.equal(code, 0);
    assert.match(out.join("\n"), /1 skill/);
    assert.match(out.join("\n"), /1 pack/);
  });

  it("defaults to the working directory", () => {
    const out = [];
    const code = runCli({ argv: [], cwd: fixtureTree(GOOD_TREE), log: (m) => out.push(m) });
    assert.equal(code, 0);
  });

  it("prints a warning and still exits 0", () => {
    // The `description-no-trigger` decision, at the level a contributor meets
    // it: the rule is a substring whitelist, so it advises rather than gates —
    // but it is printed on every run, because a warning nobody sees is a rule
    // that has been deleted with extra steps.
    const out = [];
    const err = [];
    const root = fixtureTree({
      ...GOOD_TREE,
      "developer-workflow/error-triage/SKILL.md": GOOD_SKILL_MD.replace(
        /^description:.*$/m,
        "description: Triages a runtime failure.",
      ),
    });
    const code = runCli({
      argv: [root],
      cwd: "/nowhere",
      log: (m) => out.push(m),
      error: (m) => err.push(m),
    });
    assert.equal(code, 0);
    assert.match(err.join("\n"), /description-no-trigger/);
    assert.match(out.join("\n"), /1 warning/);
  });

  it("prints every problem and exits 1", () => {
    const err = [];
    const root = fixtureTree({
      "gallery-links.json": LINKS_PENDING,
      "developer-workflow/error-triage/SKILL.md": GOOD_SKILL_MD,
    });
    const code = runCli({ argv: [root], cwd: "/nowhere", log: () => {}, error: (m) => err.push(m) });
    assert.equal(code, 1);
    const printed = err.join("\n");
    assert.match(printed, /developer-workflow\/error-triage/);
    assert.match(printed, /scripts-missing/);
  });
});
