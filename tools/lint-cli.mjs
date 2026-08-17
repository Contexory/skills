#!/usr/bin/env node
// Entry point only: argv in, exit code out. Every decision lives in lint.mjs,
// which is where the tests are.
import { runCli } from "./lint.mjs";

process.exit(runCli({ argv: process.argv.slice(2) }));
