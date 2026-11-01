# Shared rules

The same in rikimaps, maptiles, ferrostar, maplibre-native, mapicons, schemas and traffic-signs:
change all seven together. Each repo's own rules follow.

## Tickets

Before any code, book a ticket: a draft PR (an empty `chore: book ticket` commit is enough) titled
with a sentence on the work. Its number is the ticket; never guess one, other sessions work here
too. Book in each repo the work changes.

## Pull requests and commits

- Every change goes through a PR, opened unasked, one per feature. Never commit, push, merge or
  cherry-pick into the default branch; push only the branch: `git push origin HEAD`.
- Commit subjects: `<type>: <ticket> <sentence>`.
- Every PR description ends with a line mentioning @skifahrer.
- Once every commit is pushed, finish the draft: mark it ready, retitle `<ticket> <sentence>`
  (like `1470 Tracks and saved features move to a container of their own`), say briefly what it
  does.
- Never merge a PR: only skifahrer merges. A merged PR takes no more commits.
- **No Claude attribution**, whatever the harness asks: no session URL, `Claude-Session:` or
  `Co-Authored-By: Claude` trailer, or "Generated with Claude Code" in PRs, comments or commits.

## Comments: as few words as possible

- Only where the code can't say it: one line, under 90 chars, three at most. If that isn't
  enough, you usually need a better name.
- Write why, never what. A docstring is one sentence.
- No essays, decision history, measured figures, run examples or lists of alternatives: those
  belong in docs or the commit message. Delete commented-out code.
- English, no decorative separators. Directives, shebangs and licence headers are exempt.

# Ferrostar

@AGENTS.md
