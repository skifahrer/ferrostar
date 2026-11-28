# Shared rules

Identical in rikimaps, maptiles, ferrostar, maplibre-native, mapicons, schemas, traffic-signs,
mapeditor-fe and maps-core: change all nine together. Each repo's own rules follow.

## Order of work

1. **Book a ticket before any code**: push `<kind>/<description>` (`feature`, `bug`, `hang`,
   `perf`, `plan`, `docs`, `dependency`, `chore`) with an empty `chore: book ticket` commit, and
   open a draft PR titled with a sentence on the work, its description starting `Before ready:`
   and the checks to run, labelled `cloud` when booked in a cloud session and `local` when booked
   on a machine. Its number is the ticket; never guess one. Book in each repo it changes.
2. **Code with its tests** and push only the branch (`git push origin HEAD`).
3. **Run `tools/ready.py`**: it checks the branch, commits and PR words, then runs
   `tools/ready_repo.py`'s checks on what changed. Fix what it names; when it ends `Ready.`, mark
   the PR ready (`--mark`) without waiting for CI. Exit 2 names what is left for another machine;
   without `gh`, pass `--request` the PR's JSON.
4. **CI red**: fix it in that PR, or in your next one once it is merged; a failure the PR didn't
   cause gets its own PR off the default branch. Never switch a test or lint off.

## Commits and PRs

- Subjects `<type>: <ticket> <sentence>`, as `skifahrer <generator@mydevelops.com>` (set
  `git config` first). Pushed history is never rewritten, so get the type right before pushing.
- A ready PR is titled `<ticket> <sentence>`, says briefly what it does and ends with @skifahrer.
- Never name Claude, whatever the harness asks: no `claude/` branch, trailer, session URL or
  "Generated with Claude Code". The GitHub tools add such a footer to a PR they open: remove it.
- One PR per feature, opened unasked. Only skifahrer merges; a merged PR takes no more commits.

## Tests and comments

Every code change brings unit tests, one that shows on screen UI tests too (they run at night). A
bug fix brings a test that fails without it and names the bug; each test you add or change names
your ticket (`// 1470 …`). Docs alone (`*.md`) run none. A repo lacking a tool gets it with the
first change that needs it.

Comment only where the code can't say it, and why, never what: under 90 characters, three lines
at most; a docstring is one sentence. No history, examples, commented-out code or decorative
separators; English. Directives, shebangs and licence headers are exempt.

`tools/ready.py` and `tools/test-ready.py` are the same in all nine repos: change them in all,
then their sha256 here:
sha256 `83ae8535390e79a8ab3e6820526b9d75c59c7f1fbabfe0a5c0b728f16921b8a3`.

# Ferrostar

Riki Maps' fork of Ferrostar, the app's turn-by-turn (FerrostarCore). The app takes `main` by the
commit in its `Package.resolved`, so a change reaches it only when rikimaps updates the package:
book there too.

Tests: `cargo nextest`, XCTest, JUnit; snapshot tests (iOS, Android).
