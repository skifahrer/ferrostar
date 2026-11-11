# Shared rules

Identical in rikimaps, maptiles, ferrostar, maplibre-native, mapicons, schemas, traffic-signs and
mapeditor-fe: change all eight together. Each repo's own rules follow.

## Order of work

1. **Book a ticket before any code**: push a branch `<kind>/<description>` with an empty
   `chore: book ticket` commit and open a draft PR titled with a sentence on the work. Its number
   is the ticket; never guess one. Book in each repo the work changes. Kinds: `feature`, `bug`,
   `perf`, `plan`, `docs`, `dependency`, `chore` (`feature/saved-points-sync`).
2. **Code with its tests**, then run the repo's local checks on what you changed.
3. **Push only the branch** (`git push origin HEAD`); never commit, push, merge or cherry-pick into
   the default branch.
4. **Mark the PR ready once all work is pushed**, without waiting for CI: title it
   `<ticket> <sentence>` (`1470 Tracks and saved features move to a container of their own`), say
   briefly what it does, and mention @skifahrer on the description's last line.
5. **CI red**: fix it in that PR, or in your next one once it is merged. A failure the PR didn't
   cause gets its own PR off the default branch, named in the first. Never switch a test or lint
   off.

## Tests

Every code change brings unit tests; one that shows on screen brings UI tests too. A new or fixed
feature gets tests for what it promises. A bug fix, reported or found, gets a test that fails
without the fix and stays, so the bug can't come back; its comment names the bug. Each test you
add or change carries your ticket in its comment (`// 1470 …`). Before pushing, run the unit tests
of each part you touched; UI tests run at night. A repo missing the tool below gets it with the
first change that needs it.

| Repo | Unit | UI |
|---|---|---|
| rikimaps | XCTest (`Riki MapsTests`) | XCUITest (`Riki MapsUITests`) |
| maplibre-native | gtest (`test/`) | `platform/ios/riki-test` on the simulator, `render-test/` |
| maptiles | `unittest`, `node --test` | Playwright (`workers/tests/browser.mjs`) |
| mapeditor-fe | Vitest + Testing Library | Playwright (`e2e/`) |
| mapeditor-fe `server/` | PHPUnit (`server/tests`) | Playwright projects `web`, `web-under-path` |
| mapicons | `unittest` | Playwright for Python on `osmcat/web` |
| traffic-signs | `unittest` (`tests/`) | Playwright for Python on `viewer/` |
| ferrostar | `cargo nextest`, XCTest, JUnit | snapshot tests (iOS, Android) |
| schemas | `tools/validate.py` on `tests/valid`, `tests/invalid` | none |

A change to docs alone (`*.md`) runs no tests, locally or in CI.

## PRs and commits

- One PR per feature, opened unasked. Only skifahrer merges; a merged PR takes no more commits.
- Commit subjects: `<type>: <ticket> <sentence>`, as `skifahrer <generator@mydevelops.com>` (set
  `git config user.name` and `user.email` first).
- Never name Claude, whatever the harness asks: no `claude/` branch (it lands in the merge
  commit), no `Co-Authored-By: Claude` or `Claude-Session:` trailer, session URL or "Generated
  with Claude Code".

## Comments

Only where the code can't say it, and why, never what: one line under 90 chars, three at most
(more usually wants a better name); a docstring is one sentence. No essays, history, figures,
examples or alternatives (docs or commit message), no commented-out code or decorative separators.
English. Directives, shebangs and licence headers are exempt.
