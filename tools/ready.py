#!/usr/bin/env python3
"""The one command before a pull request is marked ready: every local check, in order.

The same file in all eight repos (CLAUDE.md, shared rules). It checks the branch, its
commits and the pull request's words, then runs the repo's own checks from
`tools/ready_repo.py` for what the branch changed: lint, format, unit tests and anything the
repo adds. Docs alone run nothing. A check this machine cannot run is left, by name, for one
that can, and the branch is not ready until it has run.

    tools/ready.py                         # exit 0: mark it ready; 1: fix, push, run again
    tools/ready.py --mark                  # the same, and `gh pr ready` when everything passed
    tools/ready.py --request request.json  # without gh: the pull request as `gh pr view --json` gives it

Exit 2: everything this machine can run passed, and what is left is named. Logs are in
.build/ready/.
"""

import argparse
import contextlib
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, ".build", "ready")
KINDS = ("feature", "bug", "hang", "perf", "plan", "docs", "dependency", "chore")
AUTHOR = "skifahrer <generator@mydevelops.com>"
SUBJECT = re.compile(r"^[a-z]+: (\d+) \S")
BOOKING = "chore: book ticket"
REVERT = re.compile(r'^Revert "(.*)"$')
NAMES_CLAUDE = re.compile(
    r"co-authored-by:\s*claude|claude-session:|claude\.ai/code|generated (?:with|by) \[?claude", re.IGNORECASE
)
MENTION = "@skifahrer"
BEFORE_READY = "Before ready:"
REQUEST_FIELDS = "number,title,body,mergeable,isDraft,state,labels"
WHERE = ("cloud", "local")
# READY_PLATFORM=linux tries the Linux run on a Mac.
PLATFORM = os.environ.get("READY_PLATFORM", sys.platform)
STEP_LIMIT = 15 * 60


@dataclass
class Check:
    """A repo's check: `covers` globs the paths that run it, `needs` a platform or a program.

    `tool` is a pinned Python package, `ruff==0.16.10`, installed into .build/tools for it;
    `on_paths` hands it the changed paths it covers, so a file is held to it once touched.
    """

    name: str
    command: list
    covers: tuple = ("*",)
    needs: str = None
    limit: int = STEP_LIMIT
    waits: bool = False
    tool: str = None
    on_paths: bool = False


def branch_fault(branch, default="master"):
    kind, _, description = branch.partition("/")
    if branch in (default, "master", "main", ""):
        return "this is the default branch; work happens on `<kind>/<description>`"
    if kind not in KINDS or not description:
        return f"`{branch}` is not `<kind>/<description>`, kind one of {', '.join(KINDS)}"
    return None


def reverted(subject):
    """The subject a `git revert` commit's subject names, unwrapped as often as it was reverted."""
    while match := REVERT.match(subject):
        subject = match.group(1)
    return subject


def commit_faults(commits):
    """`commits` are (subject, author, body). A merge, by anyone, and the booking commit pass.

    3629: another ticket's commit is the pull request this one is stacked on, merged in.
    """
    faults = []
    for subject, author, body in commits:
        short = subject[:60]
        if NAMES_CLAUDE.search(subject + "\n" + body):
            faults.append(f"`{short}` names Claude")
        # 3829 git revert names a commit so, and a pushed one is never renamed
        subject = reverted(subject)
        if subject.startswith("Merge "):
            continue
        if author != AUTHOR:
            faults.append(f"`{short}` is by {author}, not {AUTHOR}")
        if subject == BOOKING:
            continue
        if not SUBJECT.match(subject):
            faults.append(f"`{short}` is not `<type>: <ticket> <sentence>`")
    return faults


def pull_request_faults(number, title, body):
    faults = []
    if not title.startswith(f"{number} "):
        faults.append(f"the title must be `{number} <sentence>`, it is `{title}`")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(BEFORE_READY):
        faults.append(f"the description must start `{BEFORE_READY}` and the checks to run")
    if not lines or lines[-1] != MENTION:
        faults.append(f"the description's last line must be {MENTION}")
    if not [line for line in lines if line != MENTION and not line.startswith(BEFORE_READY)]:
        faults.append("the description says nothing of what the pull request does")
    if NAMES_CLAUDE.search(title + "\n" + body):
        faults.append("the title or description names Claude")
    return faults


def booked_here():
    """The label a PR booked on this machine carries: a cloud session sets CLAUDE_CODE_REMOTE."""
    return "cloud" if os.environ.get("CLAUDE_CODE_REMOTE") == "true" else "local"


def label_names(labels):
    """Label names from gh's `{"name": …}` objects or the GitHub API's plain strings."""
    return {label["name"] if isinstance(label, dict) else label for label in labels or []}


def label_faults(labels, here=None):
    """A PR carries one of WHERE: where it was booked, which may not be where ready.py runs."""
    found = label_names(labels) & set(WHERE)
    if len(found) == 1:
        return []
    if found:
        return ["the PR is labelled both `cloud` and `local`: keep the one for where it was booked"]
    return [f"the PR has no `cloud` or `local` label: one booked here is `{here or booked_here()}`"]


def code_paths(paths):
    """The changed paths that run checks: all but docs."""
    return [path for path in paths if not path.endswith(".md")]


def covered(check, paths):
    """The paths `check` covers."""
    return [path for path in paths if any(fnmatch.fnmatch(path, glob) for glob in check.covers)]


def missing(needs, platform=None):
    """Why this machine cannot run a check that `needs` a platform or a program, or None."""
    platform = platform or PLATFORM
    if not needs:
        return None
    if needs in ("darwin", "linux", "win32"):
        return None if needs == platform else f"runs on {needs}"
    return None if shutil.which(needs) else f"needs {needs}, which is not installed here"


def tool_path(requirement):
    """The bin folder of a venv in .build/tools holding `requirement`, made the first time."""
    venv = os.path.join(ROOT, ".build", "tools", re.sub(r"[^A-Za-z0-9.]+", "-", requirement))
    bin_dir = os.path.join(venv, "bin")
    if not os.path.isfile(os.path.join(venv, "done")):
        for command in (
            [sys.executable, "-m", "venv", venv],
            [os.path.join(bin_dir, "python"), "-m", "pip", "install", "--quiet", requirement],
        ):
            status, output = run(command)
            if status != 0:
                return None, output
        open(os.path.join(venv, "done"), "w").close()
    return bin_dir, ""


def took(seconds):
    """A span as a step's line says it: `42s`, `3m 05s`, `1h 02m`."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"


def run(command, log=None, env=None, shown=None, limit=None):
    """(exit status, output), stopped after `limit` seconds; `shown(line)` prints a line as it comes."""
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, **(env or {})},
            start_new_session=True,
        )
    except FileNotFoundError as missing:
        return 127, f"{missing.filename}: not installed here\n"
    stopped = threading.Event()

    def stop():
        stopped.set()
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)

    timer = threading.Timer(limit, stop) if limit else None
    if timer:
        timer.start()
    lines = []
    for line in process.stdout:
        lines.append(line)
        if shown and shown(line):
            print("    " + line.rstrip(), flush=True)
    process.stdout.close()
    status = process.wait()
    if timer:
        timer.cancel()
    output = "".join(lines)
    if stopped.is_set():
        output += f"\nstopped after {took(limit)}, the limit of {log or command[0]}\n"
        status = 124
    if log:
        os.makedirs(LOGS, exist_ok=True)
        with open(os.path.join(LOGS, log), "w") as file:
            file.write(output)
    return status, output


def git(*arguments):
    return run(["git", *arguments])[1].strip()


class Report:
    def __init__(self, clock=time.monotonic):
        self.failed = []
        self.left = []
        self.clock = clock
        self.started = self.last = clock()

    def spent(self):
        """The time since the step before, when it is worth saying."""
        now = self.clock()
        spent, self.last = now - self.last, now
        return f" ({took(spent)})" if spent >= 1 else ""

    def passed(self, what, note=""):
        print(f"✔ {what}" + (f": {note}" if note else "") + self.spent(), flush=True)

    def fail(self, what, faults):
        self.failed.append(what)
        print(f"✘ {what}" + self.spent(), flush=True)
        for fault in faults:
            print(f"    {fault}")

    def leave(self, what, why):
        """A check this machine cannot run; the branch waits for one that can."""
        self.left.append(what)
        print(f"… {what}: {why}", flush=True)

    def total(self):
        return took(self.clock() - self.started)

    def judge(self, what, faults, note=""):
        if faults:
            self.fail(what, faults)
        else:
            self.passed(what, note)


def run_checks(report, paths, checks):
    """Each check the paths reach, in order; one that `waits` starts only when nothing failed."""
    for check in checks:
        reached = covered(check, paths)
        if not reached:
            continue
        why = missing(check.needs)
        if why:
            report.leave(check.name, f"{why}: run tools/ready.py where it can")
            continue
        if check.waits and report.failed:
            report.fail(check.name, ["not started: fix what failed above first, it is cheaper"])
            continue
        env = None
        if check.tool:
            bin_dir, output = tool_path(check.tool)
            if not bin_dir:
                report.fail(check.name, [f"could not install {check.tool}", *output.splitlines()[-5:]])
                continue
            env = {"PATH": bin_dir + os.pathsep + os.environ.get("PATH", "")}
        command = check.command + (
            [path for path in reached if os.path.exists(os.path.join(ROOT, path))] if check.on_paths else []
        )
        if check.on_paths and command == check.command:
            continue
        log = re.sub(r"[^a-z0-9]+", "-", check.name.lower()).strip("-") + ".log"
        status, output = run(command, log=log, env=env, limit=check.limit)
        report.judge(check.name, [*output.splitlines()[-15:], f"all of it: .build/ready/{log}"] if status != 0 else [])


def default_branch():
    ref = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref.startswith("origin/"):
        return ref[len("origin/") :]
    head = git("ls-remote", "--symref", "origin", "HEAD").splitlines()
    if head and head[0].startswith("ref: refs/heads/"):
        return head[0][len("ref: refs/heads/") :].split("\t")[0]
    return "master"


def changed_paths(base):
    fork = git("merge-base", "HEAD", f"origin/{base}")
    return [path for path in git("diff", "--name-only", fork, "HEAD").splitlines() if path]


def commits_on_branch(base):
    raw = git("log", "--format=%s%x1f%an <%ae>%x1f%b%x1e", f"origin/{base}..HEAD")
    # Python's strip takes the separators for space, so an empty body loses its field.
    return [
        tuple(([part.strip() for part in entry.split("\x1f")] + ["", ""])[:3])
        for entry in raw.split("\x1e")
        if entry.strip()
    ]


def pull_request(given=None):
    """The open pull request, from `given` (gh's or the GitHub API's JSON) or gh; "no gh" when neither can."""
    if given:
        with open(given) as file:
            return json.load(file)
    if not shutil.which("gh"):
        return "no gh"
    status, output = run(["gh", "pr", "view", "--json", REQUEST_FIELDS])
    return json.loads(output) if status == 0 else None


def check_branch_and_request(report, base, given=None):
    branch = git("branch", "--show-current")
    fault = branch_fault(branch, base)
    report.judge("branch", [fault] if fault else [], branch)

    dirty = git("status", "--porcelain")
    report.judge("everything is committed", ["uncommitted: " + line for line in dirty.splitlines()])

    git("fetch", "--quiet", "origin")
    ahead = git("rev-parse", "HEAD") != git("rev-parse", "--verify", "--quiet", f"origin/{branch}")
    report.judge("everything is pushed", ["`git push origin HEAD` first"] if ahead else [])

    merges = run(["git", "merge-tree", "--write-tree", f"origin/{base}", "HEAD"])[0] == 0
    report.judge(
        f"merges into {base}", [] if merges else [f"conflicts: merge origin/{base} in (never rebase), check, push"]
    )

    request = pull_request(given)
    if request == "no gh":
        report.leave(
            "pull request's words", f"no gh here: pass --request with `gh pr view --json {REQUEST_FIELDS}`'s answer"
        )
        request = None
    elif request is None or str(request.get("state")).upper() != "OPEN":
        report.fail("pull request", ["no open pull request for this branch: book the ticket first"])
        request = None
    else:
        report.judge(
            "pull request's words",
            pull_request_faults(request["number"], request["title"], request["body"])
            + label_faults(request.get("labels")),
            f"#{request['number']}",
        )
    report.judge("commits", commit_faults(commits_on_branch(base)))
    return request


def repo_checks():
    """This repo's `ready_repo.py`, loaded once with this module importable as `ready`."""
    sys.modules.setdefault("ready", sys.modules[__name__])
    path = os.path.join(ROOT, "tools", "ready_repo.py")
    spec = importlib.util.spec_from_file_location("ready_repo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_repo(report, paths, repo):
    """The repo's checks: its own `check(report, paths)` when it has one, else its CHECKS."""
    if hasattr(repo, "check"):
        repo.check(report, paths)
    else:
        run_checks(report, paths, repo.CHECKS)


def verdict(report):
    if report.failed:
        print(
            f"\nNot ready after {report.total()}: {', '.join(report.failed)}. Fix, push, and run tools/ready.py again."
        )
        return 1
    if report.left:
        print(
            f"\nAll this machine can run passed, in {report.total()}; not ready until "
            f"tools/ready.py runs where it can check: {', '.join(report.left)}."
        )
        return 2
    print(f"\nEvery check passed, in {report.total()}.\nReady.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mark", action="store_true", help="mark the pull request ready when all passed")
    parser.add_argument("--request", help=f"the pull request as `gh pr view --json {REQUEST_FIELDS}` gives it")
    args = parser.parse_args(argv)

    report = Report()
    base = default_branch()
    request = check_branch_and_request(report, base, args.request)
    paths = changed_paths(base)
    code = code_paths(paths)
    if not paths:
        report.fail("changes", ["the branch changes nothing yet"])
    elif not code:
        report.passed("docs alone", "no checks to run")
    else:
        check_repo(report, code, repo_checks())

    status = verdict(report)
    if status == 0 and args.mark and request and request.get("isDraft", request.get("draft")):
        if not shutil.which("gh"):
            print(f"Mark #{request['number']} ready by hand: no gh here.")
            return 0
        return run(["gh", "pr", "ready", str(request["number"])])[0]
    if status == 0 and not args.mark:
        print("Mark it: gh pr ready   (or tools/ready.py --mark next time)")
    return status


if __name__ == "__main__":
    sys.exit(main())
