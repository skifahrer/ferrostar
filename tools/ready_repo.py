"""Ferrostar's checks for `tools/ready.py`: clippy and format by part, then each part's tests."""

from ready import Check

# a fork of upstream: clippy holds a file to its warnings once the branch touches it
CLIPPY = """
import json, subprocess, sys
touched = {p.removeprefix("common/") for p in sys.argv[1:]}
run = subprocess.run(["cargo", "clippy", "--workspace", "--all-targets", "--quiet", "--message-format=json"],
                     cwd="common", capture_output=True, text=True)
hits = []
for line in run.stdout.splitlines():
    message = json.loads(line).get("message") if line.startswith("{") else None
    spans = [s for s in (message or {}).get("spans", []) if s.get("is_primary")]
    if message and (message["level"] == "error" or any(s["file_name"] in touched for s in spans)):
        hits.append(message["rendered"])
print("".join(hits) or (run.stderr if run.returncode else ""), end="")
sys.exit(1 if hits or run.returncode else 0)
"""
RUST = ("common/*",)
APPLE = ("apple/*", "Package.swift", ".swiftformat", ".swiftlint.yml")
ANDROID = ("android/*",)
WEB = ("web/*",)

CHECKS = [
    Check("ready's tests", ["python3", "tools/test-ready.py"], covers=("tools/*ready*",)),
    Check("clippy", ["python3", "-c", CLIPPY], covers=("common/*.rs",), needs="cargo", on_paths=True, limit=30 * 60),
    Check("format, Rust", ["sh", "-c", "cd common && cargo fmt --check"], covers=RUST, needs="cargo"),
    Check("SwiftLint", ["swiftlint", "lint", "--quiet", "--strict"], covers=APPLE, needs="swiftlint"),
    Check("format, Swift", ["swiftformat", ".", "--lint"], covers=APPLE, needs="swiftformat"),
    Check(
        "format, Kotlin",
        ["sh", "-c", "cd android && ./gradlew -q ktfmtCheck"],
        covers=ANDROID,
        needs="java",
        limit=30 * 60,
    ),
    Check(
        "lint and format, web",
        ["sh", "-c", "cd web && npm install --silent && npm run format:check && npm run lint"],
        covers=WEB,
        needs="npm",
    ),
    Check(
        "unit tests, Rust",
        ["sh", "-c", "cd common && cargo nextest run --no-fail-fast && cargo test --doc"],
        covers=RUST,
        needs="cargo-nextest",
        waits=True,
        limit=30 * 60,
    ),
    Check(
        "unit tests, Android",
        ["sh", "-c", "cd android && ./gradlew -q test"],
        covers=ANDROID + RUST,
        needs="java",
        waits=True,
        limit=45 * 60,
    ),
    Check(
        "unit tests, Apple",
        [
            "xcodebuild",
            "-scheme",
            "FerrostarCore-Package",
            "test",
            "-skipMacroValidation",
            "-destination",
            "platform=iOS Simulator,name=iPhone 13",
        ],
        covers=APPLE + RUST,
        needs="darwin",
        waits=True,
        limit=45 * 60,
    ),
    Check("unit tests, web", ["sh", "-c", "cd web && npm test -- --run"], covers=WEB + RUST, needs="npm", waits=True),
]
