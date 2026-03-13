"""Best-effort local equivalents for common GitHub Actions."""

import re

# Map action references to their local shell equivalents.
# Each entry: pattern (regex on the action ref) -> (description, command)
ACTION_EQUIVALENTS = [
    (
        r"^actions/checkout@",
        "Clone/checkout repository (already mounted at /workspace)",
        "echo 'Repository is mounted at /workspace via Docker volume'",
    ),
    (
        r"^actions/setup-node@",
        "Install Node.js",
        "apt-get update -qq && apt-get install -y -qq nodejs npm > /dev/null 2>&1 && node --version && npm --version",
    ),
    (
        r"^actions/setup-python@",
        "Install Python",
        "apt-get update -qq && apt-get install -y -qq python3 python3-pip > /dev/null 2>&1 && python3 --version",
    ),
    (
        r"^actions/setup-go@",
        "Install Go",
        "apt-get update -qq && apt-get install -y -qq golang > /dev/null 2>&1 && go version",
    ),
    (
        r"^actions/setup-java@",
        "Install Java",
        "apt-get update -qq && apt-get install -y -qq default-jdk > /dev/null 2>&1 && java --version",
    ),
    (
        r"^actions/cache@",
        "Cache (no-op locally)",
        "echo 'Caching is not needed in local debugging mode'",
    ),
    (
        r"^actions/upload-artifact@",
        "Upload artifact (no-op locally)",
        "echo 'Artifacts are available locally in the mounted workspace'",
    ),
    (
        r"^actions/download-artifact@",
        "Download artifact (no-op locally)",
        "echo 'Artifacts are available locally in the mounted workspace'",
    ),
]


def get_action_equivalent(action_ref: str) -> tuple[str, str] | None:
    """Return (description, command) for a known action, or None."""
    for pattern, desc, cmd in ACTION_EQUIVALENTS:
        if re.match(pattern, action_ref):
            return desc, cmd
    return None
