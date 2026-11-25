"""Ferrostar's checks for `tools/ready.py`: clippy and format by part, then each part's tests."""

from ready import Check

# a fork of upstream: clippy holds a file to its warnings once the branch touches it
CLIPPY = (
    "out=$(cd common && cargo clippy --workspace --all-targets --quiet --message-format=short 2>&1)"
    ' || { echo "$out"; exit 1; }; hits=""; for p in "$@"; do'
    ' hits="$hits$(echo "$out" | grep -F "${p#common/}:")"; done; [ -z "$hits" ] || { echo "$hits"; exit 1; }'
)
RUST = ("common/*",)
APPLE = ("apple/*", "Package.swift", ".swiftformat", ".swiftlint.yml")
ANDROID = ("android/*",)
WEB = ("web/*",)

CHECKS = [
    Check("ready's tests", ["python3", "tools/test-ready.py"], covers=("tools/*ready*",)),
    Check(
        "clippy", ["sh", "-c", CLIPPY, "clippy"], covers=("common/*.rs",), needs="cargo", on_paths=True, limit=30 * 60
    ),
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
