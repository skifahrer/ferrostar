#!/usr/bin/env python3
"""Tests for `ready.py`, the same file in all eight repos as the script they test.

python3 tools/test-ready.py
"""

import hashlib
import importlib.util
import os
import re
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ready", os.path.join(TOOLS, "ready.py"))
ready = importlib.util.module_from_spec(spec)
sys.modules["ready"] = ready
spec.loader.exec_module(ready)

BY = ready.AUTHOR
GOOD_BODY = "Before ready: tools/ready.py --mark\n\nOpens the store in memory.\n\n@skifahrer\n"


class JudgingTests(unittest.TestCase):
    """3199: what the command calls a fault, with nothing run."""

    def test_a_branch_is_kind_and_description(self):
        self.assertIsNone(ready.branch_fault("bug/buildings-stand-at-zoom-17"))
        # 3538 a hang fix books on a hang branch
        self.assertIsNone(ready.branch_fault("hang/tones-off-main"))
        for wrong in ("master", "main", "", "claude/fix-things", "bug/", "buildings"):
            with self.subTest(wrong):
                self.assertIsNotNone(ready.branch_fault(wrong))

    # 3728 a repo whose default branch has another name
    def test_the_default_branch_by_any_name_is_no_work_branch(self):
        self.assertIsNotNone(ready.branch_fault("feature/icons", default="feature/icons"))

    def test_a_commit_carries_the_type_and_the_ticket(self):
        good = [
            ("fix: 3199 The store opens", BY, ""),
            ("chore: book ticket", BY, ""),
            ("Merge remote-tracking branch 'origin/master' into bug/x", BY, ""),
        ]
        self.assertEqual(ready.commit_faults(good), [])
        self.assertEqual(len(ready.commit_faults([("The store opens", BY, "")])), 1)
        self.assertEqual(len(ready.commit_faults([("fix: the store opens", BY, "")])), 1)

    # 3629 a stacked pull request carries the commits of the one it builds on
    def test_a_commit_of_another_ticket_passes_as_stacked_work(self):
        self.assertEqual(ready.commit_faults([("fix: 3100 The store opens", BY, "")]), [])

    # 3629 a merge is git's, whoever ran it; it may still not name Claude
    def test_a_merge_by_somebody_else_passes_unless_it_names_claude(self):
        merge = "Merge remote-tracking branch 'origin/master' into feature/x"
        self.assertEqual(ready.commit_faults([(merge, "Someone <a@b.c>", "")]), [])
        named = "Co-Authored-By: Claude <noreply@anthropic.com>"
        self.assertEqual(len(ready.commit_faults([(merge, "Someone <a@b.c>", named)])), 1)

    def test_a_commit_by_somebody_else_is_a_fault(self):
        faults = ready.commit_faults([("fix: 3199 The store opens", "Someone <a@b.c>", "")])
        self.assertEqual(len(faults), 1)

    def test_a_commit_that_names_claude_is_a_fault(self):
        for body in (
            "Co-Authored-By: Claude <noreply@anthropic.com>",
            "Claude-Session: https://claude.ai/code/session_1",
            "Generated with [Claude Code](https://claude.com/claude-code)",
        ):
            with self.subTest(body):
                self.assertEqual(len(ready.commit_faults([("fix: 3199 It opens", BY, body)])), 1)

    def test_a_pull_request_has_its_number_its_words_and_its_mention(self):
        self.assertEqual(ready.pull_request_faults(3199, "3199 The store opens", GOOD_BODY), [])
        self.assertEqual(len(ready.pull_request_faults(3199, "The store opens", GOOD_BODY)), 1)
        no_mention = GOOD_BODY.replace("@skifahrer", "")
        self.assertEqual(len(ready.pull_request_faults(3199, "3199 The store opens", no_mention)), 1)
        named = GOOD_BODY.replace("@skifahrer", "🤖 Generated with [Claude Code](https://claude.com)\n\n@skifahrer")
        self.assertEqual(len(ready.pull_request_faults(3199, "3199 The store opens", named)), 1)

    # 3728 the next agent learns from the first line what to run before ready
    def test_a_description_starts_with_the_checks_to_run_before_ready(self):
        body = "Opens the store in memory.\n\n@skifahrer"
        self.assertEqual(len(ready.pull_request_faults(3199, "3199 The store opens", body)), 1)

    # 3728 a `Before ready:` line alone says nothing of the work
    def test_a_description_says_what_the_pull_request_does(self):
        body = "Before ready: nothing, docs only.\n\n@skifahrer"
        self.assertEqual(len(ready.pull_request_faults(3199, "3199 The store opens", body)), 1)

    def test_a_booking_description_is_not_ready(self):
        self.assertTrue(ready.pull_request_faults(3199, "The store opens", "Before ready: x\n\nBooking."))

    def test_docs_alone_run_no_checks(self):
        self.assertEqual(ready.code_paths(["STANDARDS.md", ".planning/a.md", "src/README.md"]), [])
        self.assertEqual(ready.code_paths(["CLAUDE.md", "tools/lint.sh"]), ["tools/lint.sh"])


class CheckTests(unittest.TestCase):
    """3728 a repo's checks run by what changed, in order, and on the platform they need."""

    def setUp(self):
        self.ran = []
        self.saved = ready.run, ready.PLATFORM, ready.git
        ready.PLATFORM = "linux"
        ready.run = lambda command, **_: self.ran.append(command[0]) or self.status.get(command[0], (0, ""))
        self.status = {}

    def tearDown(self):
        ready.run, ready.PLATFORM, ready.git = self.saved

    def checks(self, *checks):
        report = ready.Report()
        ready.run_checks(report, ["src/app.py", "tools/build.sh"], list(checks))
        return report

    # 3728
    def test_a_check_runs_only_when_a_path_it_covers_changed(self):
        self.checks(ready.Check("lint", ["ruff"], covers=("*.py",)), ready.Check("web", ["npm"], covers=("web/*",)))
        self.assertEqual(self.ran, ["ruff"])

    # 3728 a check another machine runs is left, by name, and the branch is not ready
    def test_a_check_for_another_platform_is_left_for_it(self):
        report = self.checks(ready.Check("build", ["xcodebuild"], needs="darwin"))
        self.assertEqual(self.ran, [])
        self.assertEqual(report.left, ["build"])
        self.assertEqual(ready.verdict(report), 2)

    # 3728 a slow check waits until the cheap ones pass
    def test_a_waiting_check_starts_only_when_nothing_failed(self):
        self.status["ruff"] = (1, "E501 line too long")
        report = self.checks(ready.Check("lint", ["ruff"]), ready.Check("unit", ["pytest"], waits=True))
        self.assertEqual(self.ran, ["ruff"])
        self.assertEqual(report.failed, ["lint", "unit"])
        self.assertEqual(ready.verdict(report), 1)

    # 3728
    def test_every_check_passing_is_ready(self):
        report = self.checks(ready.Check("lint", ["ruff"]), ready.Check("unit", ["pytest"], waits=True))
        self.assertEqual(self.ran, ["ruff", "pytest"])
        self.assertEqual(ready.verdict(report), 0)

    # 3728 a check that `on_paths` is handed only the changed files it covers
    def test_a_check_on_paths_gets_the_files_it_covers(self):
        given = []
        ready.run = lambda command, **_: given.append(command) or (0, "")
        checks = [
            ready.Check("format", ["ruff", "format", "--check"], covers=("*.py",), on_paths=True),
            ready.Check("shell", ["shellcheck"], covers=("*.zsh",), on_paths=True),
        ]
        ready.run_checks(ready.Report(), ["tools/ready.py", "tools/deleted-on-this-branch.py"], checks)
        self.assertEqual(given, [["ruff", "format", "--check", "tools/ready.py"]])

    # 3728 a check that needs a program this machine lacks is left for one that has it
    def test_a_check_needing_a_missing_program_is_left(self):
        report = self.checks(ready.Check("format", ["swiftformat"], needs="no-such-program-anywhere"))
        self.assertEqual((self.ran, report.left), ([], ["format"]))
        self.assertIsNone(ready.missing("python3" if ready.shutil.which("python3") else "sh"))
        self.assertIsNotNone(ready.missing("darwin", platform="linux"))
        self.assertIsNone(ready.missing("linux", platform="linux"))

    # 3728 a pinned tool runs from its own venv, first on PATH
    def test_a_pinned_tool_runs_from_its_venv(self):
        given = []
        saved = ready.tool_path
        ready.tool_path = lambda requirement: (f"/venv/{requirement}", "")
        ready.run = lambda _command, env=None, **_: given.append(env["PATH"].split(ready.os.pathsep)[0]) or (0, "")
        try:
            self.checks(ready.Check("lint", ["ruff", "check", "."], tool="ruff==0.16.10"))
        finally:
            ready.tool_path = saved
        self.assertEqual(given, ["/venv/ruff==0.16.10"])

    # 3728 without gh the pull request is read from the file `--request` names
    def test_the_pull_request_can_come_from_a_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file:
            # 3728 the GitHub API's answer says `open`, gh's `OPEN`
            file.write('{"number": 7, "title": "7 It opens", "body": "", "state": "open"}')
        try:
            self.assertEqual(ready.pull_request(file.name)["number"], 7)
            report = ready.Report()
            ready.git = lambda *_: ""
            self.assertEqual(ready.check_branch_and_request(report, "master", file.name)["number"], 7)
            self.assertNotIn("pull request", report.failed)
        finally:
            os.unlink(file.name)


class TimingTests(unittest.TestCase):
    """3614 a step says how long it took, stops at its limit, and the tests show as they run."""

    # 3614
    def test_a_span_reads_in_seconds_minutes_or_hours(self):
        self.assertEqual([ready.took(s) for s in (42, 185, 3720)], ["42s", "3m 05s", "1h 02m"])

    # 3614 instant checks say no time; a step that took some says it
    def test_each_line_says_the_time_since_the_one_before(self):
        now = [0.0]
        report = ready.Report(clock=lambda: now[0])
        self.assertEqual(report.spent(), "")
        now[0] = 125.0
        self.assertEqual(report.spent(), " (2m 05s)")
        self.assertEqual(report.total(), "2m 05s")

    # 3614 a step past its limit is stopped and fails, saying so
    def test_a_step_past_its_limit_stops_and_fails(self):
        status, output = ready.run(["sleep", "30"], limit=1)
        self.assertEqual(status, 124)
        self.assertIn("stopped after 1s", output)

    # 3728 a tool this machine lacks fails its check instead of the script
    def test_a_missing_tool_fails_its_check(self):
        status, output = ready.run(["no-such-tool-anywhere"])
        self.assertEqual(status, 127)
        self.assertIn("not installed", output)


class SharedTests(unittest.TestCase):
    """3728 the script and these tests are the same in all eight repos."""

    # 3728 an edit in one repo alone fails here until CLAUDE.md, in all eight, names its hash
    def test_the_shared_files_match_the_hash_claude_md_names(self):
        digest = hashlib.sha256()
        for name in ("ready.py", "test-ready.py"):
            with open(os.path.join(TOOLS, name), "rb") as file:
                digest.update(file.read())
        with open(os.path.join(os.path.dirname(TOOLS), "CLAUDE.md")) as file:
            named = re.search(r"sha256 `([0-9a-f]{64})`", file.read())
        self.assertIsNotNone(named, "CLAUDE.md names no sha256 of tools/ready.py and tools/test-ready.py")
        self.assertEqual(
            named.group(1),
            digest.hexdigest(),
            "tools/ready.py or tools/test-ready.py changed: change all eight repos, then the hash in their CLAUDE.md",
        )

    # 3728 every repo carries its own checks beside the shared script
    def test_this_repo_has_its_checks(self):
        repo = ready.repo_checks()
        if hasattr(repo, "check"):
            return
        names = [check.name for check in repo.CHECKS]
        self.assertTrue(names)
        self.assertEqual(sorted(names), sorted(set(names)), "two checks share a name, and so a log")
        self.assertEqual([c for c in repo.CHECKS if not isinstance(c, ready.Check)], [])


if __name__ == "__main__":
    unittest.main()
